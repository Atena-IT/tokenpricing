"""Fetch and manage LLM pricing data from LLMTracker.

Data source: https://github.com/DiTo97/LLMTracker
Website: https://mrunreal.github.io/LLMTracker/
"""

import httpx
from async_lru import alru_cache

from tokenpricing.modeling import PricingData

# LLMTracker data URL - updated every 6 hours
LLMTRACKER_URL = (
    "https://raw.githubusercontent.com/DiTo97/LLMTracker/main/data/current/prices.json"
)

# Cache TTL: 6 hours (21600 seconds) - aligns with LLMTracker update frequency
CACHE_TTL_SECONDS = 6 * 60 * 60


async def fetch_pricing_data() -> PricingData:
    """Fetch pricing data from LLMTracker.

    This function makes an async HTTP request to LLMTracker's pricing data endpoint
    and parses it into a PricingData object.

    Returns:
        PricingData: Parsed pricing data from LLMTracker

    Raises:
        httpx.HTTPError: If the HTTP request fails
        pydantic.ValidationError: If the response data is invalid
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(LLMTRACKER_URL)
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
