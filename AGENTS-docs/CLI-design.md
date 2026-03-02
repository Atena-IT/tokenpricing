# CLI Design (planned)

Status: CLI shipped with Click. Commands: `price` and `cost` as specified below.

## Requirements

- Console script entry in pyproject when implemented.
- Query by model id; optional `--provider` to disambiguate names.
- Output input/output prices; default USD.
- Optional `--currency EUR` using cached forex rates (when FX exists).
- Human-friendly default output; optional `--json` for scripting.

## Framework

- Prefer `typer` for fast, typed CLIs; `click` acceptable.
- Commands discoverable via `--help` with clear error messages.

## Example UX

```bash
# Price for a model in USD (default)
tokenpricing pricing openai/gpt-4o

# Price converted to EUR (when FX is implemented)
tokenpricing pricing openai/gpt-4o --currency EUR

# Disambiguate by provider
tokenpricing pricing anthropic/command-r+

# JSON output for scripting
tokenpricing pricing openai/gpt-4o --json

# Compute cost for a usage
tokenpricing cost openai/gpt-4o --in 1000 --out 500 --currency EUR
```

## Behavior

- All network ops are async; wrap async in the CLI entry point.
- Respect caches (6h pricing, 24h FX when available).
- Clear errors for unknown model/provider/currency.

## Acceptance Criteria

- End-to-end tests for parsing and output (mocking network/FX).
- Graceful errors and helpful usage text.
- Minimal dependencies; follows project policies in AGENTS.md.
