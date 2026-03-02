"""Currency utilities with 24h cached USD base rates.

Fetches USD-based currency rates from the JSDelivr currency API and caches the
uppercased currency mapping for 24 hours using async-lru's built-in TTL.
All conversions use Decimal for precision.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
from async_lru import alru_cache

FOREX_TTL_SECONDS = 24 * 60 * 60
FOREX_FETCH_TIMEOUT_SECONDS = 10
FOREX_BASE = "USD"
FOREX_ENDPOINT_TEMPLATE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{base}.json"


def _sync_get_usd_rates() -> dict[str, Decimal]:
    """Synchronous helper to fetch USD-based rates.

    This runs in a worker thread via ``asyncio.to_thread`` to avoid blocking
    the event loop. It performs a blocking HTTP request using httpx's
    synchronous client and normalizes the returned mapping to Decimal with
    uppercased currency codes.
    """
    base_lower = FOREX_BASE.lower()
    url = FOREX_ENDPOINT_TEMPLATE.format(base=base_lower)
    with httpx.Client(timeout=FOREX_FETCH_TIMEOUT_SECONDS) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    # Extract inner currency list for the base (e.g., "usd") and uppercase keys
    inner = data.get(base_lower, {})
    return {
        code.upper(): (val if isinstance(val, Decimal) else Decimal(str(val)))
        for code, val in inner.items()
    }


@alru_cache(maxsize=1, ttl=FOREX_TTL_SECONDS)
async def _get_usd_rates_bucketed() -> dict[str, Decimal]:
    # Run the synchronous helper in a worker thread
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_get_usd_rates), timeout=FOREX_FETCH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError("Fetching USD forex rates timed out") from e


async def get_usd_rates(force_refresh: bool = False) -> dict[str, Decimal]:
    """Return mapping of currency code -> Decimal rate for 1 USD.

    Rates are cached for 24 hours. If `force_refresh` is True, the cache is
    cleared before retrieving fresh data.
    """
    if force_refresh:
        _get_usd_rates_bucketed.cache_clear()
    return await _get_usd_rates_bucketed()


async def get_usd_rate(currency: str) -> Decimal:
    """Get Decimal conversion rate for 1 USD -> `currency`.

    Args:
        currency: ISO currency code (e.g., 'EUR'). Case-insensitive.

    Returns:
        Decimal rate such that `amount_usd * rate` yields amount in `currency`.

    Raises:
        ValueError: If the currency is not supported (includes suggestion if available).
    """
    code = currency.upper()
    if code == "USD":
        return Decimal("1")
    rates = await get_usd_rates()

    if code in rates:
        return rates[code]

    # Currency not found - try to suggest a similar one for the error message
    from tokenpricing.suggestions import suggest_currency

    match = suggest_currency(query=code, currency_codes=list(rates.keys()))
    if match is not None:
        raise ValueError(
            f"Unsupported currency: {currency}. Did you mean '{match.match}'?"
        )

    raise ValueError(f"Unsupported currency: {currency}")
