# tokenpricing (Python SDK) — AGENTS.md

This file orients AI coding agents working on the Python SDK. Keep it concise, follow progressive disclosure, and always link to detailed docs in AGENTS-docs.

## Why
- Provide up-to-date API pricing math for 1k+ AI models using LLMTracker (updates ~6h).
- Focus on pricing data only — no token counting. For counting, see tokencost.
- Credit LLMTracker in code and docs: repo and website.

## What
- Stack: Python 3.12, `httpx` (async), `async-lru` (TTL), `pydantic` models, `pytest` (+pytest-asyncio), `ruff`, package manager `uv`.
- Key modules:
  - src/tokenpricing/pricing.py — async fetch + 6h TTL cache of LLMTracker JSON.
  - src/tokenpricing/currency.py — USD base rates from JSDelivr currency API with 24h TTL cache.
  - src/tokenpricing/modeling.py — Pydantic models for dataset, search helpers.
  - src/tokenpricing/core.py — public facade exposing async and sync versions of `get_pricing` and `compute_cost`.
  - src/tokenpricing/safeasyncio.py — utilities for safely running async code in sync contexts.
  - src/tokenpricing/__init__.py — exports `get_pricing`, `get_pricing_sync`, `compute_cost`, and `compute_cost_sync`.
- Current state (truth):
  - Pricing fetch + cache implemented.
  - CLI implemented with Click: `tokenpricing pricing` and `tokenpricing cost`.
  - Multi-currency implemented: daily USD base rates cached 24h from JSDelivr currency API.
  - Dual API (async + sync): Both versions share the same underlying async cache via safeasyncio module.
- Project map: see repository tree; tests live in tests/test_*.py.

## How
Follow the mandatory workflow in AGENTS-docs/workflow.md. In short: plan → review → TDD (failing) → implement (minimal) → verify → report.

### Self-Contained Tasks
When a user requests a self-contained task (e.g., a new feature, critical bug fix, significant refactoring, or complex enhancement), follow this GitHub-based workflow:

1. **Create an Issue**: Use the GitHub MCP server or the GitHub CLI (`gh`) to create a detailed issue describing the task, requirements, and expected outcomes.
2. **Create a Linked Branch and Checkout**: Create a branch linked to the issue and checkout: `gh issue develop <issue> --checkout`
3. **Create a Draft PR**: Create a draft pull request with a precise description linking to the issue. Include acceptance criteria and implementation plan. `gh pr create --draft`
4. **Begin Work**: Follow the standard workflow (plan → review → TDD → implement → verify → report) on the feature branch.

This ensures proper tracking, collaboration, and review process for substantial changes.

Common commands (run from `libraries/python/`):
```bash
# Setup
uv sync

# Test
uv run pytest -q

# Format & lint (pre-commit — run from repo root)
uv run pre-commit install
uv run pre-commit run -a
```

Policies
- Async I/O: All network calls are async via `httpx` (or `aiohttp`). No `requests`.
- Caching: Pricing data cached for 6h using async-lru TTL. Do not extend TTL beyond 6h.
- Documentation: Keep README, AGENTS.md (this file) and AGENTS-docs in sync with code behavior.
- Scope: Pricing data library only. Do not add token counting features.

Public API policy
- Expose async and sync versions:
  - Async: `get_pricing(model_id, currency="USD")` and `compute_cost(model_id, input_tokens, output_tokens, currency="USD")`
  - Sync: `get_pricing_sync(model_id, currency="USD")` and `compute_cost_sync(model_id, input_tokens, output_tokens, currency="USD")`
- Both APIs share the same underlying async cache (no duplicate fetches).
- Caching must remain transparent to callers (no cache controls in public API).
- Sync wrappers use safeasyncio module to safely run async code.

Progressive disclosure
- Workflow and reporting: AGENTS-docs/workflow.md
- Caching + async rules (current + planned FX): AGENTS-docs/caching-and-async.md
- CLI spec (planned): AGENTS-docs/CLI-design.md
- Testing guidance (TDD, mocking, TTL): AGENTS-docs/testing-guidelines.md
- Contribution checklist (quality gates): AGENTS-docs/contribution-checklist.md

Design decisions
- No Token Counting: different tokenizers and use-cases make estimates unreliable; https://github.com/AgentOps-AI/tokencost already covers this very well.
- Data Source: LLMTracker JSON at https://raw.githubusercontent.com/MrUnreal/LLMTracker/main/data/current/prices.json
- Multi-currency: USD base via JSDelivr currency API (https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json) cached daily (24h) with uppercased currency tags.
- CLI: implemented with Click; `tokenpricing pricing` and `tokenpricing cost` commands.

What not to do
- Don't fetch more often than needed; rely on 6h cache.
- Don't add dependencies without justification.
- Don't use package managers other than `uv`.
- Don't write hypey or overly verbose docs.

Credits
- Pricing data: LLMTracker (repo: https://github.com/MrUnreal/LLMTracker, data endpoint: https://raw.githubusercontent.com/MrUnreal/LLMTracker/main/data/current/prices.json, website: https://mrunreal.github.io/LLMTracker/).
