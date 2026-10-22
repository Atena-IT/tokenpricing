# ADR 0001: Add a SQLite read layer for the canonical pricing database

- **Status:** Proposed
- **Date:** 2026-06-27
- **Deciders:** tokenpricing maintainers
- **Tracking issue:** [#60](https://github.com/Atena-IT/tokenpricing/issues/60)
- **Supersedes:** —

## Context

Today the canonical pricing data is a set of JSON files committed to the
repository and served as static files over the GitHub raw CDN:

| Path | Size | Role |
| --- | --- | --- |
| `database/current/prices.json` | ~2.9 MB | Canonical catalog, 3,244 models |
| `database/current/openrouter.json` / `litellm.json` | ~2.3 MB | Raw upstream payloads |
| `database/history/prices-<ts>.json` | ~2.8 MB each, ≤42 kept (~115 MB) | Immutable per-sync snapshots |
| `database/changelog/latest.json` | <1 KB | Last sync's diff summary |

Every consumer reads these files directly — there is no backend
(`docs/database.md`: "there is no separate backend"). The
[sync service](../../services/sync/) regenerates them every six hours and a
GitHub Action commits the result.

This is simple, transparent, and diff-reviewable, but it forces every read to
materialize the **entire** dataset:

- **Web UI (dashboard).** `services/dashboard/src/lib/data.ts` fetches the full
  2.9 MB `prices.json` on mount, parses it, and `explorer.tsx` filters the
  3,244-row array on **every keystroke** (`O(n)` substring scan, no index).
  Price-history charts fetch up to **12 × 2.8 MB** snapshots via the GitHub
  contents API (`loadHistorySnapshots`, `history.tsx`).
- **SDKs / server-side ("web server").** `libraries/python` and
  `libraries/typescript` fetch and parse the full 2.9 MB blob on first use
  (~100–200 ms parse), cache it in memory for 6 h, then run `search_models`
  as an `O(n)` linear scan over all models with no indexing
  (`modeling.py:search_models`, `core.ts`).
- **Sync.** Each cycle deserializes the full previous 2.9 MB snapshot to diff
  it (`services/sync/.../cli.py` → `diff.py`), and writes a fresh 2.8 MB
  history file that git stores as a brand-new blob.

The data is small in row count (3,244) but large in payload because each read
is "download + parse everything to answer one question." The bottleneck is
**payload and parse**, not CPU on the math itself (cost computation is already
trivial multiplication).

## Decision drivers

- Faster cold loads and queries in the dashboard and SDK consumers.
- Indexed / range / full-text queries instead of `O(n)` array scans.
- Keep pricing changes **reviewable in pull requests** (the 6-hourly sync
  commit is currently a readable JSON diff — this is a feature, not an accident).
- Avoid bloating git history with a 3 MB binary that changes every 6 hours.
- No new always-on infrastructure (the project intentionally has no backend).
- Backward compatibility: published packages and external scripts already
  depend on the raw JSON URLs.

## Considered options

### Option A — Replace JSON with a committed SQLite binary (`prices.db` in git)

Make `database/current/prices.db` the single source of truth and stop
committing JSON.

- ➕ One artifact; "local database" in the most literal sense.
- ➖ **Binary is not diff-reviewable** — the readable 6-hourly pricing diff is
  lost, and the notifier/changelog story leans on that reviewability.
- ➖ A ~3 MB binary that fully rewrites every 6 hours **bloats git history**
  unboundedly (git can't delta binary SQLite pages well).
- ➖ Breaks every existing consumer of the raw JSON URLs at once.

### Option B — Keep JSON canonical; add a **derived, published** SQLite artifact (recommended)

JSON stays the git-committed source of truth (diff-reviewable, unchanged URLs).
The sync pipeline **additionally** builds `prices.db` from the JSON and
publishes it as a build artifact — to GitHub Pages alongside the dashboard and
to GitHub Releases — **without committing the binary to git**. Clients gain a
fast SQLite read path; the JSON path remains as the compatibility fallback.

- ➕ Keeps reviewable JSON diffs and stable public URLs.
- ➕ No binary in git history (built in CI, published as an asset).
- ➕ Enables the real wins (below) for both the UI and SDKs.
- ➕ Migration is incremental and reversible at each phase.
- ➖ Adds a build/publish step and a second artifact to keep in sync.
- ➖ Two read paths to maintain during the transition.

### Option C — Stand up a query backend (Postgres / hosted API)

- ➕ Most flexible querying.
- ➖ Introduces always-on infrastructure, hosting cost, and an availability
  surface the project deliberately avoids. Overkill for 3,244 rows.

## Decision

Adopt **Option B**. Keep the JSON files as the canonical, git-committed,
diff-reviewable source of truth. Extend the sync pipeline to build a derived
**SQLite** database (`prices.db`) from that JSON and publish it as a CI
artifact. Migrate read-heavy consumers (dashboard first, then the SDKs and
history charts) to query the SQLite artifact over HTTP, keeping the JSON path
as a fallback for at least one release after each consumer migrates.

The question of whether JSON is *eventually* retired in favor of SQLite is
**explicitly deferred** to a future ADR, to be revisited only after Option B
has shipped and the reviewability concern has a concrete answer (e.g. a
JSON-export diff bot). The current recommendation is to keep JSON indefinitely
as the source of truth.

## Why SQLite makes computation "way faster"

- **Partial reads via HTTP range requests.** With
  [`sql.js-httpvfs`](https://github.com/phiresky/sql.js-httpvfs) (and `Range`
  support on GitHub Pages / raw), the browser and any HTTP client fetch **only
  the database pages a query touches** instead of the whole 2.9 MB file. A
  single-model lookup or a filtered query reads tens of KB, not megabytes.
- **Indexes instead of scans.** Indexes on `provider`, `category`,
  `model_type` and an **FTS5** virtual table over `model_id` + `display_name`
  turn the dashboard's per-keystroke `O(n)` filter and the SDK's `search_models`
  scan into `O(log n)` / index-backed queries.
- **No cold-start parse.** SDK consumers that ship `prices.db` locally skip the
  100–200 ms full-JSON parse entirely; SQLite memory-maps the file.
- **History as a time series.** A single `price_history` table replaces the
  ≤42 × 2.8 MB snapshot files (115 MB). History charts run one indexed query
  instead of fetching 12 multi-MB snapshots through the GitHub API.

## Proposed schema (v1)

```sql
PRAGMA user_version = 1;            -- schema version

CREATE TABLE meta (                 -- one row
  generated_at  TEXT NOT NULL,
  total_models  INTEGER NOT NULL,
  schema_version INTEGER NOT NULL
);

CREATE TABLE providers (
  provider      TEXT PRIMARY KEY,
  name          TEXT,
  website       TEXT,
  pricing_page  TEXT,
  affiliate_link TEXT
);

CREATE TABLE models (
  model_id      TEXT PRIMARY KEY,
  provider      TEXT NOT NULL REFERENCES providers(provider),
  display_name  TEXT NOT NULL,
  input_per_million          REAL,
  output_per_million         REAL,
  cache_read_per_million     REAL,
  cache_creation_per_million REAL,
  currency      TEXT NOT NULL DEFAULT 'USD',
  context_window    INTEGER,
  max_output_tokens INTEGER,
  model_type    TEXT,
  category      TEXT,
  supports_vision           INTEGER,  -- 0/1
  supports_function_calling INTEGER,
  supports_streaming        INTEGER
);
CREATE INDEX idx_models_provider   ON models(provider);
CREATE INDEX idx_models_category   ON models(category);
CREATE INDEX idx_models_model_type ON models(model_type);

CREATE TABLE model_sources (        -- per-source provenance
  model_id  TEXT NOT NULL REFERENCES models(model_id),
  source    TEXT NOT NULL,          -- 'openrouter' | 'litellm'
  price_input          REAL,
  price_output         REAL,
  price_cache_read     REAL,
  price_cache_creation REAL,
  last_updated TEXT,
  PRIMARY KEY (model_id, source)
);

CREATE TABLE price_history (        -- replaces database/history/*.json
  generated_at TEXT NOT NULL,
  model_id     TEXT NOT NULL,
  input_per_million          REAL,
  output_per_million         REAL,
  cache_read_per_million     REAL,
  cache_creation_per_million REAL,
  PRIMARY KEY (generated_at, model_id)
);
CREATE INDEX idx_history_model ON price_history(model_id, generated_at);

CREATE VIRTUAL TABLE models_fts USING fts5(  -- search / suggestions
  model_id, display_name, content='models', content_rowid='rowid'
);
```

Notes:
- Prices are stored as `REAL` to preserve the exact float semantics the JSON
  schema and SDKs already use; currency conversion stays in the SDK layer
  (unchanged). If the team prefers exact decimals, store as `TEXT` and parse —
  resolve during Phase 0.
- `PRAGMA user_version` carries the schema version so clients can refuse an
  incompatible DB and fall back to JSON.
- The DB is shipped pre-`VACUUM`ed and `ANALYZE`d for compact, query-planned
  reads.

## Consequences

**Positive**
- Dashboard cold load drops from ~2.9 MB to tens of KB; filtering/search become
  indexed and instant.
- SDK `search_models` and history queries become index-backed.
- History storage shrinks from ~115 MB of snapshot files to one time-series
  table; sync can diff via SQL instead of re-parsing the prior full snapshot.
- Public JSON URLs and existing consumers keep working unchanged.

**Negative / costs**
- A new CI build+publish step and a second artifact to validate each sync.
- Two read paths (JSON + SQLite) coexist during the transition.
- `sql.js-httpvfs` depends on HTTP `Range` support of the hosting origin —
  **must be verified** for GitHub Pages and `raw.githubusercontent.com` in
  Phase 0 (fall back to a single `.db` download + in-browser query if ranges
  are unreliable).
- Schema versioning and a JSON↔DB equivalence test become permanent
  maintenance items.

## Publish target (resolved)

The derived databases are published as a **rolling GitHub Release** under the
fixed tag `database-latest`, refreshed on every sync. This gives consumers
stable, unauthenticated download URLs without committing a binary to git.

Two variants are published, because the full history is valuable to the web
platform but pure overhead for SDK lookups:

| Asset | Contents | Size (approx.) | Primary consumer |
| --- | --- | --- | --- |
| `prices.db` | Full schema incl. `price_history` | ~30 MB | Dashboard / history charts |
| `prices-current.db` | Slim schema, no `price_history` | a few MB | Python SDK (default), SDK consumers |

```
https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices.db
https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices-current.db
```

Both carry the identical v1 schema (`PRAGMA user_version = 1`); the slim
variant omits only the `price_history` table and its index, so it is a drop-in
for any consumer that does not query history. The release is created with
`make_latest: false` so it never displaces the SDK package releases as the
repository's "latest" release. Both files are also uploaded as a
short-retention workflow artifact for debugging.

This split is an interim optimization for the static-hosting model. The longer
term direction is to move ingestion to a more resilient store. GitHub Pages
remains the near-term option specifically to unlock HTTP range-request
streaming (`sql.js-httpvfs` chunked mode) and browser-side use of the full DB
(release assets are not reliably CORS- or `Range`-accessible from a browser),
which is what the dashboard needs to actually read SQLite rather than falling
back to JSON.

## Rollout

Phasing, owners, and acceptance criteria live in the migration tracking issue.
At a high level: (0) build + publish `prices.db` in sync, non-breaking;
(1) dashboard reads SQLite with JSON fallback; (2) SDKs gain an optional SQLite
backend; (3) history charts + sync diffing move to the DB; (4) revisit JSON
retention in a follow-up ADR.
