# tokenpricing (TypeScript SDK)

[![npm version](https://img.shields.io/npm/v/tokenpricing)](https://www.npmjs.com/package/tokenpricing)

API pricing math for 1k+ AI models from the canonical tokenpricing database with multi-currency and cache-token pricing support.

## Why tokenpricing?

Token pricing for AI models changes frequently across different providers and model types. This library now consumes the canonical database published from this repository, synchronized directly from upstream pricing sources every six hours.

**Important:** This library does **not** estimate token counts from strings or messages. tokenpricing focuses solely on providing accurate, current pricing data.

## Features

- Up-to-date AI model pricing from the tokenpricing canonical database
- Caching with 6-hour TTL for pricing data
- Multi-currency conversion via JSDelivr currency API with a 24-hour cached USD rates map
- TypeScript-first with full type definitions
- ESM and CJS dual-format package
- Zero dependencies beyond `fuse.js` (for fuzzy matching)

## Installation

```bash
pnpm add @atenareply/tokenpricing
```

Or with npm:

```bash
npm install @atenareply/tokenpricing
```

## Usage

```typescript
import { getPricing, computeCost } from "@atenareply/tokenpricing";
```

### Get Pricing

```typescript
const pricing = await getPricing("openai/gpt-5.2");
console.log(`Input: $${pricing.inputPerMillion.toFixed(2)}/1M tokens`);
console.log(`Output: $${pricing.outputPerMillion.toFixed(2)}/1M tokens`);
```

### Get Pricing in Another Currency

```typescript
const pricing = await getPricing("openai/gpt-5.2", "EUR");
console.log(`Input: €${pricing.inputPerMillion.toFixed(2)}/1M tokens`);
```

### Compute Cost

```typescript
const cost = await computeCost("openai/gpt-5.2", 1000, 500, "EUR", { cacheReadTokens: 250, cacheCreationTokens: 100 });
console.log(`Total cost: €${cost.toFixed(6)}`);
```

### Helpful Error Messages

When you make a typo in a model ID or currency code, tokenpricing provides helpful "Did you mean?" suggestions:

```typescript
await getPricing("openai/gpt4");
// Error: Model not found: openai/gpt4. Did you mean 'openai/gpt-4'?

await getPricing("openai/gpt-4", "ERU");
// Error: Unsupported currency: ERU. Did you mean 'EUR'?
```

## API

### `getPricing(modelId, currency?)`

Get pricing info for a specific model.

- `modelId` — Model identifier (e.g., `"openai/gpt-4"`)
- `currency` — Target currency code (default: `"USD"`)
- Returns `Promise<PricingInfo>`

### `computeCost(modelId, inputTokens, outputTokens, currency?, options?)`

Compute total cost for a specific model given token counts.

- `modelId` — Model identifier
- `inputTokens` — Number of input tokens
- `outputTokens` — Number of output tokens
- `currency` — Target currency code (default: `"USD"`)
- `options.cacheReadTokens` / `options.cacheCreationTokens` — optional cached-token usage
- Returns `Promise<number>`

### `PricingInfo`

```typescript
interface PricingInfo {
  inputPerMillion: number;
  outputPerMillion: number;
  cacheReadPerMillion?: number;
  cacheCreationPerMillion?: number;
  currency: string;
}
```

## SQLite Backend (optional, Node.js only)

By default, the SDK fetches the full ~2.9 MB JSON dataset over HTTP on first use. For faster cold starts and indexed lookups, you can opt in to a SQLite read path that downloads and caches the slim `prices-current.db` (~a few MB) published with every database sync.

### Enabling

1. Install the optional peer dependency:

   ```bash
   npm install better-sqlite3
   ```

2. Set the environment variable before your process starts:

   ```bash
   TOKENPRICING_USE_SQLITE=1 node your-app.js
   ```

   Accepted truthy values: `1`, `true`, `yes` (case-insensitive). Any other value (including unset) uses the default JSON path.

### How it works

- On first call the SDK downloads `prices-current.db` from the rolling GitHub Release at `database-latest` and caches it in `<os.tmpdir()>/tokenpricing/prices-current.db`.
- The cache file is reused for 6 hours (same TTL as the JSON path). After 6 hours the file is re-downloaded on the next request.
- The database is validated: schema version must equal `1` (`PRAGMA user_version`) and the `models_fts` FTS table must be present. Any validation failure falls back to JSON transparently with a `console.warn`.

### Environment variable overrides

| Variable | Default | Description |
| --- | --- | --- |
| `TOKENPRICING_USE_SQLITE` | unset (disabled) | Set to `1`, `true`, or `yes` to enable |
| `TOKENPRICING_DB_URL` | GitHub Release URL for `prices-current.db` | Override the download URL (e.g. to use `prices.db` with full history) |
| `TOKENPRICING_DB_CACHE_DIR` | `<os.tmpdir()>/tokenpricing` | Override the local cache directory |

### Fallback behaviour

Any failure in the SQLite path (download error, schema mismatch, missing `better-sqlite3`, etc.) is caught and logged as a warning, and the SDK falls back to the HTTP-JSON path automatically. The SQLite backend never causes a hard failure.

## Data Source

Pricing data is sourced from the canonical tokenpricing dataset generated in this repository from OpenRouter and LiteLLM.

Caching uses a 6-hour TTL aligned to the canonical sync cadence. Currency conversion uses daily USD base rates from the JSDelivr currency API with a 24-hour cache.

## Development

### Setup

```bash
pnpm install
```

### Commands

```bash
pnpm build          # Build ESM + CJS bundles
pnpm test           # Run tests
pnpm test:coverage  # Run tests with coverage
pnpm lint           # Lint and format check
pnpm lint:fix       # Auto-fix lint/format issues
pnpm typecheck      # TypeScript type check
```

## Credits

- Canonical database sync: [Atena-IT/tokenpricing](https://github.com/Atena-IT/tokenpricing)

## License

See [LICENSE](../../LICENSE) file for details.
