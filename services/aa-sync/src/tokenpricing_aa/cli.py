from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tokenpricing_aa.fetch import fetch_openness_page, fetch_provider_pages
from tokenpricing_aa.normalize import normalize_sources
from tokenpricing_aa.paths import (
    CURRENT_DATABASE_DIR,
    HISTORY_DIR,
    RAW_CAPTURE_DIR,
)

DATASET_NAME = "artificial-analysis"


def ensure_directories() -> None:
    CURRENT_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    RAW_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit UTF-8: benchmark names carry non-ASCII (τ²-Bench), which the
    # platform default encoding rejects on Windows.
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _raw_paths() -> tuple[Path, Path]:
    return RAW_CAPTURE_DIR / "providers.json", RAW_CAPTURE_DIR / "openness.json"


def sync() -> dict[str, Any]:
    """Fetch AA pages, keep the raw capture, then normalize it."""
    ensure_directories()
    providers = fetch_provider_pages()
    openness = fetch_openness_page()
    providers_path, openness_path = _raw_paths()
    write_json(providers_path, providers)
    write_json(openness_path, openness)
    return _build(providers, openness)


def normalize_only() -> dict[str, Any]:
    """Rebuild the dataset from the raw capture already on disk."""
    ensure_directories()
    providers_path, openness_path = _raw_paths()
    return _build(read_json(providers_path), read_json(openness_path))


def _build(providers: dict[str, Any], openness: dict[str, Any]) -> dict[str, Any]:
    dataset = normalize_sources(providers, openness)
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
        "openness_rows": dataset.metadata.openness_row_count,
        "openness_matched": dataset.metadata.openness_matched,
        "openness_unmatched": dataset.metadata.openness_unmatched,
        "openness_ambiguous": dataset.metadata.openness_ambiguous,
        "match_tiers": dataset.metadata.match_tiers,
        "unreachable_provider_slugs": dataset.metadata.unreachable_provider_slugs,
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
    parser.error("unknown command")
