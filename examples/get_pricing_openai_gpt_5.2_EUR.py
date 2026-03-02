import asyncio

from tokenpricing import get_pricing


async def main():
    model_id = "openai/gpt-5.2"
    try:
        pricing = await get_pricing(model_id, currency="EUR")
        print(f"{model_id} pricing ({pricing.currency}):")
        print(f"  Input per 1M: €{pricing.input_per_million}")
        print(f"  Output per 1M: €{pricing.output_per_million}")
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
