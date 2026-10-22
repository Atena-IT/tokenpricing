"""Optional SQLite read backend for tokenpricing.

Downloads ``prices-current.db`` (the slim database, without ``price_history``)
from a configurable URL (default: rolling GitHub Release at
``database-latest``), caches it on disk with a 6-hour freshness TTL, and
serves lookups / searches via indexed SQL instead of parsing the full ~2.9 MB
JSON.

The SDK never queries ``price_history``, so the slim database is a drop-in
replacement for the full ``prices.db``.  Using it results in a materially
smaller download on first use.  To switch to the full database set
``TOKENPRICING_DB_URL`` to the ``prices.db`` release URL.

Activation
----------
Set the environment variable ``TOKENPRICING_USE_SQLITE=1`` before importing.
When OFF (default) the existing HTTP-JSON path is used and this module is
never invoked by the SDK.

Fallback contract
-----------------
Every public entry-point in this module raises ``SQLiteBackendError`` on ANY
failure (download error, schema mismatch, sqlite error, missing FTS table …).
The caller (``pricing.py``) catches that base class and falls back to JSON
transparently.

URL override
------------
Set ``TOKENPRICING_DB_URL`` to use a different download URL.

Cache directory override
------------------------
Set ``TOKENPRICING_DB_CACHE_DIR`` to override the default
``~/.cache/tokenpricing`` directory.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import httpx

from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
    SourceInfo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DB_DOWNLOAD_URL = (
    os.environ.get("TOKENPRICING_DB_URL")
    or "https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices-current.db"
)

DB_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours – mirrors the JSON cache TTL

EXPECTED_USER_VERSION = 1

DOWNLOAD_TIMEOUT_SECONDS = 30


def _cache_dir() -> Path:
    """Return the platform cache directory for the tokenpricing DB."""
    override = os.environ.get("TOKENPRICING_DB_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "tokenpricing"


def _db_path() -> Path:
    return _cache_dir() / "prices-current.db"


# ---------------------------------------------------------------------------
# Public exception (callers catch this to trigger JSON fallback)
# ---------------------------------------------------------------------------


class SQLiteBackendError(Exception):
    """Raised on any failure in the SQLite backend so callers can fall back."""


# ---------------------------------------------------------------------------
# DB freshness + download
# ---------------------------------------------------------------------------


def _is_fresh(path: Path) -> bool:
    """Return True if the file exists and is younger than the TTL."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < DB_CACHE_TTL_SECONDS


def _download_db(dest: Path) -> None:
    """Download prices.db to *dest*, replacing any stale copy atomically."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = DB_DOWNLOAD_URL
    logger.debug("Downloading prices.db from %s", url)
    try:
        with httpx.Client(
            timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            # Write to a temp file in the same dir, then rename atomically
            tmp_fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".db.tmp")
            try:
                with os.fdopen(tmp_fd, "wb") as fh:
                    fh.write(response.content)
                os.replace(tmp_path, dest)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
    except httpx.HTTPError as exc:
        raise SQLiteBackendError(f"Failed to download prices.db: {exc}") from exc
    except OSError as exc:
        raise SQLiteBackendError(f"Failed to write prices.db to cache: {exc}") from exc


def _ensure_db() -> Path:
    """Return path to a fresh prices.db, downloading if needed."""
    path = _db_path()
    if not _is_fresh(path):
        _download_db(path)
    return path


# ---------------------------------------------------------------------------
# Read-only connection context manager
# ---------------------------------------------------------------------------


@contextmanager
def _open_db(path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Open the DB read-only and validate schema version."""
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        raise SQLiteBackendError(f"Cannot open prices.db: {exc}") from exc
    try:
        con.row_factory = sqlite3.Row
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version != EXPECTED_USER_VERSION:
            raise SQLiteBackendError(
                f"prices.db has schema version {version}, expected {EXPECTED_USER_VERSION}"
            )
        # Verify FTS table exists
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='models_fts'"
        ).fetchone()
        if row is None:
            raise SQLiteBackendError("prices.db is missing the models_fts FTS table")
        yield con
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Row → Pydantic helpers
# ---------------------------------------------------------------------------


