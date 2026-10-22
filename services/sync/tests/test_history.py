"""Tests for the compact history artifact (history.py).

Verifies that ``build_compact_history`` correctly:
- aggregates per-model price points across multiple snapshots
- preserves ascending chronological order
- handles null cache fields
- includes a model that appears in only one snapshot
- omits models absent from all snapshots (i.e. no empty lists)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tokenpricing_sync.history import build_compact_history

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

SNAPSHOT_A_NAME = "prices-20260617T010000Z.json"
SNAPSHOT_B_NAME = "prices-20260618T010000Z.json"

SNAPSHOT_A: dict = {
    "generated_at": "2026-06-17T01:00:00Z",
    "models": {
        "openai/gpt-4o": {
            "pricing": {
                "input_per_million": 5.0,
                "output_per_million": 15.0,
                "cache_read_per_million": 2.5,
                "cache_creation_per_million": None,
            }
        },
        "anthropic/claude-haiku-3-5": {
            "pricing": {
                "input_per_million": 0.8,
                "output_per_million": 4.0,
                "cache_read_per_million": 0.08,
                "cache_creation_per_million": 1.0,
            }
        },
    },
}

SNAPSHOT_B: dict = {
    "generated_at": "2026-06-18T01:00:00Z",
    "models": {
        "openai/gpt-4o": {
            "pricing": {
                "input_per_million": 4.0,
                "output_per_million": 12.0,
                "cache_read_per_million": None,
                "cache_creation_per_million": None,
            }
        },
        # anthropic/claude-haiku-3-5 is NOT in this snapshot — tests single-point
        "openai/gpt-4o-mini": {
            "pricing": {
                "input_per_million": 0.15,
                "output_per_million": 0.6,
                "cache_read_per_million": None,
                "cache_creation_per_million": None,
            }
        },
    },
}


@pytest.fixture()
def history_dir(tmp_path: Path) -> Path:
    """Write two fixture snapshots to a temp directory."""
    (tmp_path / SNAPSHOT_A_NAME).write_text(json.dumps(SNAPSHOT_A))
    (tmp_path / SNAPSHOT_B_NAME).write_text(json.dumps(SNAPSHOT_B))
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_output_has_generated_at(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    assert "generated_at" in result
    assert result["generated_at"]  # non-empty string


def test_output_has_models_key(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    assert "models" in result


def test_gpt4o_has_two_points(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    points = result["models"]["openai/gpt-4o"]
    assert len(points) == 2


def test_points_are_sorted_ascending(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    points = result["models"]["openai/gpt-4o"]
    timestamps = [p["t"] for p in points]
    assert timestamps == sorted(timestamps)


def test_first_point_timestamp_from_filename(history_dir: Path) -> None:
    """Timestamp is derived from the filename, not generated_at."""
    result = build_compact_history(history_dir)
    points = result["models"]["openai/gpt-4o"]
    # Snapshot A filename → 2026-06-17T01:00:00Z
    assert points[0]["t"] == "2026-06-17T01:00:00Z"


def test_price_fields_correct(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    point = result["models"]["openai/gpt-4o"][0]
    assert point["in"] == pytest.approx(5.0)
    assert point["out"] == pytest.approx(15.0)
    assert point["cr"] == pytest.approx(2.5)
    assert point["cc"] is None


def test_null_cache_fields_preserved(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    # Second point for gpt-4o has both cache fields null
    point = result["models"]["openai/gpt-4o"][1]
    assert point["cr"] is None
    assert point["cc"] is None


def test_cache_creation_populated_when_present(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    point = result["models"]["anthropic/claude-haiku-3-5"][0]
    assert point["cc"] == pytest.approx(1.0)


def test_model_in_only_one_snapshot_has_one_point(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    # gpt-4o-mini only appears in snapshot B
    points = result["models"]["openai/gpt-4o-mini"]
    assert len(points) == 1
    assert points[0]["t"] == "2026-06-18T01:00:00Z"


def test_model_absent_from_all_snapshots_not_present(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    assert "nonexistent/model" not in result["models"]


def test_empty_history_dir(tmp_path: Path) -> None:
    result = build_compact_history(tmp_path)
    assert result["models"] == {}


def test_haiku_appears_only_in_first_snapshot(history_dir: Path) -> None:
    result = build_compact_history(history_dir)
    points = result["models"]["anthropic/claude-haiku-3-5"]
    assert len(points) == 1
    assert points[0]["in"] == pytest.approx(0.8)
    assert points[0]["out"] == pytest.approx(4.0)
