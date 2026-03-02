# Testing Guidelines (TDD)

All work follows TDD: write failing tests before implementation. Use pytest for test discovery and execution.

## Structure

- tests/test_*.py files mirror public APIs
- Prefer small, focused tests over broad integration when possible
- Use type hints in tests where helpful to clarify intent

## External API Mocking

- LLMTracker pricing fetches: mock network responses
- forex-python exchange: planned — mock once implemented
- Use `unittest.mock` (patch) or pytest fixtures to inject doubles

### HTTP Mocking (httpx/aiohttp)

- Prefer `httpx.AsyncClient` or `aiohttp` with async tests
- Patch the client method used by the code (e.g., `httpx.AsyncClient.get`)
- Return representative JSON payloads and status codes
- Cover error paths: timeouts, non-200, malformed payload

## Caching Tests

- Pricing cache TTL: 6 hours (implemented)
- FX cache TTL: 24 hours (implemented; USD base rates)
- Strategy:
  - First call: expect underlying provider to be invoked.
  - Subsequent calls within TTL: ensure provider is NOT invoked; return cached result.
  - After TTL: ensure provider is invoked again.
- For time control, prefer designing cache utilities to accept an injectable "now" or clock function; otherwise monkeypatch time source where feasible.

### Currency Cache

- Entry points: `tokenpricing.currency.get_usd_rates()` and `get_usd_rate(currency)`.
- Cache: async-lru with TTL (24h) on the internal cached getter.
- Test pattern:
  - Clear cache with `tokenpricing.currency._get_usd_rates_bucketed.cache_clear()` before each test.
  - Monkeypatch `_sync_get_usd_rates` to track call counts and return a small mapping of `Decimal` rates.
  - Assert only one underlying fetch within the TTL window; subsequent calls re-use the cached object.
  - Verify USD short-circuit: `get_usd_rate('USD')` returns `Decimal('1')` without fetching rates.
- See: [tests/test_currency.py](tests/test_currency.py) for examples.

## Failure-first Tests

- Confirm tests fail for the intended reason (e.g., missing key, incorrect value, uncalled mock)
- Keep the error messages clear; assert on specific behaviors, not broad exceptions

## Running Tests and Quality Checks

```bash
# Run tests
uv run pytest -q

# Re-run a specific test node
uv run pytest tests/test_pricing.py::test_fetch_prices_async -q

# Format and lint (pre-commit)
uv run pre-commit install
uv run pre-commit run -a
```

## Coverage

- Aim for meaningful coverage on public APIs
- Validate edge cases: missing currencies, stale cache, API failures, invalid inputs

## Test Data

- Keep fixtures small and realistic
- Store small JSON payloads inline in tests when clearer; otherwise use dedicated fixture helpers
