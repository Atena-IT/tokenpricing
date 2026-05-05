---
name: tokenpricing
description: Query live LLM token pricing and compute workload cost from known token counts. Use when the user asks what a model costs per 1M tokens, wants to compare model pricing across providers or currencies, or needs total spend for a workload with known input/output token counts. This skill shells out to the tokenpricing CLI. Do not use it for counting tokens from raw text, subscription or invoice questions, or billing topics that are not model-pricing math. Triggers include "what does openai/gpt-5.2 cost", "compare Claude and GPT pricing in EUR", "what would 250000 input and 40000 output tokens cost", or "show me machine-readable pricing for this model".
allowed-tools: Bash(tokenpricing:*), Bash(uv run --project libraries/python tokenpricing:*)
hidden: true
---

# tokenpricing

**Use when** you need live model pricing or total cost math from known input and output token counts.

**Do not use** for token counting from raw text, subscription or invoice questions, or generic billing support. If token counts are missing, ask for them or suggest a tokenizer first.

## Before you start

- In this repository, prefer `uv run --project libraries/python tokenpricing ...`.
- Outside this repository, use the installed `tokenpricing ...` command.
- Prefer `--json` when you need to compare models, reason over numeric output, or chain multiple CLI calls.
- If the user asks for total cost, make sure both input and output token counts are known before calling `cost`.

## Core commands

### Pricing lookup

```bash
tokenpricing pricing MODEL --currency CODE --json
uv run --project libraries/python tokenpricing pricing MODEL --currency CODE --json
```

### Workload cost

```bash
tokenpricing cost MODEL --in INPUT_TOKENS --out OUTPUT_TOKENS --currency CODE --json
uv run --project libraries/python tokenpricing cost MODEL --in INPUT_TOKENS --out OUTPUT_TOKENS --currency CODE --json
```

## Recommended workflow

1. Confirm the model ID and target currency if the user did not provide them.
2. Use `pricing --json` for per-model price lookups.
3. Use `cost --json` only when the user has provided both input and output token counts.
4. When comparing models, run pricing lookups in the same currency before summarizing the differences.
5. Present the final answer with the model, currency, and numeric result rather than pasting raw JSON unless the user asked for it.

## Output guidance

- Do not invent token counts or estimate them from prompts, chats, or documents.
- Normalize comparisons to a single currency.
- Preserve the exact model identifiers returned by the user or CLI.
- If the CLI returns a helpful "Did you mean" suggestion for a model or currency, surface that suggestion instead of guessing.
