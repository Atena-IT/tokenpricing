"""Example usage of tokenpricing public API."""

import asyncio

from tokenpricing import compute_cost, get_pricing


async def main():
    """Demonstrate basic usage of tokenpricing public API."""
    model_id = "openai/gpt-5.2-codex"

    pricing = await get_pricing(model_id)
    print(f"Pricing for {model_id} ({pricing.currency}):")
    print(
        f"  Input: ${pricing.input_per_million:.2f} per M tokens\n"
        f"  Output: ${pricing.output_per_million:.2f} per M tokens"
    )

    # Compute a sample cost
    input_tokens = 1000
    output_tokens = 500
    total = await compute_cost(model_id, input_tokens, output_tokens)
    print(
        f"\nCost for {input_tokens} in / {output_tokens} out: ${total:.6f} ({pricing.currency})"
    )


if __name__ == "__main__":
    asyncio.run(main())
