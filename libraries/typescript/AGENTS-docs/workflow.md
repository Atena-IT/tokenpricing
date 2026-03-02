# Agent Workflow (TypeScript SDK)

This document defines the mandatory workflow for all agent-driven changes. The core rule: no implementation occurs before plan approval and failing tests exist.

## Required Cycle

1. Plan
   - Propose the smallest viable steps to solve the request
   - Include scope, affected files, risks, test strategy, and success criteria
2. Plan Review
   - Share the plan with the requester
   - Iterate until explicit approval is given
3. TDD First
   - Write or update tests to capture the desired behavior
   - Ensure tests fail for the right reason (red state)
4. Implement
   - Make minimal, focused changes to pass tests (green state)
5. Verify
   - Run: `pnpm lint && pnpm typecheck && pnpm test`
   - Update documentation as needed
6. Report
   - Summarize changes, list updated files, surface follow-ups

## Plan Template

- Context: brief problem statement with links to relevant files
- Goals: what will be achieved and what is explicitly out-of-scope
- Changes: list of intended edits/additions (files and symbols)
- Tests: new/updated tests and target behaviors (failing first)
- Risks: potential pitfalls or compatibility concerns
- Rollback: how to revert if needed

## Guardrails

- Use native `fetch` for all HTTP operations
- Respect cache TTLs (6h for pricing, 24h for FX)
- Keep documentation synchronized with code changes
- Do not add dependencies without strong justification
- Always run `pnpm build` to verify the build after source changes
