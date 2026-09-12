"""Tests for the optional SQLite read backend.

These tests build a minimal in-memory / on-disk SQLite fixture that matches
the v1 schema (ADR 0001) and verify:
- Single-model lookup parity with the JSON path
- search_models filter parity (provider / category / supports_vision / supports_function_calling)
- FTS search returns expected rows
- user_version validation rejects an incompatible DB
- A missing / broken DB causes get_all_pricing_data to raise SQLiteBackendError
  and pricing.fetch_pricing_data to fall back to JSON
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Schema DDL (matches build_db.py exactly)
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA user_version = 1;

CREATE TABLE meta (
  generated_at   TEXT NOT NULL,
  total_models   INTEGER NOT NULL,
  schema_version INTEGER NOT NULL
);

CREATE TABLE providers (
  provider      TEXT PRIMARY KEY,
  name          TEXT,
  website       TEXT,
  pricing_page  TEXT,
  affiliate_link TEXT
);

CREATE TABLE models (
  model_id      TEXT PRIMARY KEY,
  provider      TEXT NOT NULL REFERENCES providers(provider),
  display_name  TEXT NOT NULL,
  input_per_million          REAL,
  output_per_million         REAL,
  cache_read_per_million     REAL,
  cache_creation_per_million REAL,
  currency      TEXT NOT NULL DEFAULT 'USD',
  context_window    INTEGER,
  max_output_tokens INTEGER,
  model_type    TEXT,
  category      TEXT,
  supports_vision           INTEGER,
  supports_function_calling INTEGER,
  supports_streaming        INTEGER
);
CREATE INDEX idx_models_provider   ON models(provider);
CREATE INDEX idx_models_category   ON models(category);
CREATE INDEX idx_models_model_type ON models(model_type);

CREATE TABLE model_sources (
  model_id  TEXT NOT NULL REFERENCES models(model_id),
  source    TEXT NOT NULL,
  price_input          REAL,
  price_output         REAL,
  price_cache_read     REAL,
  price_cache_creation REAL,
  last_updated TEXT,
  PRIMARY KEY (model_id, source)
);

CREATE TABLE price_history (
  generated_at TEXT NOT NULL,
  model_id     TEXT NOT NULL,
  input_per_million          REAL,
  output_per_million         REAL,
  cache_read_per_million     REAL,
  cache_creation_per_million REAL,
  PRIMARY KEY (generated_at, model_id)
);
CREATE INDEX idx_history_model ON price_history(model_id, generated_at);

CREATE VIRTUAL TABLE models_fts USING fts5(
  model_id, display_name, content='models', content_rowid='rowid'
);
"""

# Fixture data mirrors tests/test_modeling.py's sample_pricing_data
_FIXTURE_PROVIDERS = [
    (
        "openai",
        "OpenAI",
        "https://openai.com",
        "https://openai.com/pricing",
        "https://platform.openai.com/signup",
    ),
    (
        "anthropic",
        "Anthropic",
        "https://anthropic.com",
        "https://anthropic.com/pricing",
        "https://console.anthropic.com/",
    ),
]

_FIXTURE_MODELS = [
    # (model_id, provider, display_name, input_per_million, output_per_million,
    #  cache_read_per_million, cache_creation_per_million, currency,
    #  context_window, max_output_tokens, model_type, category,
    #  supports_vision, supports_function_calling, supports_streaming)
    (
        "openai/gpt-4",
        "openai",
        "OpenAI: GPT-4",
        30.0,
        60.0,
        15.0,
        45.0,
        "USD",
        8192,
        4096,
        "text",
        "flagship",
        0,
        1,
        1,
    ),
    (
        "openai/gpt-4-vision",
        "openai",
        "OpenAI: GPT-4 Vision",
        30.0,
        60.0,
        None,
        None,
        "USD",
        128000,
        4096,
        "text",
        "flagship",
        1,
        1,
        1,
    ),
    (
        "anthropic/claude-3-opus",
        "anthropic",
        "Anthropic: Claude 3 Opus",
        15.0,
        75.0,
        None,
        None,
        "USD",
        200000,
        4096,
        "text",
        "flagship",
        1,
        1,
        1,
    ),
]

_FIXTURE_SOURCES = [
    # (model_id, source, price_input, price_output, price_cache_read, price_cache_creation, last_updated)
    ("openai/gpt-4", "openrouter", 30.0, 60.0, 15.0, 45.0, "2026-01-20T06:05:10+00:00"),
]

_GENERATED_AT = "2026-01-20T06:05:10+00:00"


