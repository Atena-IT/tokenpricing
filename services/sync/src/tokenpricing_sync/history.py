"""Compact per-model price time-series artifact.

Reads all retained ``database/history/prices-*.json`` snapshots and emits a
single ``database/current/price-history.json`` containing only the pricing
fields needed for the dashboard history charts.

Output shape::

    {
        "generated_at": "<ISO-8601>",
        "models": {
            "openai/gpt-4o": [
                {"t": "2026-06-17T01:28:28Z", "in": 5.0, "out": 15.0, "cr": 2.5, "cc": null}
            ]
        }
    }

Keys per point:
    t   snapshot ISO timestamp (from filename or ``generated_at``)
    in  ``input_per_million`` (USD / 1 M tokens)
    out ``output_per_million``
    cr  ``cache_read_per_million`` or null
    cc  ``cache_creation_per_million`` or null

Points are sorted in ascending chronological order.  Models that never appear
in any snapshot are omitted from the output.
"""

from __future__ import annotations

import json
import re
from datetime import timezone
from pathlib import Path
from typing import Any

# Matches filenames like prices-20260617T012828Z.json
_SNAPSHOT_FILENAME_RE = re.compile(
    r"prices-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z\.json$"
)


def _timestamp_from_path(path: Path, snapshot: dict[str, Any]) -> str:
    """Return an ISO-8601 UTC timestamp for a snapshot.

    Prefers the filename (deterministic and stable across re-parses); falls
    back to the ``generated_at`` field in the snapshot body.
    """
    match = _SNAPSHOT_FILENAME_RE.search(path.name)
    if match:
        year, month, day, hour, minute, second = match.groups()
        return f"{year}-{month}-{day}T{hour}:{minute}:{second}Z"
    generated_at: str = snapshot.get("generated_at", "")
    if generated_at:
        return generated_at
    raise ValueError(f"Cannot determine timestamp for snapshot {path}")


def build_compact_history(
    history_dir: Path,
) -> dict[str, Any]:
    """Read all snapshots in *history_dir* and build the compact time-series.

    Parameters
    ----------
    history_dir:
        Directory that contains ``prices-<timestamp>.json`` files.

    Returns
    -------
    dict
        The compact history payload ready to be serialised to JSON.
    """
    from datetime import datetime

    snapshots: list[tuple[str, dict[str, Any]]] = []

    for path in sorted(history_dir.glob("prices-*.json")):
        try:
            snapshot = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        timestamp = _timestamp_from_path(path, snapshot)
        snapshots.append((timestamp, snapshot))

    # Sort chronologically — the glob is sorted lexicographically which
    # happens to match timestamp order for this filename convention, but sort
    # explicitly for correctness.
    snapshots.sort(key=lambda pair: pair[0])

    models: dict[str, list[dict[str, Any]]] = {}

    for timestamp, snapshot in snapshots:
        raw_models: dict[str, Any] = snapshot.get("models", {})
        for model_id, model_data in raw_models.items():
            pricing = model_data.get("pricing", {})
            point: dict[str, Any] = {
                "t": timestamp,
                "in": pricing.get("input_per_million"),
                "out": pricing.get("output_per_million"),
                "cr": pricing.get("cache_read_per_million"),
                "cc": pricing.get("cache_creation_per_million"),
            }
            models.setdefault(model_id, []).append(point)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "generated_at": generated_at,
        "models": models,
    }


def write_compact_history(
    history_dir: Path,
    output_path: Path,
    write_json_fn: Any,
) -> Path:
    """Build and write the compact history artifact.

    Parameters
    ----------
    history_dir:
        Source directory of ``prices-<timestamp>.json`` snapshots.
    output_path:
        Destination path for ``price-history.json``.
    write_json_fn:
        The ``write_json`` helper from ``cli`` (handles indent + trailing
        newline consistently).

    Returns
    -------
    Path
        The path written.
    """
    payload = build_compact_history(history_dir)
    write_json_fn(output_path, payload)
    return output_path
