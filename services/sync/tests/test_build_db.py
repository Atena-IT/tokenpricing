"""JSON <-> SQLite equivalence tests for build_db.

These tests build an in-memory SQLite database from a small fixture and
verify that:
  - model count matches the fixture
  - sampled models have matching prices and fields
  - FTS search returns expected rows
  - PRAGMA user_version is set to the expected schema version
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tokenpricing_sync.build_db import SCHEMA_VERSION, build_db, build_both_dbs

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

FIXTURE_PRICES: dict = {
    "generated_at": "2026-06-27T00:00:00+00:00",
    "models": {
        "openai/gpt-4o": {
            "provider": "openai",
            "model_id": "openai/gpt-4o",
            "display_name": "GPT-4o",
            "pricing": {
                "input_per_million": 5.0,
                "output_per_million": 15.0,
                "cache_read_per_million": 2.5,
                "cache_creation_per_million": None,
                "currency": "USD",
            },
            "context_window": 128000,
            "max_output_tokens": 16384,
            "model_type": "text",
            "supports_vision": True,
            "supports_function_calling": True,
            "supports_streaming": True,
            "category": "flagship",
            "sources": {
                "openrouter": {
                    "price_input": 5.0,
                    "price_output": 15.0,
                    "price_cache_read": 2.5,
                    "price_cache_creation": None,
                    "last_updated": "2026-06-27T00:00:00+00:00",
                }
            },
            "affiliate_links": {},
        },
        "anthropic/claude-haiku-3-5": {
            "provider": "anthropic",
            "model_id": "anthropic/claude-haiku-3-5",
            "display_name": "Claude Haiku 3.5",
            "pricing": {
                "input_per_million": 0.8,
                "output_per_million": 4.0,
                "cache_read_per_million": 0.08,
                "cache_creation_per_million": 1.0,
                "currency": "USD",
            },
            "context_window": 200000,
            "max_output_tokens": 8192,
            "model_type": "text",
            "supports_vision": True,
            "supports_function_calling": True,
            "supports_streaming": True,
            "category": "budget",
            "sources": {
                "litellm": {
                    "price_input": 0.8,
                    "price_output": 4.0,
                    "price_cache_read": 0.08,
                    "price_cache_creation": 1.0,
                    "last_updated": "2026-06-27T00:00:00+00:00",
                }
            },
            "affiliate_links": {},
        },
    },
    "providers": {
        "openai": {
            "name": "OpenAI",
            "website": "https://openai.com",
            "pricing_page": "https://openai.com/pricing",
            "affiliate_link": None,
        },
        "anthropic": {
            "name": "Anthropic",
            "website": "https://anthropic.com",
            "pricing_page": "https://www.anthropic.com/pricing",
            "affiliate_link": None,
        },
    },
    "metadata": {
        "total_models": 2,
        "sources": ["openrouter", "litellm"],
        "last_scrape": "2026-06-27T00:00:00+00:00",
        "categories": {"flagship": 1, "budget": 1},
    },
}

FIXTURE_HISTORY: dict = {
    "generated_at": "2026-06-26T00:00:00+00:00",
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
    "providers": {},
    "metadata": {
        "total_models": 2,
        "sources": ["openrouter", "litellm"],
        "last_scrape": "2026-06-26T00:00:00+00:00",
        "categories": {},
    },
}


@pytest.fixture()
def fixture_db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    """Write fixture JSON to tmp_path, build the DB, return (db_path, connection)."""
    prices_json = tmp_path / "prices.json"
    prices_json.write_text(json.dumps(FIXTURE_PRICES))

    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "prices-20260626T000000Z.json").write_text(
        json.dumps(FIXTURE_HISTORY)
    )

    db_path = tmp_path / "prices.db"
    built = build_db(
        prices_json=prices_json,
        history_dir=history_dir,
        output=db_path,
    )
    con = sqlite3.connect(str(built))
    con.row_factory = sqlite3.Row
    yield built, con
    con.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_schema_version(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    version = con.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_model_count_matches(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    count = con.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    assert count == len(FIXTURE_PRICES["models"])


def test_meta_row(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    row = con.execute("SELECT * FROM meta").fetchone()
    assert row is not None
    assert row["total_models"] == FIXTURE_PRICES["metadata"]["total_models"]
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["generated_at"] == FIXTURE_PRICES["generated_at"]


def test_gpt4o_fields_match(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    row = con.execute(
        "SELECT * FROM models WHERE model_id = ?", ("openai/gpt-4o",)
    ).fetchone()
    assert row is not None

    fixture = FIXTURE_PRICES["models"]["openai/gpt-4o"]
    pricing = fixture["pricing"]

    assert row["provider"] == fixture["provider"]
    assert row["display_name"] == fixture["display_name"]
    assert row["input_per_million"] == pytest.approx(pricing["input_per_million"])
    assert row["output_per_million"] == pytest.approx(pricing["output_per_million"])
    assert row["cache_read_per_million"] == pytest.approx(
        pricing["cache_read_per_million"]
    )
    assert row["cache_creation_per_million"] is None
    assert row["currency"] == pricing["currency"]
    assert row["context_window"] == fixture["context_window"]
    assert row["max_output_tokens"] == fixture["max_output_tokens"]
    assert row["model_type"] == fixture["model_type"]
    assert row["category"] == fixture["category"]
    assert bool(row["supports_vision"]) is fixture["supports_vision"]
    assert (
        bool(row["supports_function_calling"]) is fixture["supports_function_calling"]
    )
    assert bool(row["supports_streaming"]) is fixture["supports_streaming"]


def test_haiku_cache_creation_field(
    fixture_db: tuple[Path, sqlite3.Connection],
) -> None:
    _, con = fixture_db
    row = con.execute(
        "SELECT cache_creation_per_million FROM models WHERE model_id = ?",
        ("anthropic/claude-haiku-3-5",),
    ).fetchone()
    assert row is not None
    assert row["cache_creation_per_million"] == pytest.approx(1.0)


def test_model_sources_populated(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    rows = con.execute(
        "SELECT * FROM model_sources WHERE model_id = ?", ("openai/gpt-4o",)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["source"] == "openrouter"
    assert rows[0]["price_input"] == pytest.approx(5.0)


def test_providers_populated(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    providers = {
        r["provider"] for r in con.execute("SELECT provider FROM providers").fetchall()
    }
    assert "openai" in providers
    assert "anthropic" in providers


def test_price_history_populated(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    count = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    # Two models in the history snapshot
    assert count == 2

    row = con.execute(
        "SELECT * FROM price_history WHERE model_id = ? AND generated_at = ?",
        ("openai/gpt-4o", "2026-06-26T00:00:00+00:00"),
    ).fetchone()
    assert row is not None
    assert row["input_per_million"] == pytest.approx(5.0)


def test_fts_search_returns_model(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    # FTS5 tokenises on punctuation/hyphens, so search on a whole word in the
    # display_name ("GPT") rather than a hyphenated token ("GPT-4o").
    rows = con.execute(
        "SELECT model_id FROM models_fts WHERE models_fts MATCH ?", ("GPT*",)
    ).fetchall()
    model_ids = [r["model_id"] for r in rows]
    assert "openai/gpt-4o" in model_ids


def test_fts_search_by_model_id(fixture_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_db
    rows = con.execute(
        "SELECT model_id FROM models_fts WHERE models_fts MATCH ?", ("haiku",)
    ).fetchall()
    model_ids = [r["model_id"] for r in rows]
    assert "anthropic/claude-haiku-3-5" in model_ids


def test_db_not_created_if_prices_json_missing(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        build_db(
            prices_json=tmp_path / "nonexistent.json",
            history_dir=tmp_path / "history",
            output=tmp_path / "prices.db",
        )


# ---------------------------------------------------------------------------
# Slim database tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_slim_db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    """Write fixture JSON to tmp_path, build the slim DB, return (db_path, connection)."""
    prices_json = tmp_path / "prices.json"
    prices_json.write_text(json.dumps(FIXTURE_PRICES))

    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "prices-20260626T000000Z.json").write_text(
        json.dumps(FIXTURE_HISTORY)
    )

    db_path = tmp_path / "prices-current.db"
    built = build_db(
        prices_json=prices_json,
        history_dir=history_dir,
        output=db_path,
        with_history=False,
    )
    con = sqlite3.connect(str(built))
    con.row_factory = sqlite3.Row
    yield built, con
    con.close()


def test_slim_schema_version(fixture_slim_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_slim_db
    version = con.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_slim_has_models(fixture_slim_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_slim_db
    count = con.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    assert count == len(FIXTURE_PRICES["models"])


def test_slim_has_providers(fixture_slim_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_slim_db
    providers = {
        r["provider"] for r in con.execute("SELECT provider FROM providers").fetchall()
    }
    assert "openai" in providers
    assert "anthropic" in providers


def test_slim_has_model_sources(
    fixture_slim_db: tuple[Path, sqlite3.Connection],
) -> None:
    _, con = fixture_slim_db
    rows = con.execute("SELECT * FROM model_sources").fetchall()
    assert len(rows) > 0


def test_slim_has_fts(fixture_slim_db: tuple[Path, sqlite3.Connection]) -> None:
    _, con = fixture_slim_db
    rows = con.execute(
        "SELECT model_id FROM models_fts WHERE models_fts MATCH ?", ("GPT*",)
    ).fetchall()
    assert any(r["model_id"] == "openai/gpt-4o" for r in rows)


def test_slim_no_price_history(
    fixture_slim_db: tuple[Path, sqlite3.Connection],
) -> None:
    """Slim DB must NOT contain the price_history table."""
    _, con = fixture_slim_db
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'"
    ).fetchone()
    assert row is None, "price_history table must not exist in the slim database"


def test_full_db_still_has_price_history(
    fixture_db: tuple[Path, sqlite3.Connection],
) -> None:
    """Full DB must still contain price_history with the expected rows."""
    _, con = fixture_db
    count = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    assert count == 2


def test_build_both_dbs(tmp_path: Path) -> None:
    """build_both_dbs produces both a full and a slim database."""
    prices_json = tmp_path / "prices.json"
    prices_json.write_text(json.dumps(FIXTURE_PRICES))

    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "prices-20260626T000000Z.json").write_text(
        json.dumps(FIXTURE_HISTORY)
    )

    full_output = tmp_path / "prices.db"
    slim_output = tmp_path / "prices-current.db"

    full_path, slim_path = build_both_dbs(
        prices_json=prices_json,
        history_dir=history_dir,
        full_output=full_output,
        slim_output=slim_output,
    )

    assert full_path.exists()
    assert slim_path.exists()

    # Full DB has price_history; slim does not.
    with sqlite3.connect(str(full_path)) as full_con:
        row = full_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'"
        ).fetchone()
        assert row is not None, "Full DB must have price_history"

    with sqlite3.connect(str(slim_path)) as slim_con:
        row = slim_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'"
        ).fetchone()
        assert row is None, "Slim DB must not have price_history"

    # Slim DB is smaller than the full DB (it has no history rows).
    assert slim_path.stat().st_size < full_path.stat().st_size
