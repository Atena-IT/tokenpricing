# tokenpricing sync

Canonical pricing-data sync service for this repository.

## What it does

- fetches raw source catalogs from OpenRouter and LiteLLM
- normalizes them into the tokenpricing schema
- preserves cache-token pricing fields from the forked LLMTracker work
- writes canonical snapshots into `/data/current`, `/data/history`, and `/data/changelog`

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
```

## Run one sync

```bash
uv run tokenpricing-sync sync
```

## Generate from existing raw source files

```bash
uv run tokenpricing-sync normalize
```
