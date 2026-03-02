# Contribution Checklist

Use this checklist before submitting changes. It assumes the Agent Workflow (plan → review → TDD → implement → verify → report).

## Pre-Implementation

- Plan created and approved by requester
- Scope is minimal and clearly defined
- Tests written to fail for the right reason

## Implementation

- Code changes limited to what tests demand
- Type hints added/maintained (Python 3.12+)
- Async I/O used for all network operations
- Caching rules respected (6h pricing, 24h FX)

## Quality

```bash
uv run pre-commit install
uv run pre-commit run -a
uv run pytest -q
```

## Documentation

- README updated if user-facing behavior changed
- LLMTracker credit present where relevant
- No token counting features introduced; reference tokencost when relevant

## Final Report

- Summary of changes and rationale
- Files modified/added
- Tests added/updated and their coverage
- Any follow-ups or open issues
