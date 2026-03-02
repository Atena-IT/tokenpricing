"""Example: Get pricing using sync API (no asyncio needed)."""

from tokenpricing import get_pricing_sync


def main():
    model_id = "openai/gpt-5.2"
    try:
        pricing = get_pricing_sync(model_id, currency="USD")
        print(f"{model_id} pricing ({pricing.currency}):")
        print(f"  Input per 1M tokens: ${pricing.input_per_million}")
        print(f"  Output per 1M tokens: ${pricing.output_per_million}")
    except ValueError as e:
        print(f"Model not found or unavailable: {e}")


if __name__ == "__main__":
    main()
