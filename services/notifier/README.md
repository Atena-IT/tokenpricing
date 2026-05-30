# tokenpricing notifier

Webhook notification service for tokenpricing pricing changes and model lifecycle updates.

## Features

- stores webhook subscriptions in SQLite
- derives a normalized model family from the upstream model identifier
- snapshots pricing data from the Python `tokenpricing` SDK
- detects pricing changes, model additions, removals, and heuristic deprecation-style markers
- signs outgoing webhooks and retries failed deliveries with backoff
- exposes a FastAPI management API plus CLI commands for serving, syncing, and running a worker loop

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Running the API

```bash
uv run notifier serve --db-path ./data/notifier.db --host 127.0.0.1 --port 8000
```

## Running one sync cycle

```bash
uv run notifier sync --db-path ./data/notifier.db --deliver
```

## Running the worker loop

```bash
uv run notifier worker --db-path ./data/notifier.db --poll-interval 21600
```

## Webhook payload

Deliveries include the following headers:

- `X-Tokenpricing-Delivery`
- `X-Tokenpricing-Event`
- `X-Tokenpricing-Timestamp`
- `X-Tokenpricing-Signature`

The signature is an HMAC-SHA256 over `{timestamp}.{raw_json_body}`.

## Model status detection

The notifier infers deprecation status heuristically from upstream text fields because the
current `tokenpricing.modeling.ModelInfo` payload does not expose a dedicated lifecycle or
deprecation field. It currently matches whole-word markers such as `deprecated`, `legacy`,
`retired`, `sunset`, and `EOL`, so false positives and false negatives remain possible when
upstream naming changes.

On a cold start with an empty database, the first sync only seeds the baseline snapshot and
does not emit `MODEL_ADDED` events. Later syncs report changes relative to that stored
baseline.
