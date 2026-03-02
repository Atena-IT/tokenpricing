# Testing Guidelines (TypeScript SDK)

All work follows TDD: write failing tests before implementation. Use Vitest for test discovery and execution.

## Structure

- `tests/*.test.ts` files mirror `src/` modules
- Prefer small, focused tests over broad integration tests

## HTTP Mocking

- Mock `globalThis.fetch` using `vi.stubGlobal("fetch", mockFetch)`
- Return representative JSON payloads and status codes
- Cover error paths: non-200 responses, malformed payloads
- Always clear mocks in `afterEach` blocks

Example:
```typescript
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

afterEach(() => {
  mockFetch.mockReset();
  clearPricingCache();
});
```

## Cache Testing

- Clear caches in `afterEach` using exported clear functions
- Test cache hit/miss by counting mock fetch calls
- Use injectable `now()` function in TtlCache for TTL tests:
  ```typescript
  let now = 0;
  const cache = new TtlCache(1000, loader, () => now);
  ```
- Test force-refresh bypasses cache

## Running Tests

```bash
# Run all tests
pnpm test

# Watch mode
pnpm test:watch

# With coverage
pnpm test:coverage

# Run a specific test file
pnpm vitest run tests/cache.test.ts
```

## Coverage

- Aim for meaningful coverage on public APIs
- Validate edge cases: missing currencies, unknown models, API failures
- Current: 48 tests across 6 test files
