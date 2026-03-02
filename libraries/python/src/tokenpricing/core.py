"""Public facade API for tokenpricing.

Exposes async and sync versions:
- get_pricing(model_id, currency="USD") [async]
- get_pricing_sync(model_id, currency="USD") [sync]
- compute_cost(model_id, input_tokens, output_tokens, currency="USD") [async]
- compute_cost_sync(model_id, input_tokens, output_tokens, currency="USD") [sync]

Under the hood, uses async cached pricing data from LLMTracker and optional
forex conversion via JSDelivr currency API (cached for 24h).

When lookups fail, errors include "Did you mean X?" suggestions when a close
match is found.
"""

from __future__ import annotations

from decimal import Decimal

from tokenpricing.currency import get_usd_rate
from tokenpricing.pricing import get_pricing_data
from tokenpricing.safeasyncio import make_sync


async def get_pricing(model_id: str, currency: str = "USD"):
    """Get pricing info for a specific model.

    Args:
        model_id: The model identifier (e.g., 'openai/gpt-4')
        currency: Target currency code (default: USD). Case-insensitive.

    Returns:
        PricingInfo for the model, priced in the requested currency.

    Raises:
        ValueError: If the model or currency is not found (includes suggestions).
    """
    data = await get_pricing_data()
    model = data.get_model(model_id)
    if model is None:
        # Try to suggest a similar model for the error message
        suggestion = data.suggest_model(model_id)
        if suggestion:
            raise ValueError(
                f"Model not found: {model_id}. Did you mean '{suggestion}'?"
            )
        raise ValueError(f"Model not found: {model_id}")

    # If USD requested, return as-is
    target = currency.upper()
    if target == "USD":
        return model.pricing

    # Convert pricing from USD to target currency using Decimal
    # Note: get_usd_rate already includes "Did you mean" in its error
    rate = await get_usd_rate(target)
    inp = Decimal(str(model.pricing.input_per_million)) * rate
    outp = Decimal(str(model.pricing.output_per_million)) * rate

    from tokenpricing.modeling import PricingInfo

    return PricingInfo(
        input_per_million=float(inp),
        output_per_million=float(outp),
        currency=target,
    )


async def compute_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    currency: str = "USD",
) -> float:
    """Compute total cost for a specific model given token counts.

    Pricing is calculated using price per million tokens.

    Args:
        model_id: The model identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        currency: Target currency code (default: USD). Case-insensitive.

    Returns:
        Total cost as a float in the requested currency.

    Raises:
        ValueError: If the model is not found or token counts are negative.
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be non-negative")

    pricing = await get_pricing(model_id, currency=currency)

    per_million = 1_000_000
    input_cost = (input_tokens / per_million) * pricing.input_per_million
    output_cost = (output_tokens / per_million) * pricing.output_per_million
    return input_cost + output_cost


# Sync wrappers using safeasyncio
get_pricing_sync = make_sync()(get_pricing)
compute_cost_sync = make_sync()(compute_cost)
