# tokenpricing (TypeScript SDK)

[![npm version](https://img.shields.io/npm/v/tokenpricing)](https://www.npmjs.com/package/tokenpricing)

API pricing math for 1k+ AI models from [LLMTracker](https://mrunreal.github.io/LLMTracker) with multi-currency support.

## Why tokenpricing?

Token pricing for LLMs changes frequently across different providers. This library provides up-to-date pricing information by leveraging [LLMTracker](https://github.com/MrUnreal/LLMTracker), which updates pricing data every six hours from various sources.

**Important:** This library does **not** estimate token counts from strings or messages. tokenpricing focuses solely on providing accurate, current pricing data.

## Features

- Up-to-date LLM pricing from [LLMTracker](https://mrunreal.github.io/LLMTracker/)
- Caching with 6-hour TTL for pricing data
- Multi-currency conversion via JSDelivr currency API with a 24-hour cached USD rates map
- TypeScript-first with full type definitions
- ESM and CJS dual-format package
- Zero dependencies beyond `fuse.js` (for fuzzy matching)

## Installation

```bash
pnpm add tokenpricing
```

Or with npm:

```bash
npm install tokenpricing
```

## Usage

```typescript
import { getPricing, computeCost } from "tokenpricing";
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
const cost = await computeCost("openai/gpt-5.2", 1000, 500, "EUR");
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

### `computeCost(modelId, inputTokens, outputTokens, currency?)`

Compute total cost for a specific model given token counts.

- `modelId` — Model identifier
- `inputTokens` — Number of input tokens
- `outputTokens` — Number of output tokens
- `currency` — Target currency code (default: `"USD"`)
- Returns `Promise<number>`

### `PricingInfo`

```typescript
interface PricingInfo {
  inputPerMillion: number;
  outputPerMillion: number;
  currency: string;
}
```

## Data Source

Pricing data is sourced from [LLMTracker](https://github.com/MrUnreal/LLMTracker), which aggregates and updates pricing information from various LLM providers every six hours.

Caching uses a 6-hour TTL aligned to LLMTracker's refresh cadence. Currency conversion uses daily USD base rates from the JSDelivr currency API with a 24-hour cache.

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

- Pricing data: [LLMTracker](https://github.com/MrUnreal/LLMTracker) by MrUnreal

## License

See [LICENSE](../../LICENSE) file for details.
