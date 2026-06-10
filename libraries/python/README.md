# tokenpricing (Python SDK)

[![PyPI version](https://img.shields.io/pypi/v/tokenpricing)](https://pypi.org/project/tokenpricing/)

API pricing math for 1k+ AI models from the canonical tokenpricing dataset with multi-currency and cache-token pricing support.

## Why tokenpricing?

Token pricing for AI models changes frequently across different providers and model types. This library now consumes the canonical dataset published from this repository, synchronized directly from upstream pricing sources every six hours.

**Important:** This library does **not** estimate token counts from strings or messages. Any estimation would be too approximate for anything beyond plain text, and the [tokencost](https://github.com/AgentOps-AI/tokencost) package already handles that use case well. tokenpricing focuses solely on providing accurate, current pricing data.

## Features

- Up-to-date AI model pricing from the tokenpricing canonical dataset
- Async caching via async-lru with a 6-hour TTL for pricing data
- Multi-currency conversion via JSDelivr currency API with a 24-hour cached USD rates map
- Clean, typed data models (Pydantic)

## Installation

```bash
uv add tokenpricing
```

Or with pip:

```bash
pip install tokenpricing
```

## Usage

The public API exposes both async and sync functions:

**Async API:**
- `get_pricing(model_id, currency="USD")`
- `compute_cost(model_id, input_tokens, output_tokens, currency="USD", cache_read_tokens=0, cache_creation_tokens=0)`

**Sync API:**
- `get_pricing_sync(model_id, currency="USD")`
- `compute_cost_sync(model_id, input_tokens, output_tokens, currency="USD", cache_read_tokens=0, cache_creation_tokens=0)`

### Async Example

```python
import asyncio

from tokenpricing import get_pricing, compute_cost


async def main():
    model_id = "openai/gpt-5.2"

    # Get pricing (cached transparently for ~6 hours)
    pricing = await get_pricing(model_id, currency="EUR")
    print(f"Pricing for {model_id} ({pricing.currency}):")
    print(f"  Input per 1M tokens: €{pricing.input_per_million:.2f}")
    print(f"  Output per 1M tokens: €{pricing.output_per_million:.2f}")

    # Compute total cost for a usage
    total = await compute_cost(model_id, input_tokens=1000, output_tokens=500, currency="EUR", cache_read_tokens=250, cache_creation_tokens=100)
    print(f"Total cost (EUR): €{total:.6f}")


asyncio.run(main())
```

### Sync Example

For simpler scripts, Jupyter notebooks, or environments where async is inconvenient, use the sync versions:

```python
from tokenpricing import get_pricing_sync, compute_cost_sync

model_id = "openai/gpt-5.2"

# Get pricing (cached transparently for ~6 hours)
pricing = get_pricing_sync(model_id, currency="EUR")
print(f"Pricing for {model_id} ({pricing.currency}):")
print(f"  Input per 1M tokens: €{pricing.input_per_million:.2f}")
print(f"  Output per 1M tokens: €{pricing.output_per_million:.2f}")

# Compute total cost for a usage
total = compute_cost_sync(
    model_id,
    input_tokens=1000,
    output_tokens=500,
    currency="EUR",
    cache_read_tokens=250,
    cache_creation_tokens=100,
)
print(f"Total cost (EUR): €{total:.6f}")
```

Both sync and async APIs share the same underlying cache, so mixing them won't cause duplicate fetches.

### Helpful Error Messages

When you make a typo in a model ID or currency code, tokenpricing provides helpful "Did you mean?" suggestions:

```python
from tokenpricing import get_pricing_sync

# Typo in model name: "gpt4" instead of "gpt-4"
get_pricing_sync("openai/gpt4")
# ValueError: Model not found: openai/gpt4. Did you mean 'openai/gpt-4'?

# Typo in currency: "ERU" instead of "EUR"
get_pricing_sync("openai/gpt-4", currency="ERU")
# ValueError: Unsupported currency: ERU. Did you mean 'EUR'?
```

## CLI

Install via UV or pip, then use the `tokenpricing` command.

```bash
# Show price per 1M tokens (USD default)
tokenpricing pricing openai/gpt-5.2

# Convert to another currency (uses cached FX rates)
tokenpricing pricing openai/gpt-5.2 --currency EUR

# JSON output for scripting
tokenpricing pricing openai/gpt-5.2 --json

# Compute total cost for a usage
tokenpricing cost openai/gpt-5.2 --in 1000 --out 500 --cache-read 250 --cache-write 100 --currency EUR
```

## Claude Code skill

The repository also ships a Claude Code marketplace manifest at `.claude-plugin/marketplace.json` and the canonical hidden skill at `skills/tokenpricing/SKILL.md`.

The skill wraps the existing `tokenpricing` CLI for pricing lookups and workload cost calculations. It does not estimate token counts from raw text.

The canonical skill source in this repository is `skills/tokenpricing/SKILL.md`.

## Data Source

Pricing data is sourced from the canonical tokenpricing dataset generated in this repository from OpenRouter and LiteLLM. The raw data is available at:
```
https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json
```

Caching uses async-lru with a 6-hour TTL aligned to the canonical sync cadence. Caching is fully transparent to callers of the public API.

Note: Pricing data is denominated in USD; currency conversion uses daily USD base rates from the JSDelivr currency API with a 24h cache (keys uppercased).

## Development

This project uses `uv` as the package manager.

### Setup

```bash
uv sync
```

### Running Tests

```bash
uv run pytest
```

### Quality (pre-commit)

Use pre-commit to run formatting and linting consistently:

```bash
# One-time setup (from repo root)
uv run pre-commit install

# Run all hooks on the codebase (from repo root)
uv run pre-commit run -a
```

This runs `ruff-format` and `ruff` with `--fix`, along with basic repo hygiene checks.

## API Surface

The public API includes both async and sync versions:
- Async: `get_pricing`, `compute_cost`
- Sync: `get_pricing_sync`, `compute_cost_sync`

Internal modules and models are not considered public and may change. Both APIs share the same cache, so you can mix async and sync calls without performance penalty.

## Credits

- Canonical database sync: [Atena-IT/tokenpricing](https://github.com/Atena-IT/tokenpricing)

## License

See [LICENSE](../../LICENSE) file for details.
