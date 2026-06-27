# Architecture decision records

This directory holds Architecture Decision Records (ADRs) — short documents
that capture a significant architectural choice, the context that forced it,
the options weighed, and the consequences.

Each ADR is immutable once **Accepted**. To change a decision, add a new ADR
that supersedes the old one (and update the old one's status to *Superseded*).

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-canonical-pricing-database-storage.md) | SQLite read layer for the canonical pricing database | Proposed |

## Format

`NNNN-short-title.md` with sections: Status, Context, Decision drivers,
Considered options, Decision, Consequences.
