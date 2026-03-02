# tokenpricing (TypeScript SDK) — AGENTS.md

This file orients AI coding agents working on the TypeScript SDK. Keep it concise, follow progressive disclosure, and always link to detailed docs in AGENTS-docs.

## Why
- Provide up-to-date API pricing math for 1k+ AI models using LLMTracker (updates ~6h).
- Focus on pricing data only — no token counting.
- TypeScript equivalent of the Python SDK — same data source, same behavior, idiomatic TS API.
- Credit LLMTracker in code and docs: repo and website.

## What
- Stack: TypeScript 5, Node 18+, native `fetch`, `fuse.js` (fuzzy matching), `vitest` (testing), `tsup` (build), `biome` (lint/format), `pnpm` (package manager).
- Key modules:
  - src/cache.ts — generic `TtlCache<T>` class for single-entry TTL caching.
  - src/modeling.ts — TypeScript interfaces and runtime validator for LLMTracker JSON.
  - src/pricing.ts — fetch + 6h TTL cache of LLMTracker pricing data.
  - src/currency.ts — USD base rates from JSDelivr currency API with 24h TTL cache.
  - src/suggestions.ts — fuzzy matching via fuse.js for "Did you mean?" errors.
  - src/core.ts — public facade: `getPricing()` and `computeCost()`.
  - src/index.ts — re-exports public API and types.
- Current state (truth):
  - Full SDK implemented — getPricing, computeCost with multi-currency.
  - Fuzzy "Did you mean?" suggestions for model IDs and currency codes.
  - 48 tests across 6 test files, all passing.
  - No CLI — CLI is Python SDK only.
- Project map: tests in tests/*.test.ts mirroring src modules.

## How
Follow the mandatory workflow in AGENTS-docs/workflow.md. In short: plan → review → TDD (failing) → implement (minimal) → verify → report.

### Self-Contained Tasks
Same GitHub workflow as the Python SDK:
1. Create an Issue with `gh issue create`
2. Create a linked branch: `gh issue develop <issue> --checkout`
3. Create a Draft PR: `gh pr create --draft`
4. Begin work following the standard workflow.

Common commands (run from `libraries/typescript/`):
```bash
# Setup
pnpm install

# Build
pnpm build

# Test
pnpm test

# Test with coverage
pnpm test:coverage

# Lint + format check
pnpm lint

# Auto-fix lint/format
pnpm lint:fix

# Type check
pnpm typecheck
```

Policies
- All network calls use native `fetch` (Node 18+ built-in). No axios/got.
- Caching: Pricing data cached for 6h, FX rates cached for 24h via TtlCache.
- Dependencies: Only runtime dep is `fuse.js`. Don't add deps without justification.
- Package manager: `pnpm` only. Always `pnpm install && pnpm update` for fresh installs.
- Build output: ESM + CJS via tsup. Always verify build after source changes.

Public API policy
- Async-only API (no sync wrappers — TS/Node doesn't need them):
  - `getPricing(modelId, currency?)` → `Promise<PricingInfo>`
  - `computeCost(modelId, inputTokens, outputTokens, currency?)` → `Promise<number>`
- Types use camelCase at the public boundary; internal types match raw JSON snake_case.
- Both caches are transparent to callers.

Progressive disclosure
- Workflow and reporting: AGENTS-docs/workflow.md
- Caching rules: AGENTS-docs/caching.md
- Testing guidance: AGENTS-docs/testing.md
- Contribution checklist: AGENTS-docs/checklist.md

Design decisions
- No Token Counting: same rationale as Python SDK.
- Data Source: LLMTracker JSON (same URL as Python SDK).
- `number` not `Decimal`: TS SDK uses native `number` — Python SDK already returns `float` at the boundary.
- No CLI: CLI stays in Python SDK only (already shipped via Click).
- `fuse.js` for fuzzy matching: popular, lightweight, zero deps.
- Custom `TtlCache`: only 2 single-entry caches — no library needed.

What not to do
- Don't fetch more often than needed; rely on cached data.
- Don't add dependencies without justification.
- Don't use package managers other than `pnpm`.
- Don't add sync wrappers or CLI commands.
- Don't write hypey or overly verbose docs.

Credits
- Pricing data: LLMTracker (repo: https://github.com/MrUnreal/LLMTracker, website: https://mrunreal.github.io/LLMTracker/).
