"""Build a SQLite database from the canonical pricing JSON files.

The schema follows ADR 0001. Prices are stored as REAL. The database is
derived from the JSON source of truth — never committed to git.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tokenpricing_sync.paths import CURRENT_DATABASE_DIR, HISTORY_DIR

SCHEMA_VERSION = 1

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


def _populate_from_snapshot(
    con: sqlite3.Connection,
    snapshot: dict[str, Any],
    *,
    include_models: bool = True,
    include_providers: bool = True,
) -> None:
    """Insert models/providers from a single snapshot dict into an open connection.

    When *include_models* is False only providers are inserted (used when
    loading history-only snapshots so we don't duplicate model rows).
    """
    providers = snapshot.get("providers") or {}
    models_data = snapshot.get("models") or {}

    if include_providers:
        for provider_id, pinfo in providers.items():
            con.execute(
                """
                INSERT OR IGNORE INTO providers
                  (provider, name, website, pricing_page, affiliate_link)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    pinfo.get("name"),
                    pinfo.get("website") or "",
                    pinfo.get("pricing_page") or "",
                    pinfo.get("affiliate_link"),
                ),
            )

    if include_models:
        for model_id, m in models_data.items():
            pricing = m.get("pricing") or {}
            con.execute(
                """
                INSERT OR IGNORE INTO models (
                  model_id, provider, display_name,
                  input_per_million, output_per_million,
                  cache_read_per_million, cache_creation_per_million,
                  currency, context_window, max_output_tokens,
                  model_type, category,
                  supports_vision, supports_function_calling, supports_streaming
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id,
                    m.get("provider", "unknown"),
                    m.get("display_name", model_id),
                    pricing.get("input_per_million"),
                    pricing.get("output_per_million"),
                    pricing.get("cache_read_per_million"),
                    pricing.get("cache_creation_per_million"),
                    pricing.get("currency") or "USD",
                    m.get("context_window"),
                    m.get("max_output_tokens"),
                    m.get("model_type"),
                    m.get("category"),
                    1 if m.get("supports_vision") else 0,
                    1 if m.get("supports_function_calling") else 0,
                    1 if m.get("supports_streaming") else 0,
                ),
            )

            for source_name, src in (m.get("sources") or {}).items():
                con.execute(
                    """
                    INSERT OR IGNORE INTO model_sources
                      (model_id, source, price_input, price_output,
                       price_cache_read, price_cache_creation, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        source_name,
                        src.get("price_input"),
                        src.get("price_output"),
                        src.get("price_cache_read"),
                        src.get("price_cache_creation"),
                        src.get("last_updated"),
                    ),
                )


def _load_history_snapshots(
    con: sqlite3.Connection,
    history_dir: Path,
) -> None:
    """Load all timestamped history snapshots into price_history."""
    history_files = sorted(history_dir.glob("prices-*.json"))
    for hist_path in history_files:
        try:
            snap = json.loads(hist_path.read_text())
        except Exception:
            continue
        generated_at = snap.get("generated_at")
        if not generated_at:
            continue
        models_data = snap.get("models") or {}
        rows = []
        for model_id, m in models_data.items():
            pricing = m.get("pricing") or {}
            rows.append(
                (
                    generated_at,
                    model_id,
                    pricing.get("input_per_million"),
                    pricing.get("output_per_million"),
                    pricing.get("cache_read_per_million"),
                    pricing.get("cache_creation_per_million"),
                )
            )
        if rows:
            con.executemany(
                """
                INSERT OR IGNORE INTO price_history
                  (generated_at, model_id,
                   input_per_million, output_per_million,
                   cache_read_per_million, cache_creation_per_million)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )


def build_db(
    prices_json: Path | None = None,
    history_dir: Path | None = None,
    output: Path | None = None,
) -> Path:
    """Build (or rebuild) a SQLite prices.db from canonical JSON files.

    Args:
        prices_json: Path to the canonical prices.json.  Defaults to
            ``database/current/prices.json`` relative to the repo root.
        history_dir: Directory containing timestamped ``prices-*.json``
            history snapshots.  Defaults to ``database/history``.
        output: Destination path for the SQLite file.  Defaults to
            ``database/current/prices.db``.

    Returns:
        The resolved path to the written database file.
    """
    if prices_json is None:
        prices_json = CURRENT_DATABASE_DIR / "prices.json"
    if history_dir is None:
        history_dir = HISTORY_DIR
    if output is None:
        output = CURRENT_DATABASE_DIR / "prices.db"

    snapshot: dict[str, Any] = json.loads(prices_json.read_text())
    generated_at: str = snapshot.get("generated_at") or datetime.now(
        timezone.utc
    ).isoformat()
    metadata = snapshot.get("metadata") or {}
    total_models: int = metadata.get("total_models") or len(snapshot.get("models") or {})

    # Remove stale DB so we always start from a clean slate.
    if output.exists():
        output.unlink()

    con = sqlite3.connect(str(output))
    try:
        con.executescript(_DDL)
        con.execute(
            "INSERT INTO meta (generated_at, total_models, schema_version) VALUES (?, ?, ?)",
            (generated_at, total_models, SCHEMA_VERSION),
        )
        _populate_from_snapshot(con, snapshot, include_models=True, include_providers=True)
        _load_history_snapshots(con, history_dir)

        # Populate the FTS index from the models table.
        con.execute(
            "INSERT INTO models_fts (rowid, model_id, display_name) "
            "SELECT rowid, model_id, display_name FROM models"
        )

        con.commit()
        # Compact and build query stats.
        con.execute("VACUUM")
        con.execute("ANALYZE")
        con.commit()
    finally:
        con.close()

    return output
