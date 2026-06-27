"""Fetch and manage canonical pricing data from tokenpricing.

Data source: https://github.com/Atena-IT/tokenpricing

Backend selection
-----------------
By default the HTTP-JSON path is used.  Set ``TOKENPRICING_USE_SQLITE=1``
to opt into the experimental SQLite backend (see ``sqlite_backend.py``).
The SQLite backend silently falls back to JSON on any failure.
"""

import logging
import os

import httpx
from async_lru import alru_cache

from tokenpricing.modeling import PricingData

logger = logging.getLogger(__name__)

# Canonical pricing data URL - updated every 6 hours
CANONICAL_DATASET_URL = "https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json"

# Cache TTL: 6 hours (21600 seconds) - aligns with canonical database refresh frequency
CACHE_TTL_SECONDS = 6 * 60 * 60


def _sqlite_enabled() -> bool:
    """Return True when the SQLite backend opt-in env var is set."""
    val = os.environ.get("TOKENPRICING_USE_SQLITE", "").strip().lower()
    return val not in ("", "0", "false", "no")


async def fetch_pricing_data() -> PricingData:
    """Fetch pricing data from the tokenpricing canonical database.

    When ``TOKENPRICING_USE_SQLITE=1`` is set, attempts to load from the cached
    SQLite DB first; falls back to the HTTP-JSON path on any failure.

    Returns:
        PricingData: Parsed pricing data from the canonical database

    Raises:
        httpx.HTTPError: If the HTTP request fails (JSON path)
        pydantic.ValidationError: If the response data is invalid
    """
    if _sqlite_enabled():
        try:
            import asyncio

            from tokenpricing.sqlite_backend import get_all_pricing_data

            data = await asyncio.to_thread(get_all_pricing_data)
            logger.debug("Loaded pricing data from SQLite backend")
            return data
        except Exception as exc:
            logger.warning(
                "SQLite backend failed (%s: %s), falling back to JSON",
                type(exc).__name__,
                exc,
            )

    async with httpx.AsyncClient() as client:
        response = await client.get(CANONICAL_DATASET_URL)
        response.raise_for_status()
        data = response.json()  # httpx .json() is not async
        return PricingData.model_validate(data)


@alru_cache(ttl=CACHE_TTL_SECONDS)
async def _get_pricing_data_bucketed() -> PricingData:
    """Internal cached getter using async-lru TTL."""
    return await fetch_pricing_data()


async def get_pricing_data(force_refresh: bool = False) -> PricingData:
    """Get pricing data with async-lru caching (6h TTL).

    Args:
        force_refresh: If True, clear cache and fetch fresh data

    Returns:
        PricingData: Current pricing data
    """
    if force_refresh:
        # Clear cache to force fresh fetch
        _get_pricing_data_bucketed.cache_clear()

    return await _get_pricing_data_bucketed()


def clear_pricing_cache() -> None:
    """Clear the pricing data cache (used in tests)."""
    _get_pricing_data_bucketed.cache_clear()
