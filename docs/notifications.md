# Webhook notifications

The notifier service watches the canonical database and delivers webhook events when prices move or models change lifecycle state. It lives in the repository under `services/notifier` and stores its state in SQLite (default `~/.tokenpricing/notifier.db`).

## Run the service

```bash
cd services/notifier
uv sync --group dev
uv run notifier serve --host 127.0.0.1 --port 8000
```

Two companion commands handle polling:

```bash
uv run notifier sync --deliver    # one polling cycle, then flush pending deliveries
uv run notifier worker            # long-running poller (default interval: 6 hours)
```

## Create a subscription

```bash
curl -X POST http://127.0.0.1:8000/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://example.com/hooks/tokenpricing",
    "description": "Anthropic price moves",
    "filters": {
      "provider": "anthropic",
      "event_types": ["pricing_changed", "cache_price_changed", "model_deprecated", "model_removed"]
    }
  }'
```

The response includes the subscription `id` and a `secret` used to sign deliveries — store it.

### Filters

All filter fields are optional; omitted fields match everything.

| Field | Example | Notes |
| --- | --- | --- |
| `model_id` | `anthropic/claude-opus-4` | Exact model |
| `provider` | `anthropic` | Provider slug |
| `model_family` | `claude` | Family grouping |
| `model_type` | `text` | OpenRouter taxonomy: `text`, `image`, `embeddings`, `audio`, `video`, `rerank`, `speech`, `transcription` |
| `category` | `flagship` | `budget`, `standard`, `flagship` |
| `supports_vision` | `true` | Capability flags |
| `supports_function_calling` | `true` | |
| `event_types` | see below | Defaults to pricing, cache, deprecation, and removal events |

### Event types

`pricing_changed` · `pricing_increased` · `pricing_decreased` · `cache_price_changed` · `model_added` · `model_deprecated` · `model_removed`

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/subscriptions` | List subscriptions |
| `POST` | `/subscriptions` | Create a subscription |
| `GET` | `/subscriptions/{id}` | Fetch one |
| `PATCH` | `/subscriptions/{id}` | Update URL, status, or filters |
| `DELETE` | `/subscriptions/{id}` | Delete |
| `POST` | `/subscriptions/{id}/test` | Send a test delivery |
| `POST` | `/subscriptions/{id}/verify` | Verify reachability |
| `POST` | `/subscriptions/{id}/rotate-secret` | Rotate the signing secret |
| `POST` | `/sync` | Trigger one polling cycle |
| `POST` | `/deliveries/flush` | Flush pending deliveries |
| `GET` | `/events` | Recent detected events |
| `GET` | `/deliveries` | Recent delivery attempts |

## Verify deliveries on your endpoint

Every delivery is HMAC-SHA256 signed. Headers:

| Header | Content |
| --- | --- |
| `X-Tokenpricing-Delivery` | Delivery id |
| `X-Tokenpricing-Event` | Event type |
| `X-Tokenpricing-Timestamp` | ISO timestamp used in the signature |
| `X-Tokenpricing-Signature` | `sha256=<hexdigest>` |

The signature covers `"{timestamp}." + body`, keyed with the subscription secret:

```python
import hashlib, hmac

def is_valid(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    message = f"{timestamp}.".encode() + body
    expected = "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Delivery guarantees

Failed deliveries are retried with backoff (immediately, then 1 m, 5 m, 30 m, 2 h) up to 5 attempts before being dead-lettered. A 2xx response from your endpoint marks the delivery as sent.
