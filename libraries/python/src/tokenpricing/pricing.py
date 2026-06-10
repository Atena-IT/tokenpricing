"""Fetch and manage canonical pricing data from tokenpricing.

Data source: https://github.com/Atena-IT/tokenpricing
"""

import httpx
from async_lru import alru_cache

from tokenpricing.modeling import PricingData

# Canonical pricing data URL - updated every 6 hours
CANONICAL_DATASET_URL = "https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json"

# Cache TTL: 6 hours (21600 seconds) - aligns with canonical dataset refresh frequency
CACHE_TTL_SECONDS = 6 * 60 * 60


async def fetch_pricing_data() -> PricingData:
    """Fetch pricing data from the tokenpricing canonical dataset.

    This function makes an async HTTP request to the canonical pricing data endpoint
    and parses it into a PricingData object.

    Returns:
        PricingData: Parsed pricing data from the canonical dataset

    Raises:
        httpx.HTTPError: If the HTTP request fails
        pydantic.ValidationError: If the response data is invalid
    """
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
