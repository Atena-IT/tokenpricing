# Canonical database

All pricing data lives in the repository under `database/`, normalized from OpenRouter and LiteLLM and refreshed every six hours by the sync service. The SDKs, the CLI, the dashboard, and the notifier all read from these files — there is no separate backend.

## Layout

| Path | Content |
| --- | --- |
| `database/current/prices.json` | The canonical model catalog with current prices |
| `database/history/prices-<timestamp>.json` | Immutable snapshots, one per sync |
| `database/changelog/latest.json` | Diff summary of the most recent sync window |
| `database/current/openrouter.json` / `litellm.json` | Raw upstream payloads from the last sync |
| `database/current/artificial-analysis.json` | Artificial Analysis provider × model dataset, refreshed weekly |
| `database/history/artificial-analysis-<timestamp>.json` | Immutable weekly snapshots |

Raw access (no authentication required):

```
https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json
https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/changelog/latest.json
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

## Artificial Analysis dataset

`database/current/artificial-analysis.json` is a separate weekly dataset covering
each model **as served by each provider** — 1045 offerings across 51 providers —
joined to the Artificial Analysis Openness Index.

> **Data source: [Artificial Analysis](https://artificialanalysis.ai).** Benchmark,
> latency and throughput figures are third-party measurements produced by
> Artificial Analysis; they are not vendor-published and are not measured by
> tokenpricing. Openness Index values follow the Artificial Analysis Openness Index
> specification (V1.0, preliminary draft).

It is kept separate from `prices.json` rather than merged into it because the grain
differs (one row per model × reasoning variant × serving platform, versus one
record per model) and because the public Artificial Analysis pages publish
`Cost per Task USD` but no per-token input/output pricing. Each offering links back
by `model_slug`, `display_name` and `creator`.

Models with no Openness Index entry keep `openness: null` and are listed under
`unmatched`; genuinely undecidable matches are listed under `ambiguous`. Neither is
silently dropped, and absent openness never becomes zero. See the
[service README](https://github.com/Atena-IT/tokenpricing/blob/main/services/aa-sync/README.md)
for the matching rules.

## Browsing

The [live dashboard](https://atena-it.github.io/tokenpricing/) provides a sortable explorer over the full catalog, two-model comparison, a cost calculator, price history charts built from the snapshots, and the changelog.