def _build_fixture_db(path: Path) -> None:
    """Build a minimal v1-schema SQLite DB at *path* from the fixture data."""
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    try:
        con.executescript(_DDL)
        con.execute(
            "INSERT INTO meta (generated_at, total_models, schema_version) VALUES (?, ?, ?)",
            (_GENERATED_AT, len(_FIXTURE_MODELS), 1),
        )
        con.executemany(
            "INSERT INTO providers (provider, name, website, pricing_page, affiliate_link) VALUES (?, ?, ?, ?, ?)",
            _FIXTURE_PROVIDERS,
        )
        con.executemany(
            """INSERT INTO models (
              model_id, provider, display_name,
              input_per_million, output_per_million,
              cache_read_per_million, cache_creation_per_million,
              currency, context_window, max_output_tokens,
              model_type, category,
              supports_vision, supports_function_calling, supports_streaming
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            _FIXTURE_MODELS,
        )
        con.executemany(
            """INSERT INTO model_sources
              (model_id, source, price_input, price_output,
               price_cache_read, price_cache_creation, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            _FIXTURE_SOURCES,
        )
        # Populate FTS
        con.execute(
            "INSERT INTO models_fts (rowid, model_id, display_name) "
            "SELECT rowid, model_id, display_name FROM models"
        )
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    """Return path to a freshly-built v1 fixture DB."""
    db_path = tmp_path / "prices.db"
    _build_fixture_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ensure the SQLite env vars don't leak between tests."""
    monkeypatch.delenv("TOKENPRICING_USE_SQLITE", raising=False)
    monkeypatch.delenv("TOKENPRICING_DB_URL", raising=False)
    monkeypatch.delenv("TOKENPRICING_DB_CACHE_DIR", raising=False)
    yield


# ---------------------------------------------------------------------------
# Unit tests for sqlite_backend module
# ---------------------------------------------------------------------------


class TestSQLiteBackendLookup:
    """Single-model lookup via get_model()."""

    def test_get_model_returns_correct_model_info(self, fixture_db: Path, monkeypatch):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        model = sqlite_backend.get_model("openai/gpt-4")

        assert model.model_id == "openai/gpt-4"
        assert model.provider == "openai"
        assert model.display_name == "OpenAI: GPT-4"
        assert model.pricing.input_per_million == 30.0
        assert model.pricing.output_per_million == 60.0
        assert model.pricing.cache_read_per_million == 15.0
        assert model.pricing.cache_creation_per_million == 45.0
        assert model.pricing.currency == "USD"
        assert model.context_window == 8192
        assert model.max_output_tokens == 4096
        assert model.supports_vision is False
        assert model.supports_function_calling is True
        assert model.supports_streaming is True
        assert model.category == "flagship"

    def test_get_model_includes_sources(self, fixture_db: Path, monkeypatch):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        model = sqlite_backend.get_model("openai/gpt-4")
        assert "openrouter" in model.sources
        src = model.sources["openrouter"]
        assert src.price_input == 30.0
        assert src.price_output == 60.0

    def test_get_model_not_found_raises_key_error(self, fixture_db: Path, monkeypatch):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        with pytest.raises(KeyError):
            sqlite_backend.get_model("nonexistent/model")

    def test_get_model_vision_model(self, fixture_db: Path, monkeypatch):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        model = sqlite_backend.get_model("openai/gpt-4-vision")
        assert model.supports_vision is True
        assert model.pricing.cache_read_per_million is None


class TestSQLiteBackendSearch:
    """search_models filter parity."""

    def _search(self, fixture_db, monkeypatch, **kwargs):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)
        return sqlite_backend.search_models(**kwargs)

    def test_search_all_returns_all(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch)
        assert len(results) == 3

    def test_search_by_provider(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, provider="openai")
        assert len(results) == 2
        assert all(m.provider == "openai" for m in results)

    def test_search_by_provider_anthropic(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, provider="anthropic")
        assert len(results) == 1
        assert results[0].model_id == "anthropic/claude-3-opus"

    def test_search_by_category(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, category="flagship")
        assert len(results) == 3

    def test_search_by_category_no_match(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, category="budget")
        assert results == []

    def test_search_by_supports_vision_true(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, supports_vision=True)
        assert len(results) == 2
        assert all(m.supports_vision for m in results)

    def test_search_by_supports_vision_false(self, fixture_db: Path, monkeypatch):
        results = self._search(fixture_db, monkeypatch, supports_vision=False)
        assert len(results) == 1
        assert results[0].model_id == "openai/gpt-4"

    def test_search_by_supports_function_calling_true(
        self, fixture_db: Path, monkeypatch
    ):
        results = self._search(fixture_db, monkeypatch, supports_function_calling=True)
        assert len(results) == 3

    def test_search_combined_filters(self, fixture_db: Path, monkeypatch):
        results = self._search(
            fixture_db, monkeypatch, provider="openai", supports_vision=True
        )
        assert len(results) == 1
        assert results[0].model_id == "openai/gpt-4-vision"


