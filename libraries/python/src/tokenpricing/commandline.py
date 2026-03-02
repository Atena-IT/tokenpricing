from __future__ import annotations

import asyncio
import json

import click

from tokenpricing.core import compute_cost, get_pricing


@click.group(help="Query LLM token pricing and compute costs")
def main(): ...


@main.command(
    "pricing",
    help="Show live input/output price per 1M tokens for a model, e.g., openai/gpt-5.2",
)
@click.argument("model", metavar="MODEL")
@click.option(
    "--currency",
    type=str,
    default="USD",
    show_default=True,
    help="Target currency code (e.g., USD, EUR). Uses cached FX rates.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output machine-readable JSON",
)
def price_command(model: str, currency: str, as_json: bool) -> None:
    async def _run() -> None:
        try:
            pricing = await get_pricing(model, currency=currency)
        except (ValueError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e

        if as_json:
            click.echo(
                json.dumps(
                    {
                        "model": model,
                        "currency": pricing.currency,
                        "input_per_million": pricing.input_per_million,
                        "output_per_million": pricing.output_per_million,
                    }
                )
            )
        else:
            click.echo(f"{model} pricing ({pricing.currency}):")
            click.echo(
                f"  Input per 1M tokens: {pricing.input_per_million:.6f} {pricing.currency}"
            )
            click.echo(
                f"  Output per 1M tokens: {pricing.output_per_million:.6f} {pricing.currency}"
            )

    asyncio.run(_run())


@main.command(
    "cost",
    help="Compute total cost for a given budget of input/output tokens for a model, e.g., openai/gpt-5.2",
)
@click.argument("model", metavar="MODEL")
@click.option("--in", "input_tokens", type=int, required=True, help="Input tokens")
@click.option("--out", "output_tokens", type=int, required=True, help="Output tokens")
@click.option(
    "--currency",
    type=str,
    default="USD",
    show_default=True,
    help="Target currency code (e.g., USD, EUR). Uses cached FX rates.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output machine-readable JSON",
)
def cost_command(
    model: str,
    input_tokens: int,
    output_tokens: int,
    currency: str,
    as_json: bool,
) -> None:
    async def _run() -> None:
        try:
            total = await compute_cost(
                model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                currency=currency,
            )
        except (ValueError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e

        if as_json:
            click.echo(
                json.dumps(
                    {
                        "model": model,
                        "currency": currency.upper(),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total": total,
                    }
                )
            )
        else:
            click.echo(
                f"Cost for {model} ({currency.upper()}): {total:.6f} on {input_tokens} in / {output_tokens} out"
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
