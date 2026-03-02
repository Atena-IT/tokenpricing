import asyncio

from tokenpricing import get_pricing


async def main():
    model_id = "openai/gpt-5.2"
    try:
        pricing = await get_pricing(model_id, currency="USD")
        print(f"{model_id} pricing ({pricing.currency}):")
        print(f"  Input per 1M tokens: ${pricing.input_per_million}")
        print(f"  Output per 1M tokens: ${pricing.output_per_million}")
    except ValueError as e:
        print(f"Model not found or unavailable: {e}")


if __name__ == "__main__":
    asyncio.run(main())