class TestSQLiteBackendFTS:
    """FTS5 search via name_query parameter."""

    def _fts(self, fixture_db, monkeypatch, query):
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)
        return sqlite_backend.search_models(name_query=query)

    def test_fts_by_display_name_prefix(self, fixture_db: Path, monkeypatch):
        results = self._fts(fixture_db, monkeypatch, "GPT*")
        assert len(results) >= 1
        ids = [m.model_id for m in results]
        assert "openai/gpt-4" in ids

    def test_fts_by_model_id_prefix(self, fixture_db: Path, monkeypatch):
        results = self._fts(fixture_db, monkeypatch, "openai*")
        assert len(results) == 2

    def test_fts_anthropic_term(self, fixture_db: Path, monkeypatch):
        results = self._fts(fixture_db, monkeypatch, "Anthropic*")
        assert len(results) == 1
        assert results[0].model_id == "anthropic/claude-3-opus"

    def test_fts_no_match_returns_empty(self, fixture_db: Path, monkeypatch):
        results = self._fts(fixture_db, monkeypatch, "zzznomatch*")
        assert results == []


class TestSQLiteSchemaValidation:
    """user_version check and missing FTS."""

    def test_wrong_user_version_raises(self, tmp_path: Path, monkeypatch):
        from tokenpricing import sqlite_backend
        from tokenpricing.sqlite_backend import SQLiteBackendError

        bad_db = tmp_path / "bad.db"
        con = sqlite3.connect(str(bad_db))
        con.execute("PRAGMA user_version = 99")
        con.commit()
        con.close()

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: bad_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        with pytest.raises(SQLiteBackendError, match="schema version"):
            sqlite_backend.get_all_pricing_data()

    def test_missing_fts_table_raises(self, tmp_path: Path, monkeypatch):
        from tokenpricing import sqlite_backend
        from tokenpricing.sqlite_backend import SQLiteBackendError

        no_fts_db = tmp_path / "nofts.db"
        # Build DB without the FTS table
        con = sqlite3.connect(str(no_fts_db))
        con.executescript("""
            PRAGMA user_version = 1;
            CREATE TABLE meta (generated_at TEXT NOT NULL, total_models INTEGER NOT NULL, schema_version INTEGER NOT NULL);
            CREATE TABLE providers (provider TEXT PRIMARY KEY, name TEXT, website TEXT, pricing_page TEXT, affiliate_link TEXT);
            CREATE TABLE models (
              model_id TEXT PRIMARY KEY, provider TEXT NOT NULL, display_name TEXT NOT NULL,
              input_per_million REAL, output_per_million REAL,
              cache_read_per_million REAL, cache_creation_per_million REAL,
              currency TEXT NOT NULL DEFAULT 'USD', context_window INTEGER,
              max_output_tokens INTEGER, model_type TEXT, category TEXT,
              supports_vision INTEGER, supports_function_calling INTEGER, supports_streaming INTEGER
            );
        """)
        con.commit()
        con.close()

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: no_fts_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        with pytest.raises(SQLiteBackendError, match="models_fts"):
            sqlite_backend.get_all_pricing_data()

    def test_missing_db_raises(self, tmp_path: Path, monkeypatch):
        from tokenpricing import sqlite_backend
        from tokenpricing.sqlite_backend import SQLiteBackendError

        missing = tmp_path / "doesnotexist.db"

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: missing)
        # Not fresh → triggers download; mock download to raise
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: False)
        monkeypatch.setattr(
            sqlite_backend,
            "_download_db",
            lambda dest: (_ for _ in ()).throw(
                SQLiteBackendError("simulated download failure")
            ),
        )

        with pytest.raises(SQLiteBackendError):
            sqlite_backend.get_all_pricing_data()


class TestSQLiteGetAllPricingData:
    """Full dataset load via get_all_pricing_data()."""

    def test_returns_pricing_data_object(self, fixture_db: Path, monkeypatch):
        from tokenpricing import sqlite_backend
        from tokenpricing.modeling import PricingData

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        data = sqlite_backend.get_all_pricing_data()
        assert isinstance(data, PricingData)
        assert len(data.models) == 3
        assert "openai" in data.providers
        assert "anthropic" in data.providers

    def test_model_lookup_parity(self, fixture_db: Path, monkeypatch):
        """Verify SQLite data matches what the JSON path would return for sampled models."""
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        data = sqlite_backend.get_all_pricing_data()

        gpt4 = data.get_model("openai/gpt-4")
        assert gpt4 is not None
        assert gpt4.pricing.input_per_million == 30.0
        assert gpt4.pricing.output_per_million == 60.0
        assert gpt4.pricing.cache_read_per_million == 15.0

        claude = data.get_model("anthropic/claude-3-opus")
        assert claude is not None
        assert claude.pricing.input_per_million == 15.0
        assert claude.pricing.output_per_million == 75.0
        assert claude.supports_vision is True

    def test_search_models_parity(self, fixture_db: Path, monkeypatch):
        """Verify PricingData.search_models from SQLite yields same counts as JSON."""
        from tokenpricing import sqlite_backend

        monkeypatch.setattr(sqlite_backend, "_db_path", lambda: fixture_db)
        monkeypatch.setattr(sqlite_backend, "_is_fresh", lambda p: True)

        data = sqlite_backend.get_all_pricing_data()

        assert len(data.search_models()) == 3
        assert len(data.search_models(provider="openai")) == 2
        assert len(data.search_models(provider="anthropic")) == 1
        assert len(data.search_models(category="flagship")) == 3
        assert len(data.search_models(supports_vision=True)) == 2
        assert len(data.search_models(supports_vision=False)) == 1
        assert len(data.search_models(provider="openai", supports_vision=True)) == 1


