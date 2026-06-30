from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tokenpricing.modeling import PricingData

from tokenpricing_sync.build_db import build_both_dbs
from tokenpricing_sync.diff import compare_datasets
from tokenpricing_sync.fetch import fetch_litellm, fetch_openrouter
from tokenpricing_sync.history import write_compact_history
from tokenpricing_sync.normalize import normalize_sources
from tokenpricing_sync.paths import CHANGELOG_DIR, CURRENT_DATABASE_DIR, HISTORY_DIR


def ensure_directories() -> None:
    CURRENT_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_previous_dataset() -> PricingData | None:
    current_path = CURRENT_DATABASE_DIR / "prices.json"
    if not current_path.exists():
        return None
    return PricingData.model_validate(read_json(current_path))


def sync() -> dict[str, Any]:
    ensure_directories()
    openrouter = fetch_openrouter()
    litellm = fetch_litellm()
    previous = load_previous_dataset()
    dataset = normalize_sources(openrouter, litellm)
    changelog = compare_datasets(previous, dataset)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_json(CURRENT_DATABASE_DIR / "openrouter.json", openrouter)
    write_json(CURRENT_DATABASE_DIR / "litellm.json", litellm)
    write_json(CURRENT_DATABASE_DIR / "prices.json", dataset.model_dump(mode="json"))
    write_json(
        HISTORY_DIR / f"prices-{timestamp}.json", dataset.model_dump(mode="json")
    )
    write_json(CHANGELOG_DIR / "latest.json", changelog)
    compact_history_path = write_compact_history(
        history_dir=HISTORY_DIR,
        output_path=CURRENT_DATABASE_DIR / "price-history.json",
        write_json_fn=write_json,
    )
    full_db_path, slim_db_path = build_both_dbs()
    return {
        "snapshot": str(CURRENT_DATABASE_DIR / "prices.json"),
        "history_snapshot": str(HISTORY_DIR / f"prices-{timestamp}.json"),
        "compact_history": str(compact_history_path),
        "changelog": str(CHANGELOG_DIR / "latest.json"),
        "database": str(full_db_path),
        "database_slim": str(slim_db_path),
        "models": dataset.metadata.total_models,
        "summary": changelog["summary"],
    }


def normalize_only() -> dict[str, Any]:
    ensure_directories()
    openrouter = read_json(CURRENT_DATABASE_DIR / "openrouter.json")
    litellm = read_json(CURRENT_DATABASE_DIR / "litellm.json")
    previous = load_previous_dataset()
    dataset = normalize_sources(openrouter, litellm)
    changelog = compare_datasets(previous, dataset)
    write_json(CURRENT_DATABASE_DIR / "prices.json", dataset.model_dump(mode="json"))
    write_json(CHANGELOG_DIR / "latest.json", changelog)
    return {"models": dataset.metadata.total_models, "summary": changelog["summary"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tokenpricing canonical database sync")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "sync", help="fetch sources and regenerate the canonical database"
    )
    subparsers.add_parser(
        "normalize",
        help="regenerate the canonical database from local raw source files",
    )
    build_db_parser = subparsers.add_parser(
        "build-db",
        help="build prices.db from the current on-disk JSON files",
    )
    build_db_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="destination path for the SQLite file (default: database/current/prices.db)",
    )
    build_db_parser.add_argument(
        "--prices-json",
        type=Path,
        default=None,
        dest="prices_json",
        help="path to prices.json (default: database/current/prices.json)",
    )
    build_db_parser.add_argument(
        "--history-dir",
        type=Path,
        default=None,
        dest="history_dir",
        help="directory containing timestamped history snapshots (default: database/history)",
    )
    build_db_parser.add_argument(
        "--slim-output",
        type=Path,
        default=None,
        dest="slim_output",
        help="destination path for the slim SQLite file without price_history (default: database/current/prices-current.db)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "sync":
        print(json.dumps(sync(), indent=2))
        return
    if args.command == "normalize":
        print(json.dumps(normalize_only(), indent=2))
        return
    if args.command == "build-db":
        full_db_path, slim_db_path = build_both_dbs(
            prices_json=args.prices_json,
            history_dir=args.history_dir,
            full_output=args.output,
            slim_output=args.slim_output,
        )
        print(
            json.dumps(
                {"database": str(full_db_path), "database_slim": str(slim_db_path)},
                indent=2,
            )
        )
        return
    parser.error("unknown command")
