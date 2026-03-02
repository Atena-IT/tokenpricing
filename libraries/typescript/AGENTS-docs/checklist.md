# Contribution Checklist (TypeScript SDK)

Use this checklist before submitting changes.

## Pre-Implementation

- [ ] Plan created and approved by requester
- [ ] Scope is minimal and clearly defined
- [ ] Tests written to fail for the right reason

## Implementation

- [ ] Code changes limited to what tests demand
- [ ] TypeScript strict mode — no `any` without justification
- [ ] Native `fetch` for all HTTP operations
- [ ] Caching rules respected (6h pricing, 24h FX)

## Quality

```bash
pnpm lint        # Biome check
pnpm typecheck   # tsc --noEmit
pnpm test        # Vitest
pnpm build       # tsup (ESM + CJS)
```

All four must pass before submitting.

## Documentation

- [ ] README updated if user-facing behavior changed
- [ ] AGENTS.md updated if module map or API changed
- [ ] LLMTracker credit present where relevant
- [ ] No token counting features introduced

## Final Report

- [ ] Summary of changes and rationale
- [ ] Files modified/added
- [ ] Tests added/updated and their coverage
- [ ] Any follow-ups or open issues