# ---------------------------------------------------------------------------
# Integration: pricing.fetch_pricing_data fallback
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    """When SQLite backend fails, fetch_pricing_data falls back to JSON."""

    _SAMPLE_JSON = {
        "generated_at": "2026-01-20T06:05:10.791612+00:00",
        "models": {
            "openai/gpt-4": {
                "provider": "openai",
                "model_id": "openai/gpt-4",
                "display_name": "OpenAI: GPT-4",
                "pricing": {
                    "input_per_million": 30.0,
                    "output_per_million": 60.0,
                    "cache_read_per_million": 15.0,
                    "cache_creation_per_million": 45.0,
                    "currency": "USD",
                },
                "context_window": 8192,
                "max_output_tokens": 4096,
                "model_type": "text",
                "supports_vision": False,
                "supports_function_calling": True,
                "supports_streaming": True,
                "category": "flagship",
            }
        },
        "providers": {
            "openai": {
                "name": "OpenAI",
                "website": "https://openai.com",
                "pricing_page": "https://openai.com/pricing",
                "affiliate_link": "https://platform.openai.com/signup",
            }
        },
        "metadata": {
            "total_models": 1,
            "sources": ["openrouter"],
            "last_scrape": "2026-01-20T06:05:10.791612+00:00",
            "categories": {"flagship": 1},
        },
    }

    @pytest.mark.asyncio
    async def test_sqlite_failure_falls_back_to_json(self, monkeypatch):
        """When SQLite raises, fetch_pricing_data transparently uses JSON."""
        import tokenpricing.pricing as pricing_mod
        from tokenpricing.sqlite_backend import SQLiteBackendError

        pricing_mod._get_pricing_data_bucketed.cache_clear()

        # Enable SQLite env var
        monkeypatch.setenv("TOKENPRICING_USE_SQLITE", "1")

        # Patch sqlite backend to always fail
        async def _broken_thread(*args, **kwargs):
            raise SQLiteBackendError("simulated failure")

        with patch("asyncio.to_thread", side_effect=SQLiteBackendError("fail")):
            from unittest.mock import Mock

            mock_response = Mock()
            mock_response.json.return_value = self._SAMPLE_JSON

            with patch("httpx.AsyncClient.get", return_value=mock_response):
                data = await pricing_mod.fetch_pricing_data()

        assert data.get_model("openai/gpt-4") is not None
        pricing_mod._get_pricing_data_bucketed.cache_clear()

    @pytest.mark.asyncio
    async def test_sqlite_off_by_default(self, monkeypatch):
        """Without TOKENPRICING_USE_SQLITE, JSON path is always used."""
        import tokenpricing.pricing as pricing_mod

        pricing_mod._get_pricing_data_bucketed.cache_clear()
        # Env var is removed by _isolate_env autouse fixture

        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.json.return_value = self._SAMPLE_JSON

        # If SQLite were tried and there's no DB, it would fail; but since it's
        # off, it should succeed purely via JSON.
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            data = await pricing_mod.fetch_pricing_data()

        assert data.get_model("openai/gpt-4") is not None
        pricing_mod._get_pricing_data_bucketed.cache_clear()

    def test_sqlite_disabled_flag_variations(self, monkeypatch):
        """Various falsy env var values should leave SQLite disabled."""
        import tokenpricing.pricing as pricing_mod

        for val in ("0", "false", "no", "", "False", "NO"):
            monkeypatch.setenv("TOKENPRICING_USE_SQLITE", val)
            assert not pricing_mod._sqlite_enabled(), f"Expected disabled for {val!r}"

        monkeypatch.setenv("TOKENPRICING_USE_SQLITE", "1")
        assert pricing_mod._sqlite_enabled()

        monkeypatch.setenv("TOKENPRICING_USE_SQLITE", "true")
        assert pricing_mod._sqlite_enabled()
