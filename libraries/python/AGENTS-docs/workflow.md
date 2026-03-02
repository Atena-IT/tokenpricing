# Agent Workflow

This document defines the mandatory workflow for all agent-driven changes in this repository. The core rule: no implementation occurs before plan approval and failing tests exist.

## Required Cycle

1. Plan
   - Propose the smallest viable steps to solve the request
   - Include scope, affected files, risks, test strategy, and success criteria
   - Keep it concise and verifiable
2. Plan Review
   - Share the plan with the requester
   - Iterate until explicit approval is given
   - Do not touch implementation before approval
3. TDD First
   - Write or update tests to capture the desired behavior
   - Ensure tests fail for the right reason (red state)
4. Implement
   - Make minimal, focused changes to pass tests (green state)
   - Maintain style, type hints, and architecture constraints
5. Verify
   - Run formatting and linting
   - Re-run full test suite
   - Update documentation as needed
6. Report
   - Summarize changes, list updated files, surface follow-ups
   - If more work is needed, return to Plan with a refined proposal

## Plan Template

- Context: brief problem statement with links to relevant files
- Goals: what will be achieved and what is explicitly out-of-scope
- Changes: list of intended edits/additions (files and symbols)
- Tests: new/updated tests and target behaviors (failing first)
- Risks: potential pitfalls or compatibility concerns
- Rollback: how to revert if needed

## Review Protocol

- The requester must explicitly approve the plan before any code changes
- Major deviations from the approved plan require a new review
- Summaries should be concise and link to files/sections for easy scanning

## Reporting Checklist

- What changed and why
- Files modified/added (with links)
- Tests added/updated and their scope
- Any decisions/trade-offs
- Next steps or open questions

## Example

Request: "Add currency option to CLI output"

- Plan: Update CLI parser to accept --currency, validate ISO code, convert using cached forex rates, update examples in README; tests for CLI parsing and conversion
- Review: Get approval
- TDD: Add failing tests for CLI flag and currency output
- Implement: Minimal changes to CLI and currency wrapper
- Verify: Run tests, ruff, and update README examples
- Report: Summarize changes and confirm behavior

## Guardrails

- Adhere to async I/O for all network operations
- Respect cache TTLs (6h for pricing, 24h for FX)
- Keep documentation synchronized with code changes
- Do not add dependencies without strong justification
