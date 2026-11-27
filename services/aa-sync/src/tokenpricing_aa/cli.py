from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tokenpricing_aa.alerting import (
    Delivery,
    payload_not_found_alert,
    request_blocked_alert,
    schema_drift_alert,
    send_alert,
)
from tokenpricing_aa.fetch import (
    LEADERBOARD_URL,
    FetchBlockedError,
    fetch_leaderboard,
    fetch_openness_page,
)
from tokenpricing_aa.flight import PayloadNotFoundError
from tokenpricing_aa.normalize import normalize_sources
from tokenpricing_aa.parse import offering_objects
from tokenpricing_aa.paths import (
    CURRENT_DATABASE_DIR,
    HISTORY_DIR,
    OFFERING_MANIFEST_PATH,
    RAW_CAPTURE_DIR,
)
from tokenpricing_aa.schema import build_manifest, check_drift

DATASET_NAME = "artificial-analysis"

logger = logging.getLogger(__name__)


class DriftError(RuntimeError):
    """Breaking drift was detected, so nothing was published.

    A stale snapshot is recoverable; a snapshot silently missing a column or
    carrying rescaled units is not. The run stops before writing.
    """


def ensure_directories() -> None:
    CURRENT_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    RAW_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit UTF-8: benchmark names carry non-ASCII, which the platform default
    # encoding rejects on Windows.
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _raw_paths() -> tuple[Path, Path]:
    return RAW_CAPTURE_DIR / "leaderboard.json", RAW_CAPTURE_DIR / "openness.json"


def sync(delivery: Delivery | None = None) -> dict[str, Any]:
    """Fetch both AA pages, keep the raw capture, check shape, then publish.

    Each of the three failure modes alerts under its own name before propagating.
    """
    ensure_directories()
    try:
        leaderboard = fetch_leaderboard()
        openness = fetch_openness_page()
    except FetchBlockedError as exc:
        send_alert(request_blocked_alert(exc.url, exc), delivery)
        raise

    leaderboard_path, openness_path = _raw_paths()
    write_json(leaderboard_path, leaderboard)
    write_json(openness_path, openness)
    return _build(leaderboard, openness, delivery)


def normalize_only(delivery: Delivery | None = None) -> dict[str, Any]:
    """Rebuild the dataset from the raw capture already on disk."""
    ensure_directories()
    leaderboard_path, openness_path = _raw_paths()
    return _build(read_json(leaderboard_path), read_json(openness_path), delivery)


def _build(
    leaderboard: dict[str, Any],
    openness: dict[str, Any],
    delivery: Delivery | None = None,
) -> dict[str, Any]:
    try:
        objects = offering_objects(leaderboard["page"])
    except PayloadNotFoundError as exc:
        send_alert(payload_not_found_alert(str(leaderboard.get("source_url")), exc), delivery)
        raise

    drift = check_drift(objects)
    if drift.new:
        logger.info("new payload fields (informational): %s", ", ".join(drift.new))
    if drift.breaking:
        send_alert(schema_drift_alert(DATASET_NAME, drift), delivery)
        raise DriftError(
            f"breaking payload drift, nothing published -- {drift.summary()}"
        )

    try:
        dataset = normalize_sources(leaderboard, openness, drift=drift)
    except PayloadNotFoundError as exc:
        send_alert(payload_not_found_alert(str(openness.get("source_url")), exc), delivery)
        raise

    payload = dataset.model_dump(mode="json")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    current_path = CURRENT_DATABASE_DIR / f"{DATASET_NAME}.json"
    history_path = HISTORY_DIR / f"{DATASET_NAME}-{timestamp}.json"
    write_json(current_path, payload)
    write_json(history_path, payload)
    return {
        "snapshot": str(current_path),
        "history_snapshot": str(history_path),
        "providers": dataset.metadata.provider_count,
        "offerings": dataset.metadata.offering_count,
        "deprecated_offerings": dataset.metadata.deprecated_offering_count,
        "openness_rows": dataset.metadata.openness_row_count,
        "openness_matched": dataset.metadata.openness_matched,
        "openness_unmatched": dataset.metadata.openness_unmatched,
        "openness_ambiguous": dataset.metadata.openness_ambiguous,
        "new_payload_fields": drift.new,
    }


def build_manifest_command(from_capture: bool = False) -> dict[str, Any]:
    """Regenerate ``schema/offering-manifest.json`` from the live payload.

    Run this deliberately, after reviewing what changed -- it is the act of
    accepting a new payload shape as expected.
    """
    if from_capture:
        leaderboard = read_json(_raw_paths()[0])
    else:
        leaderboard = fetch_leaderboard()
    manifest = build_manifest(offering_objects(leaderboard["page"]))
    write_json(OFFERING_MANIFEST_PATH, manifest)
    return {
        "manifest": str(OFFERING_MANIFEST_PATH),
        "records": manifest["record_count"],
        "fields": len(manifest["fields"]),
        "source": str(leaderboard.get("source_url", LEADERBOARD_URL)),
    }


def check_command() -> dict[str, Any]:
    """Compare the live payload against the manifest without publishing."""
    leaderboard = fetch_leaderboard()
    drift = check_drift(offering_objects(leaderboard["page"]))
    return {
        "records": drift.record_count,
        "breaking": drift.breaking,
        "missing": drift.missing,
        "type_changed": drift.type_changed,
        "range_shifted": drift.range_shifted,
        "new": drift.new,
        "summary": drift.summary(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Artificial Analysis acquisition for tokenpricing"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "sync", help="fetch Artificial Analysis pages and rebuild the AA dataset"
    )
    subparsers.add_parser(
        "normalize", help="rebuild the AA dataset from the local raw capture"
    )
    subparsers.add_parser(
        "check", help="compare the live payload against the expected-shape manifest"
    )
    manifest = subparsers.add_parser(
        "build-manifest", help="regenerate the expected-shape manifest"
    )
    manifest.add_argument(
        "--from-capture",
        action="store_true",
        help="use the local raw capture instead of fetching",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "sync":
        print(json.dumps(sync(), indent=2))
        return
    if args.command == "normalize":
        print(json.dumps(normalize_only(), indent=2))
        return
    if args.command == "check":
        print(json.dumps(check_command(), indent=2))
        return
    if args.command == "build-manifest":
        print(json.dumps(build_manifest_command(args.from_capture), indent=2))
        return
    parser.error("unknown command")
