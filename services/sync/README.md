# tokenpricing sync

Canonical pricing database sync service for this repository.

## What it does

- fetches raw source catalogs from OpenRouter and LiteLLM
- normalizes them into the tokenpricing schema
- preserves cache-token pricing fields from the forked LLMTracker work
- writes canonical snapshots into `database/current`, `database/history`, and `database/changelog`
- builds a derived SQLite database (`prices.db`) from the canonical JSON (see ADR 0001)

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

## Build the SQLite database

```bash
uv run tokenpricing-sync build-db
```

This reads `database/current/prices.json` and all history snapshots in
`database/history/` and materializes `database/current/prices.db` following
the v1 schema from ADR 0001. The `.db` file is a **derived artifact** — it is
excluded from git and published by CI as a workflow artifact after each sync.
