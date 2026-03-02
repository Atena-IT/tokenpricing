"""Example: Compute cost using sync API (no asyncio needed)."""

from tokenpricing import compute_cost_sync


def main():
    model_id = "openai/gpt-5.2"
    input_tokens = 1000
    output_tokens = 500

    try:
        # USD
        cost_usd = compute_cost_sync(
            model_id, input_tokens, output_tokens, currency="USD"
        )
        print(f"Cost for {input_tokens} input + {output_tokens} output tokens:")
        print(f"  USD: ${cost_usd:.6f}")

        # EUR
        cost_eur = compute_cost_sync(
            model_id, input_tokens, output_tokens, currency="EUR"
        )
        print(f"  EUR: €{cost_eur:.6f}")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