def _row_to_model_info(row: sqlite3.Row, sources: dict[str, SourceInfo]) -> ModelInfo:
    """Convert a models-table row (plus pre-fetched sources) to ModelInfo."""
    pricing = PricingInfo(
        input_per_million=row["input_per_million"] or 0.0,
        output_per_million=row["output_per_million"] or 0.0,
        cache_read_per_million=row["cache_read_per_million"],
        cache_creation_per_million=row["cache_creation_per_million"],
        currency=row["currency"] or "USD",
    )
    return ModelInfo(
        provider=row["provider"],
        model_id=row["model_id"],
        display_name=row["display_name"],
        pricing=pricing,
        context_window=row["context_window"] or 0,
        max_output_tokens=row["max_output_tokens"] or 0,
        model_type=row["model_type"] or "text",
        supports_vision=bool(row["supports_vision"]),
        supports_function_calling=bool(row["supports_function_calling"]),
        supports_streaming=bool(row["supports_streaming"]),
        category=row["category"] or "standard",
        sources=sources,
    )


def _fetch_sources_for_models(
    con: sqlite3.Connection, model_ids: list[str]
) -> dict[str, dict[str, SourceInfo]]:
    """Return {model_id: {source_name: SourceInfo}} for a list of model IDs."""
    if not model_ids:
        return {}
    placeholders = ",".join("?" * len(model_ids))
    rows = con.execute(
        f"SELECT model_id, source, price_input, price_output, "
        f"price_cache_read, price_cache_creation, last_updated "
        f"FROM model_sources WHERE model_id IN ({placeholders})",
        model_ids,
    ).fetchall()
    result: dict[str, dict[str, SourceInfo]] = {mid: {} for mid in model_ids}
    for r in rows:
        mid = r["model_id"]
        # last_updated may be None or a string; SourceInfo expects a datetime
        lu_raw = r["last_updated"]
        if lu_raw:
            try:
                lu = datetime.fromisoformat(lu_raw)
            except ValueError:
                lu = datetime.now(timezone.utc)
        else:
            lu = datetime.now(timezone.utc)
        src = SourceInfo(
            price_input=r["price_input"] or 0.0,
            price_output=r["price_output"] or 0.0,
            price_cache_read=r["price_cache_read"],
            price_cache_creation=r["price_cache_creation"],
            last_updated=lu,
        )
        result[mid][r["source"]] = src
    return result


def _all_providers(con: sqlite3.Connection) -> dict[str, ProviderInfo]:
    """Read the full providers table."""
    rows = con.execute(
        "SELECT provider, name, website, pricing_page, affiliate_link FROM providers"
    ).fetchall()
    providers: dict[str, ProviderInfo] = {}
    for r in rows:
        providers[r["provider"]] = ProviderInfo(
            name=r["name"] or r["provider"],
            website=r["website"] or "",
            pricing_page=r["pricing_page"] or "",
            affiliate_link=r["affiliate_link"],
        )
    return providers


def _meta_row(con: sqlite3.Connection) -> sqlite3.Row:
    return con.execute(
        "SELECT generated_at, total_models, schema_version FROM meta LIMIT 1"
    ).fetchone()


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------


def get_model(model_id: str) -> ModelInfo:
    """Fetch a single model by primary key (indexed lookup).

    Raises:
        SQLiteBackendError: on any failure (caller should fall back to JSON).
        KeyError: if the model_id does not exist in the DB (not found).
    """
    try:
        path = _ensure_db()
        with _open_db(path) as con:
            row = con.execute(
                "SELECT * FROM models WHERE model_id = ?", (model_id,)
            ).fetchone()
            if row is None:
                raise KeyError(model_id)
            sources_map = _fetch_sources_for_models(con, [model_id])
            return _row_to_model_info(row, sources_map.get(model_id, {}))
    except (KeyError, SQLiteBackendError):
        raise
    except Exception as exc:
        raise SQLiteBackendError(
            f"SQLite lookup failed for {model_id!r}: {exc}"
        ) from exc


