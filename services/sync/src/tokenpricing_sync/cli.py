from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tokenpricing.modeling import PricingData

from tokenpricing_sync.diff import compare_datasets
from tokenpricing_sync.fetch import fetch_litellm, fetch_openrouter
from tokenpricing_sync.normalize import normalize_sources
from tokenpricing_sync.paths import CHANGELOG_DIR, CURRENT_DATA_DIR, HISTORY_DIR


def ensure_directories() -> None:
    CURRENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_previous_dataset() -> PricingData | None:
    current_path = CURRENT_DATA_DIR / "prices.json"
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
    write_json(CURRENT_DATA_DIR / "openrouter.json", openrouter)
    write_json(CURRENT_DATA_DIR / "litellm.json", litellm)
    write_json(CURRENT_DATA_DIR / "prices.json", dataset.model_dump(mode="json"))
    write_json(
        HISTORY_DIR / f"prices-{timestamp}.json", dataset.model_dump(mode="json")
    )
    write_json(CHANGELOG_DIR / "latest.json", changelog)
    return {
        "snapshot": str(CURRENT_DATA_DIR / "prices.json"),
        "history_snapshot": str(HISTORY_DIR / f"prices-{timestamp}.json"),
        "changelog": str(CHANGELOG_DIR / "latest.json"),
        "models": dataset.metadata.total_models,
        "summary": changelog["summary"],
    }


def normalize_only() -> dict[str, Any]:
    ensure_directories()
    openrouter = read_json(CURRENT_DATA_DIR / "openrouter.json")
    litellm = read_json(CURRENT_DATA_DIR / "litellm.json")
    previous = load_previous_dataset()
    dataset = normalize_sources(openrouter, litellm)
    changelog = compare_datasets(previous, dataset)
    write_json(CURRENT_DATA_DIR / "prices.json", dataset.model_dump(mode="json"))
    write_json(CHANGELOG_DIR / "latest.json", changelog)
    return {"models": dataset.metadata.total_models, "summary": changelog["summary"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tokenpricing canonical database sync")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "sync", help="fetch sources and regenerate the canonical dataset"
    )
    subparsers.add_parser(
        "normalize", help="regenerate the canonical dataset from local raw source files"
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
    parser.error("unknown command")
