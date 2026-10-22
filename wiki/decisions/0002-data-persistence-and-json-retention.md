# ADR 0002: Data persistence and JSON retention

- **Status:** Proposed
- **Date:** 2026-06-27
- **Deciders:** tokenpricing maintainers
- **Tracking issue:** [#60](https://github.com/Atena-IT/tokenpricing/issues/60)
- **Relates to:** [ADR 0001](0001-canonical-pricing-database-storage.md) (resolves its deferred Phase 4 question)

## Context

ADR 0001 added a derived SQLite read layer (slim `prices-current.db` for SDKs,
full `prices.db` for the web platform) published to a rolling GitHub Release,
while keeping the JSON files as the git-committed source of truth. It
explicitly **deferred** one question: should JSON eventually be retired in
favour of SQLite? Phases 0–2 (build/publish, dashboard read path, Python + TS
SDK backends) have now shipped, so that question is answerable.

Two facts shape this decision:

1. **The full DB's `price_history` is derived from `database/history/*.json`.**
   The sync writes one **full-catalog** snapshot per run (~2.8 MB each, ≤42
   retained ⇒ ~115 MB of churn) and `build_db` reads them to populate the
   time-series. History lives in git as full snapshots; the DB is just a view
   over them.
2. **The dashboard cannot read the release DB in a browser.** GitHub release
   assets are not reliably CORS- or `Range`-accessible from a browser, so the
   dashboard's SQLite path falls back to JSON today. Its history charts still
   fetch up to **12 × ~2.8 MB** full snapshots via the GitHub contents API.

The maintainer has stated that a "proper persistence mechanism" for data
ingestion is a deliberate future decision, and that the GitHub Pages publish
can wait. This ADR records what we decide **now** and what we explicitly defer.

## Decision drivers

- Reviewability: the 6-hourly JSON pricing diff is a feature, not an accident.
- Git bloat: ~115 MB of rewritten full snapshots is the dominant cost.
- Web-UI latency: the history charts' multi-snapshot fetch is the largest
  remaining client cost.
- No always-on infrastructure (the project has no backend, by design).
- Keep heavy/irreversible persistence moves (Pages, external store) as a
  separate, deliberate future step.

## Decisions

1. **JSON stays the canonical, committed source of truth — indefinitely.**
   `database/current/prices.json` remains the reviewable origin; the SQLite
   databases remain derived, published artifacts. JSON is **not** retired.
   This resolves ADR 0001's deferred question.

2. **SQLite remains a derived read layer** (no change): slim for SDKs, full for
   the web platform, published to the `database-latest` release.

3. **History representation is the real persistence problem, and it is split
   into a near-term step and a deferred step.**
   - *Deferred (the "proper persistence mechanism"):* serving the full DB to
     browsers via **GitHub Pages** (unlocking the dashboard's in-browser SQLite
     path and `Range` streaming), and/or an **external managed store**. These
     are not pursued now, per the maintainer.
   - *Near-term (this ADR's proposal, see below):* reduce the history
     representation so it stops being the source of git bloat and the
     dashboard's slow path — **without** new infrastructure.

## History layout — options considered

| Option | What | Infra | Git churn | Browser history charts |
| --- | --- | --- | --- | --- |
| Status quo | N full-catalog snapshots | none | ~115 MB | 12 × 2.8 MB fetch |
| **A. Compact time-series JSON** | One committed `price-history.json` of per-model price points | none | small | one small fetch |
| B. History out of main repo | Orphan branch / git-LFS / data repo | low | moved out | needs a fetch path |
| C. Pages-served full DB | `sql.js-httpvfs` range reads | low-med | n/a | range queries |
| D. External managed store | Object storage / hosted DB | **breaks "no backend"** | n/a | API queries |

**Recommendation:** adopt **Option A** as the near-term move and let the same
compact artifact feed both `build_db`'s `price_history` table and the dashboard
charts. It keeps the "committed, reviewable, no backend" model, collapses the
~115 MB snapshot churn, and removes the dashboard's multi-snapshot fetch — all
without depending on the deferred Pages/external-store work. C and D remain the
longer-term "proper persistence" direction and are tracked, not chosen.

A sub-question for Option A — whether the compact artifact **replaces** the full
per-run snapshots or is published **alongside** them — is the implementation
choice for Phase 3 and is decided with the maintainer before that work lands.

## Consequences

- **Positive:** the JSON-retention question is closed (keep it); a clear,
  infra-free path exists to cut git bloat and speed the history charts; the
  heavier persistence options are explicitly scoped as future work rather than
  blocking Phase 3.
- **Negative / deferred:** the dashboard's in-browser SQLite path stays dormant
  (JSON fallback) until Pages or an external store lands; if Option A replaces
  the full snapshots, the per-run full-catalog history granularity is traded
  for per-model price points (acceptable — the charts only need prices over
  time).
- **Follow-up:** a future ADR will record the chosen "proper persistence
  mechanism" (Pages and/or external store) when the maintainer takes it on.
