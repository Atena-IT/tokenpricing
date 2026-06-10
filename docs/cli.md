# CLI reference

The `tokenpricing` CLI is installed with the Python package (`pip install tokenpricing`). Inside the repository you can run it without installing: `uv run --project libraries/python tokenpricing ...`.

## `tokenpricing pricing`

Show live prices per million tokens for a model.

```bash
tokenpricing pricing MODEL [--currency CODE] [--json]
```

| Option | Default | Description |
| --- | --- | --- |
| `MODEL` | — | Model identifier, e.g. `openai/gpt-5.2`, `anthropic/claude-opus-4` |
| `--currency` | `USD` | Target currency code (e.g. `EUR`, `GBP`, `CNY`); uses cached FX rates |
| `--json` | off | Machine-readable output |

JSON output shape:

```json
{
  "model": "anthropic/claude-opus-4",
  "currency": "USD",
  "input_per_million": 15.0,
  "output_per_million": 75.0,
  "cache_read_per_million": 1.5,
  "cache_creation_per_million": 18.75
}
```

The two cache fields are `null` when the model does not publish cache rates — that means "no published cache pricing", not free.

## `tokenpricing cost`

Compute the total cost of a workload from token counts.

```bash
tokenpricing cost MODEL --in INPUT --out OUTPUT [--cache-read N] [--cache-write N] [--currency CODE] [--json]
```

| Option | Default | Description |
| --- | --- | --- |
| `--in` | required | Input (prompt) tokens |
| `--out` | required | Output (completion) tokens |
| `--cache-read` | `0` | Cached input tokens served from cache hits |
| `--cache-write` | `0` | Input tokens written into the cache |
| `--currency` | `USD` | Target currency code |
| `--json` | off | Machine-readable output |

```bash
tokenpricing cost openai/gpt-5.2 --in 1000 --out 500 --cache-read 250 --cache-write 100 --currency EUR
```

::: tip Estimating cache savings
Run `cost` twice — once with all tokens under `--in`, once split across `--in` and `--cache-read`/`--cache-write` — and compare the totals.
:::

## Model-id suggestions

When a model or currency is not found, the CLI suggests close matches ("Did you mean …") instead of failing silently. Model identifiers follow the canonical database keys — browse them in the [dashboard](https://atena-it.github.io/tokenpricing/) or the [raw JSON](/database).
