# tokenpricing-aa-sync

Weekly acquisition of [Artificial Analysis](https://artificialanalysis.ai) public
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
uv run tokenpricing-aa-sync sync       # fetch, capture, normalize, write
uv run tokenpricing-aa-sync normalize  # rebuild from the local raw capture
```

Outputs:

| Path | What |
|---|---|
| `database/current/artificial-analysis.json` | latest dataset |
| `database/history/artificial-analysis-<ts>.json` | weekly snapshot (26 retained) |
| `.capture/artificial-analysis/*.json` | raw HTML capture — gitignored, uploaded as a CI artifact |

Scheduled weekly by [`.github/workflows/aa-sync.yml`](../../.github/workflows/aa-sync.yml).

## Where the data comes from

Two sources, both plain HTTP — **no browser is required**:

1. **Per-provider pages** (`/providers/<slug>`, ~51 reachable). Provider slugs are
   discovered from `/leaderboards/providers`, but the row data is taken from the
   individual pages because the aggregate leaderboard is filtered
   (`Status: Current`) and exposes roughly half as many rows: **1045 offerings
   across 51 providers, against 512 on the leaderboard.**
2. **The Openness Index** (`/evaluations/artificial-analysis-openness-index`),
   298 rows with the published component breakdown.

The spike this service grew out of (`experiments/aa-scrape-spike`) recommended
Playwright. That was only needed to reach the *expanded* column view of the
aggregate leaderboard, which this service does not use. Both sources here are
fully server-rendered on a plain `GET`.

### What the public pages do not carry

The provider pages publish `Cost per Task USD` but **no per-token input/output
prices** and no cache pricing — those exist only in the expanded leaderboard view.
This is why the dataset does not populate `tokenpricing.modeling.PricingInfo`; see
[Relationship to the canonical database](#relationship-to-the-canonical-database).

## The join

The two datasets carry model identity in different fields, and neither is
sufficient alone:

* Provider pages have a stable `/models/<slug>` anchor **and** an effort-suffixed
  display name (`GPT-5.6 Sol (xhigh)`).
* The Openness Index has **no anchors at all** — only a rendered display name and
  a `Creator` column — and it disambiguates variants differently
  (`(Reasoning)` / `(Non-reasoning)`, sometimes `(Reasoning, Max Effort)`).

So the join runs on a normalised name key. The parenthetical suffix space is much
wider than reasoning effort: it also carries quantisation (`FP8`, `NVFP4`),
serving tier (`FAST`, `Turbo`), hosting platform (`Vertex`, `AI Studio`) and
snapshot dates. Openness is a property of the *model*, not of how a provider
serves it, so serving-side tokens are dropped from the key while reasoning
identity is kept.

Matching runs in descending confidence and **never guesses**:

| Tier | Key |
|---|---|
| `exact` | base name + reasoning mode + effort level |
| `base+mode` | base name + reasoning mode, when all candidates agree on every component |
| `base` | base name alone, when all candidates agree |

Variant identity is read from the display name first and from the `/models/`
slug second: provider pages sometimes render a bare `Grok 4 Fast` while the href
says `grok-4-fast-reasoning`. Only an explicit trailing suffix is trusted — which
effort level owns the *unsuffixed* slug varies per model (`gpt-oss-120b` is high,
`claude-opus-5` is max), so it is never inferred by rule.

A creator known on both sides is a hard filter — two labs shipping a similarly
named model are never merged. Candidates that disagree are recorded in
`ambiguous`; models with no openness row at all are recorded in `unmatched`.
Neither is dropped from the dataset, and absent openness stays `null` rather than
becoming zero.

### Why not fuzzy matching

Fuzzy matching over these names is actively unsafe. Against the live capture, the
closest openness name to an unmatched provider model scores 88-95 on token-sort
ratio while being a *different model*:

| Unmatched | Closest openness row | Score |
|---|---|---|
| `claude opus 5` | `claude opus 4 5` | 93 |
| `gemma 3 12b` | `gemma 4 12b` | 91 |
| `gpt 5 1 codex` | `gpt 5 codex` | 92 |

Any threshold low enough to catch real matches also produces wrong ones.

### Current coverage

From the capture that this service was built against (2026-08-14):

* 1045 offerings, 51 providers, 298 openness rows
* **563 matched (54%)** — 413 `exact`, 1 `base+mode`, 149 `base`
* 481 unmatched, 1 ambiguous

The unmatched share is dominated by genuine coverage gaps, not matcher failure:
provider pages expose 305 distinct model bases while the Openness Index covers
229, and the missing ones are mostly newer models Artificial Analysis has not
scored for openness yet (Qwen3.8, Claude Opus 5, the GPT-5.x Codex line).

## Relationship to the canonical database

This dataset sits alongside `database/current/prices.json` rather than merging
into it, for two structural reasons:

1. **Different grain.** `tokenpricing.modeling.ModelInfo` is keyed by model with a
   single provider and a single price. Artificial Analysis publishes one row per
   (model x reasoning variant x serving platform) — 1045 rows over 51 providers,
   including several rows per model per provider (`Kimi K3 (max)` and
   `Kimi K3 (max) (FAST)`).
2. **No per-token pricing.** `PricingInfo.input_per_million` and
   `output_per_million` are required fields, and the public Artificial Analysis
   pages do not publish either.

The dataset links back by `model_slug`, `display_name` and `creator`, so a future
crosswalk into `ModelInfo` remains possible. The public SDK API is unchanged.

## Failure behaviour

A silent partial capture is the realistic failure mode, not an HTTP error, so the
job refuses to publish a thin snapshot. `normalize_sources` raises `ShapeError`
when fewer than 40 provider pages, 800 offerings or 250 openness rows are parsed,
or when under 95% of offerings carry a `/models/` anchor. `parse` raises
`ParseError` when either table's columns change.

Provider slugs discovered on the leaderboard do not all resolve — 7 of 58 return
404. These are recorded in `metadata.unreachable_provider_slugs` rather than
failing the run.
