# Python & TypeScript SDKs

Both SDKs read the same canonical database and expose the same two operations: pricing lookup and cost computation. Results are cached locally with a time-to-live, so repeated calls don't refetch the database.

## Python

```bash
pip install tokenpricing
```

Async-first, with `_sync` convenience wrappers:

```python
from tokenpricing import get_pricing, compute_cost            # async
from tokenpricing import get_pricing_sync, compute_cost_sync  # sync

pricing = get_pricing_sync("anthropic/claude-opus-4", currency="EUR")
pricing.input_per_million          # float
pricing.output_per_million         # float
pricing.cache_read_per_million     # float | None
pricing.cache_creation_per_million # float | None
pricing.currency                   # "EUR"

total = compute_cost_sync(
    "anthropic/claude-opus-4",
    input_tokens=250_000,
    output_tokens=40_000,
    cache_read_tokens=100_000,
    cache_creation_tokens=20_000,
    currency="USD",
)
```

## TypeScript

```bash
npm install tokenpricing
```

```typescript
import { getPricing, computeCost } from "tokenpricing";

const pricing = await getPricing("anthropic/claude-opus-4", "EUR");
// pricing.inputPerMillion, pricing.outputPerMillion,
// pricing.cacheReadPerMillion, pricing.cacheCreationPerMillion

const total = await computeCost("anthropic/claude-opus-4", 250_000, 40_000, "USD", {
  cacheReadTokens: 100_000,
  cacheCreationTokens: 20_000,
});
```

## Model metadata

Both SDKs surface the full model record from the canonical database: context window, max output tokens, capability flags (`supports_vision`, `supports_function_calling`, `supports_streaming`), and `model_type` following the OpenRouter output-modality taxonomy — `text`, `image`, `embeddings`, `audio`, `video`, `rerank`, `speech`, `transcription`.

## Currency conversion

Non-USD lookups convert using cached foreign-exchange rates. Conversion is best-effort for estimation — billing always happens in the provider's own currency.

More runnable examples live in the repository under [`libraries/python/examples`](https://github.com/Atena-IT/tokenpricing/tree/main/libraries/python/examples) and [`libraries/typescript/examples`](https://github.com/Atena-IT/tokenpricing/tree/main/libraries/typescript/examples).
