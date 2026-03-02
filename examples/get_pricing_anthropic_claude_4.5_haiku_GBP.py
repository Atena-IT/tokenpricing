import asyncio

from tokenpricing import get_pricing


async def main():
    model_id = "replicate/anthropic/claude-4.5-haiku"
    try:
        pricing = await get_pricing(model_id, currency="GBP")
        print(f"{model_id} pricing ({pricing.currency}):")
        print(f"  Input per 1M tokens: £{pricing.input_per_million}")
        print(f"  Output per 1M tokens: £{pricing.output_per_million}")
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
