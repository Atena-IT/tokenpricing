# Caching and Async I/O

This project requires strict caching rules and async HTTP for all network operations.

Status summary
- Pricing cache: implemented (6h TTL using async-lru's TTL).
- FX cache: implemented (24h USD base rates via JSDelivr API, cached with async-lru TTL).

## Pricing Data Cache (implemented)

- Source: LLMTracker prices JSON
- TTL: 6 hours (aligned with upstream update frequency)
- Behavior:
  - Cache successful fetches for 6 hours using async-lru TTL.
  - If a fetch fails, bubble up the error; do not fabricate data.
  - Validate payload shape before caching (Pydantic models).

## Exchange Rate Cache (implemented)

- Source: JSDelivr currency API (USD base rates map)
- TTL: 24 hours (API updates daily)
- Behavior:
  - Cache the USD base rates dictionary for 24h via async-lru TTL; keys uppercased.
  - Failures propagate; no silent fallback to unknown data.
  - Tests cover cache hit/miss and TTL expiry.

## Async HTTP Requirements

- Use `httpx` (AsyncClient) or `aiohttp`; never blocking `requests`.
- Set explicit timeouts and handle non-200 responses.
- Optional: limited retries with backoff for transient errors (no infinite retries).
- All I/O functions are `async` and documented as such.

## Concurrency and Safety

- Guard cache invalidation to avoid race conditions.
- Prefer per-process in-memory caches with TTL; document invalidation behavior.
- Avoid leaking global mutable state; encapsulate caches in modules.

## Testing Guidance

- Mock HTTP clients and forex-python; no real network calls in tests.
- Validate TTL behavior by controlling the time source (injectable clock or monkeypatch).
- Cover failure modes: timeouts, malformed payloads, provider errors.
