# tokenpricing-aa-sync

Daily acquisition of [Artificial Analysis](https://artificialanalysis.ai) public
leaderboard data: a provider x model offering dataset joined to the Artificial
Analysis Openness Index.

> **Data source: Artificial Analysis (https://artificialanalysis.ai).**
> Benchmark, latency and throughput figures in this dataset are third-party
> measurements produced by Artificial Analysis — they are not vendor-published and
> are not measured by tokenpricing. Openness Index values follow the Artificial
> Analysis Openness Index specification (V1.0, marked preliminary draft).

## Usage

```bash
uv sync
uv run tokenpricing-aa-sync sync            # fetch, capture, check shape, write
uv run tokenpricing-aa-sync normalize       # rebuild from the local raw capture
uv run tokenpricing-aa-sync check           # compare live payload to the manifest
uv run tokenpricing-aa-sync build-manifest  # accept a new payload shape
```

Outputs:

| Path | What |
|---|---|
| `database/current/artificial-analysis.json` | latest dataset |
| `database/history/artificial-analysis-<ts>.json` | snapshot (26 retained) |
| `.capture/artificial-analysis/*.json` | raw HTML capture — gitignored, uploaded as a CI artifact |
| `schema/offering-manifest.json` | expected payload shape, tracked in git |

Scheduled daily by [`.github/workflows/aa-sync.yml`](../../.github/workflows/aa-sync.yml).

## Where the data comes from

**Two `GET`s, no browser.** Artificial Analysis is a Next.js app: every page
streams its server-rendered data into the initial HTML as a sequence of
`self.__next_f.push([1,"…"])` chunks. Concatenating those chunks reconstructs a
flight payload holding the full dataset behind the page, and that payload is the
only thing this service reads.

1. **The provider leaderboard** (`/leaderboards/providers`) — every offering of
   every provider: **1082 offerings across 58 providers**, 64 fields each.
2. **The Openness Index** (`/evaluations/artificial-analysis-openness-index`) —
   298 scored models with the full component breakdown.

### Why the payload and not the rendered table

The rendered table is a lossy view of the payload, in two ways that both matter:

**Columns.** The table shows 12 columns collapsed and 50 expanded, but
"Expand Columns" is a client-side toggle over data that already shipped —
expanding issues no network request. Everything in the 50-column view, including
per-token pricing, cache pricing, the throughput and latency percentiles, the
Omniscience Index and the API ID, is in the initial HTML of *any* of these pages.

**Rows.** The leaderboard renders only non-deprecated offerings — its
`Status: Current` filter — while its payload carries every offering. Measured
2026-08-14:

| | rendered | payload | deprecated |
|---|---|---|---|
| Nebius | 25 | 35 | 10 |
| Azure | 20 | 84 | 64 |
| all providers | 516 | 1082 | 566 |

`rendered + deprecated == payload` exactly, so the `Status: Current` filter *is*
`deprecated == false`, applied client-side to a payload that already contains
everything.

### Why not the per-provider pages

They add nothing. Every offering id on `/providers/nebius` is present in the
leaderboard payload, and a per-key comparison of the two found **zero** fields
with a real value on the provider page but missing from the leaderboard, zero the
reverse, and zero conflicts. The only differences were React's `"$undefined"`
sentinel versus an omitted key, which `flight.clean` normalises to the same
`None`. Reading 58 provider pages therefore costs 58 requests for a strict subset
of one.

Superseded offerings are kept rather than filtered at acquisition time, with
`deprecated` carried as a column: that way a model being replaced never punches a
hole in price history, and no re-scrape is needed to recover the old rows.

### Values, not renderings

The payload is typed JSON, so the parser reads values instead of cleaning strings.
There is no em-dash / U+2212 minus / currency-symbol / thousands-separator /
trailing-asterisk handling anywhere in this service — those exist only to undo a
table rendering. Two consequences worth naming:

* `intelligence_index` is `45.1382483763163`, not `45`.
* `intelligence_index_estimated` is a real boolean field, not a trailing `*`.

## The primary key

`offering_id` — AA's own uuid for the row. **No composite of the human-readable
fields is unique.** Tested over the full 1082-row payload:

| Candidate key | Duplicate groups |
|---|---|
| `offering_id` | **0** |
| `(provider, model_slug, host_api_id, display_name)` | 4 |
| `(provider, model_slug, display_name)` | 6 |
| `(provider, model_slug)` | 23 |
| `(provider, host_api_id)` | 248 |

The irreducible collisions are real distinct endpoints that AA does not name
apart. `openai`/`o3` appears twice under one `host_api_id` (`o3-2025-04-16`) with
the same label, differing only in price ($10/$40 versus $2/$8 per 1M tokens) and
in whether performance was measured. There is no tier, region or variant field to
separate them, so `offering_id` is the only key, and `normalize_sources` asserts
its uniqueness on every run.

### Reasoning-effort grain

One offering is one (provider x model x reasoning variant x serving endpoint). Of
1082 offerings, 299 labels carry an explicit effort token and 78 (provider, base
model) groups span more than one effort:

```
anthropic / Claude Opus 5
  low     II=52.46  cost_per_task=0.425  slug=claude-opus-5-low
  medium  II=58.64  cost_per_task=0.724  slug=claude-opus-5-medium
  high    II=61.48  cost_per_task=1.227  slug=claude-opus-5-high
  xhigh   II=62.52  cost_per_task=1.801  slug=claude-opus-5-xhigh
  max     II=63.05  cost_per_task=2.337  slug=claude-opus-5
```

`max` owns the unsuffixed slug. Per-token price is constant across efforts while
`cost_per_task_usd` varies, so effort is economically meaningful even though
pricing does not change with it.

## The join

Exact match on `model_slug`. Openness records live in their own id space and
reference a model by `modelId`; that uuid appears **nowhere** in the leaderboard
payload (0 of 298 found), so `offering_id` cannot anchor this join. What does work
is the slug: the Openness page carries a model entity for each score, all 298 of
which resolve to a slug, and the leaderboard carries `model_slug` on every
offering.

So there is no name normalisation, no creator filter, no confidence tiers, and no
fuzzy matching — the previous display-name join needed all four. Coverage improved
as a result: **698 offerings matched against 563 before, with 0 ambiguous instead
of 1.**

209 of the 298 scored model slugs are served by at least one tracked provider; the
other 89 are scored models nobody serves, recorded in
`metadata.openness_without_offering`. Offerings whose model has no openness row
are listed in `unmatched`, and absent openness stays `null` rather than becoming
zero.

## Relationship to the canonical database

This dataset sits alongside `database/current/prices.json` rather than merging
into it because the **grain differs**: `tokenpricing.modeling.ModelInfo` is keyed
by model with a single provider and a single price, while Artificial Analysis
publishes one row per (provider x model x reasoning variant x serving endpoint) —
1082 rows over 58 providers.

Per-token pricing is no longer the obstacle it was thought to be: the payload
carries `input_price_usd_per_1m`, `output_price_usd_per_1m` and both cache prices,
so a future crosswalk into `PricingInfo` is now possible. The dataset links back by
`model_slug`, `display_name` and `creator`. The public SDK API is unchanged.

## Failure behaviour

Three failure modes alert under their own names, each opening (or commenting on)
a GitHub issue labelled `aa-sync-failure` — see
[`alerting.py`](src/tokenpricing_aa/alerting.py):

| Alert | Means | Detected by |
|---|---|---|
| `payload-not-found` | AA no longer ships data as a flight payload in the initial HTML | `flight.reconstruct_payload` |
| `request-blocked` | persistent non-200 or transport failure after retries | `fetch.get_page` |
| `schema-drift` | payload parsed but a field vanished, changed type, or changed units | `schema.check_drift` |

Retry policy: retryable statuses (408/425/429/5xx) get 4 attempts with 2s/8s/30s
backoff; a refusal such as 403 or 451 is **not** retried, because repeating the
request will not change it.

Drift is checked against `schema/offering-manifest.json` on every run, because "the
pipeline did not crash" is not evidence that the source is unchanged. A field that
disappears or changes type is breaking. So is a numeric field whose values move
more than 10x outside their recorded span — that is what a *unit* change looks like
from the outside (fractions rescaled to percentages, per-1M prices restated
per-1k), and it parses perfectly while meaning something else. A **new** field is
informational only: additive change is how AA ships new benchmarks and never fails
a run. On breaking drift the run alerts and publishes nothing, because a stale
snapshot is recoverable and a silently wrong one is not.

Shape guards reject a thin capture before it can be published: `ShapeError` when
fewer than 850 offerings, 45 providers or 250 openness rows are parsed, when under
95% of offerings carry a model slug, or when `offering_id` is not unique.

### Sending alerts somewhere else

Delivery is one function, `deliver_via_github_issue`. Any `(Alert) -> str`
callable is a channel; pass it as `send_alert(alert, delivery=…)` or change
`DEFAULT_DELIVERY`. Nothing else in the service knows how alerts are delivered, so
adding Teams or email is a single new function.
