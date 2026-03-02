# Caching (TypeScript SDK)

## TtlCache<T>

Both caches use the generic `TtlCache<T>` class in `src/cache.ts`. It stores a single value with a time-to-live. After TTL expires, the next access triggers a fresh fetch.

Key behaviors:
- Deduplicates concurrent calls (only one fetch in-flight at a time)
- Supports `forceRefresh` to bypass the cache
- Supports `clear()` for test isolation
- Accepts an injectable `now()` function for time-controlled tests

## Pricing Data Cache

- Source: LLMTracker prices JSON
- TTL: 6 hours (21600000 ms)
- Module: `src/pricing.ts`
- Clear: `clearPricingCache()` (exported for tests)

## Exchange Rate Cache

- Source: JSDelivr currency API (USD base rates)
- TTL: 24 hours (86400000 ms)
- Module: `src/currency.ts`
- Clear: `clearRatesCache()` (exported for tests)
- Keys are uppercased on fetch

## Rules

- Do not extend TTL beyond specified values
- Failures propagate — no silent fallback to stale data
- Both caches are module-scoped singletons (one per process)
- Always clear caches in test `afterEach` blocks