def search_models(
    provider: str | None = None,
    category: str | None = None,
    supports_vision: bool | None = None,
    supports_function_calling: bool | None = None,
    name_query: str | None = None,
) -> list[ModelInfo]:
    """Search models with SQL WHERE / FTS, mirroring PricingData.search_models.

    Raises:
        SQLiteBackendError: on any failure.
    """
    try:
        path = _ensure_db()
        with _open_db(path) as con:
            return _search_models_in_con(
                con,
                provider=provider,
                category=category,
                supports_vision=supports_vision,
                supports_function_calling=supports_function_calling,
                name_query=name_query,
            )
    except SQLiteBackendError:
        raise
    except Exception as exc:
        raise SQLiteBackendError(f"SQLite search failed: {exc}") from exc


def _search_models_in_con(
    con: sqlite3.Connection,
    provider: str | None = None,
    category: str | None = None,
    supports_vision: bool | None = None,
    supports_function_calling: bool | None = None,
    name_query: str | None = None,
) -> list[ModelInfo]:
    """Execute filtered search against an already-open connection."""
    params: list[object] = []

    if name_query:
        # Use FTS to get matching model_ids, then filter further with WHERE
        fts_rows = con.execute(
            "SELECT model_id FROM models_fts WHERE models_fts MATCH ?",
            (name_query,),
        ).fetchall()
        if not fts_rows:
            return []
        fts_ids = [r["model_id"] for r in fts_rows]
        placeholders = ",".join("?" * len(fts_ids))
        where = f"model_id IN ({placeholders})"
        params.extend(fts_ids)
    else:
        where = "1"

    clauses: list[str] = [where]

    if provider is not None:
        clauses.append("provider = ?")
        params.append(provider)
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if supports_vision is not None:
        clauses.append("supports_vision = ?")
        params.append(1 if supports_vision else 0)
    if supports_function_calling is not None:
        clauses.append("supports_function_calling = ?")
        params.append(1 if supports_function_calling else 0)

    sql = "SELECT * FROM models WHERE " + " AND ".join(clauses)
    rows = con.execute(sql, params).fetchall()
    if not rows:
        return []

    model_ids = [r["model_id"] for r in rows]
    sources_map = _fetch_sources_for_models(con, model_ids)
    return [_row_to_model_info(r, sources_map.get(r["model_id"], {})) for r in rows]


def get_all_pricing_data() -> PricingData:
    """Load the full pricing dataset from SQLite and return a PricingData object.

    This is used as a drop-in replacement for ``fetch_pricing_data()`` when the
    SQLite backend is active.  It loads all models + providers in one pass.

    Raises:
        SQLiteBackendError: on any failure.
    """
    try:
        path = _ensure_db()
        with _open_db(path) as con:
            meta = _meta_row(con)
            generated_at_raw = meta["generated_at"] if meta else None
            total_models = meta["total_models"] if meta else 0

            try:
                generated_at = (
                    datetime.fromisoformat(generated_at_raw)
                    if generated_at_raw
                    else datetime.now(timezone.utc)
                )
            except (ValueError, TypeError):
                generated_at = datetime.now(timezone.utc)

            providers = _all_providers(con)

            all_rows = con.execute("SELECT * FROM models").fetchall()
            model_ids = [r["model_id"] for r in all_rows]
            sources_map = _fetch_sources_for_models(con, model_ids)
            models: dict[str, ModelInfo] = {}
            for row in all_rows:
                mid = row["model_id"]
                models[mid] = _row_to_model_info(row, sources_map.get(mid, {}))

        # Reconstruct minimal MetadataInfo
        metadata = MetadataInfo(
            total_models=total_models or len(models),
            sources=["openrouter", "litellm"],
            last_scrape=generated_at,
            categories={},
        )
        return PricingData(
            generated_at=generated_at,
            models=models,
            providers=providers,
            metadata=metadata,
        )
    except SQLiteBackendError:
        raise
    except Exception as exc:
        raise SQLiteBackendError(
            f"Failed to load full dataset from SQLite: {exc}"
        ) from exc
