# Quickstart

tokenpricing answers two questions: *what does a model cost per million tokens* and *what will this workload cost* — for 3,000+ AI models, in any currency, including prompt-cache rates.

## Install

::: code-group

```bash [Python]
pip install tokenpricing
```

```bash [TypeScript]
npm install tokenpricing
```

:::

The Python package ships the `tokenpricing` CLI; the npm package exposes the same APIs for Node.js 18+.

## Look up a price

```bash
tokenpricing pricing openai/gpt-5.2
```

```
openai/gpt-5.2 pricing (USD):
  Input per 1M tokens: 1.250000 USD
  Output per 1M tokens: 10.000000 USD
  Cache read per 1M tokens: 0.125000 USD
```

Add `--currency EUR` for converted rates (cached FX), or `--json` for machine-readable output.

## Compute a workload cost

```bash
tokenpricing cost openai/gpt-5.2 --in 250000 --out 40000 --cache-read 100000 --currency EUR
```

Cache flags are optional and default to `0`.

## From code

::: code-group

```python [Python]
from tokenpricing import get_pricing_sync, compute_cost_sync

pricing = get_pricing_sync("openai/gpt-5.2", currency="EUR")
print(f"Input: €{pricing.input_per_million:.2f}/1M tokens")

cost = compute_cost_sync(
    "openai/gpt-5.2",
    input_tokens=1000,
    output_tokens=500,
    cache_read_tokens=250,
)
```

```typescript [TypeScript]
import { getPricing, computeCost } from "tokenpricing";

const pricing = await getPricing("openai/gpt-5.2", "EUR");

const cost = await computeCost("openai/gpt-5.2", 1000, 500, "USD", {
  cacheReadTokens: 250,
});
```

:::

## Next steps

- [CLI reference](/cli) — every flag, JSON shapes, model-id suggestions
- [SDKs](/sdks) — async APIs, caching behavior, currency handling
- [Webhook notifications](/notifications) — alerts for price moves and model lifecycle events
- [Canonical database](/database) — consume the raw JSON directly
