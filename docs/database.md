# Canonical database

All pricing data lives in the repository under `database/`, normalized from OpenRouter and LiteLLM and refreshed every six hours by the sync service. The SDKs, the CLI, the dashboard, and the notifier all read from these files — there is no separate backend.

## Layout

| Path | Content |
| --- | --- |
| `database/current/prices.json` | The canonical model catalog with current prices (source of truth, committed to git) |
| `database/history/prices-<timestamp>.json` | Immutable snapshots, one per sync |
| `database/changelog/latest.json` | Diff summary of the most recent sync window |
| `database/current/openrouter.json` / `litellm.json` | Raw upstream payloads from the last sync |
| `prices.db` *(CI artifact)* | Full derived SQLite database — all v1 tables including `price_history` — **not committed to git**, published after each sync |
| `prices-current.db` *(CI artifact)* | Slim derived SQLite database — same v1 schema minus `price_history` — **not committed to git**, default for SDK consumers |

Raw access (no authentication required):

```
https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json
https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/changelog/latest.json
```

## SQLite artifact (`prices.db`)

`prices.db` is a derived, read-only SQLite database built from the canonical JSON after every sync run. It follows the v1 schema described in [ADR 0001](https://github.com/Atena-IT/tokenpricing/blob/main/wiki/decisions/0001-canonical-pricing-database-storage.md) and includes:

- `models` — full catalog with indexes on `provider`, `category`, `model_type`
- `providers` — provider metadata
- `model_sources` — per-source provenance (OpenRouter / LiteLLM)
- `price_history` — time-series pricing from all history snapshots
- `models_fts` — FTS5 full-text index over `model_id` and `display_name`

The databases are excluded from git (binary changes every 6 hours would bloat history). They are published as a **rolling GitHub Release** (`database-latest`) on every sync, giving stable download URLs. Two variants are built — pick the one that matches your workload:

| Asset | Contents | Primary consumer |
| --- | --- | --- |
| [`prices.db`](https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices.db) | Full database **including `price_history`** | Dashboard / history charts |
| [`prices-current.db`](https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices-current.db) | Slim database **without `price_history`** (smaller download) | Python SDK (default) and other SDK consumers |

Both share the identical v1 schema (`PRAGMA user_version = 1`); the slim variant simply omits the `price_history` table and its index. Both are also attached to each `database-sync` workflow run as the `prices-db` artifact. To build them locally from the committed JSON:

```bash
cd services/sync
uv run tokenpricing-sync build-db   # writes prices.db and prices-current.db
```

## Model record

```json
{
  "provider": "anthropic",
  "model_id": "anthropic/claude-opus-4",
  "display_name": "Anthropic: Claude Opus 4",
  "pricing": {
    "input_per_million": 15.0,
    "output_per_million": 75.0,
    "cache_read_per_million": 1.5,
    "cache_creation_per_million": 18.75,
    "currency": "USD"
  },
  "context_window": 200000,
  "max_output_tokens": 32000,
  "model_type": "text",
  "supports_vision": true,
  "supports_function_calling": true,
  "supports_streaming": true,
  "category": "flagship",
  "sources": { "openrouter": { "...": "..." } }
}
```

## Model types

`model_type` follows the OpenRouter output-modality taxonomy:

| Type | Meaning |
| --- | --- |
| `text` | Chat / completion language models |
| `image` | Image generation and editing |
| `embeddings` | Vector embedding models |
| `audio` | General audio models |
| `video` | Video generation |
| `rerank` | Search-result reranking |
| `speech` | Text-to-speech |
| `transcription` | Speech-to-text |

`category` is an editorial tier: `budget`, `standard`, or `flagship`.

## Changelog

`database/changelog/latest.json` summarizes the latest sync window with per-model change entries typed as `model_added`, `model_removed`, `pricing_changed`, or `cache_price_changed` — the same events the [notifier](/notifications) delivers to webhooks, and what the dashboard's Changelog tab renders.

## Browsing

The [live dashboard](https://atena-it.github.io/tokenpricing/) provides a sortable explorer over the full catalog, two-model comparison, a cost calculator, price history charts built from the snapshots, and the changelog.
