# Spike: Artificial Analysis data acquisition

**Status:** experiment / proof-of-concept. Not production code, not wired into CI, not in `database/`.
**Date of capture:** 2026-08-13.
**Question asked:** can we reliably get (a) AA's provider-level leaderboard in its *expanded* column
view, and (b) the AA Openness Index with per-component breakdown — and would we know how to build a
tuned weekly workload on top?

**Answer:** yes, both, and more completely than expected. Everything needed is rendered into the DOM
on a single page load, with no pagination, no lazy-loading and no XHR. But there is a commercial
wrinkle that needs a decision before anyone builds the weekly workload — see
[The awkward part](#the-awkward-part-this-data-is-a-paid-product) below.

---

## TL;DR

| | (a) Provider leaderboard | (b) Openness Index |
|---|---|---|
| URL | `/leaderboards/providers` | `/evaluations/artificial-analysis-openness-index` |
| Backing JSON API on the page? | **No** | **No** |
| Rows available | **512** (model × provider) | **298** (model) |
| Columns | 11 collapsed → **51 expanded** | 10 |
| How to expand | React state, synthetic pointer events (no URL param) | n/a |
| Stable join key in DOM | **Yes** — `/models/{slug}` + `/providers/{slug}` | **No — zero anchors** |
| Openness Index present? | **No** (confirmed) | — |
| Requests to capture everything | **1 page load** | **1 page load** |

Two headline gotchas:

1. **Openness Index is genuinely absent from the provider leaderboard.** Federico's manual check was
   right. The expanded view *does* have a column called **"Omniscience Index"** — a completely
   different metric (hallucination/knowledge, and it goes negative). The names are one letter apart
   in the middle and easy to misread. That's almost certainly the source of any confusion. This is
   exactly why (b) has to be a separate dataset on a separate key.
2. **The join between (a) and (b) is the hard part**, and it's worse than "names are messy" — the
   variant disambiguator lives in a *different field* in each dataset. Details below.

---

## (a) Provider leaderboard

### There is no data API behind the page

Checked the full network log across a clean reload: **107 requests, zero XHR/fetch to any data
endpoint.** No `/api/*`, no `_next/data/*.json`, no GraphQL, no third-party data host. The
breakdown is the document itself, fonts, CSS, ~70 JS chunks, logo images, GTM/analytics, and
PostHog assets (served first-party under `/togshop/`).

The page is Next.js App Router; the payload arrives server-rendered in the initial document.
`self.__next_f` holds a ~208KB flight payload but the row values are **not** discoverable in it by
field name — the data is embedded in the rendered markup rather than as a clean JSON blob. So
**the table DOM is the interface.** That's less fragile than it sounds: it's one static table, and
we get all 512 rows from one GET.

### Reaching the expanded view

There's an **"Expand Columns"** button (label flips to "Collapse Columns"). Crucially:

- **No URL query param.** `location.href` is unchanged after expanding. You cannot deep-link it.
- **`element.click()` does not work.** React ignores it. You need a full synthetic pointer
  sequence — `pointerover, pointerdown, mousedown, pointerup, mouseup, click` — see
  [`extract.js`](./extract.js). This is the one detail that will cost someone an afternoon.
- **Expanding fires no network request.** All 51 columns of data for all 512 rows are already
  client-side; the button only changes what's rendered. Confirmed by watching the network log
  across the toggle.

Practical consequence: a plain `curl` of the HTML gets you the collapsed columns only. The workload
needs a real browser (Playwright/Puppeteer) — but exactly **one** page load and one button press.

### What the expanded view gives us

51 columns per (model, provider) row, in six groups:

- **Identity / features** — API Provider, Model, Context Window, Function Calling, JSON Mode,
  OpenAI Compatible, License, **API ID** (the provider's own model string, e.g.
  `accounts/fireworks/models/kimi-k3`, `@cf/openai/gpt-oss-120b`, `global.anthropic.claude-opus-5`),
  Footnotes.
- **Model intelligence (23 eval columns)** — AA Intelligence Index, Omniscience Index, GDPval-AA,
  AA-Briefcase, Terminal-Bench Hard / v2.1, τ²-Bench Telecom, τ³-Banking, AA-LCR, AA-Omniscience
  Accuracy + Non-Hallucination Rate, Humanity's Last Exam, GPQA Diamond, SciCode, IFBench, CritPt,
  APEX-Agents-AA, ITBench-AA, MMMU Pro, LiveCodeBench, AIME 2025, AutomationBench-AA, Harvey LAB-AA.
- **Price (5)** — Cost per Task USD, Input, Output, Cache Hit, Cache Write (all USD/1M tokens).
- **Speed (5)** — Median Tokens/s plus **P5 / P25 / P75 / P95**.
- **Latency (6)** — Median First Chunk, First Answer Token, plus **P5 / P25 / P75 / P95** First Chunk.
- **End-to-end (2)** — Total Response (s), Reasoning Time (s).

Note on "provider load": there is **no explicit load/utilisation column**. The percentile spreads
are the usable proxy — a provider whose P5→P95 tokens/s fans out wide is contended. That's a real
signal (see the sample: Together AI's P95 first-chunk latency on Kimi K3 is **112.70s** against a
**0.89s** P5 — a ~127× spread — while Parasail runs 1.80→2.32s on the same model).

The **API ID** column is a quiet win: it's the exact string you'd put in an API call, which gives us
a much better bridge to our own catalogue than display names.

### Filters change what you capture

Default filter state is `Weights: All, Size: All, Price: All, Reasoning: All, **Status: Current**`.
`Status: Current` means **deprecated/legacy endpoints are excluded by default**. Anyone building the
weekly job must decide deliberately whether to flip that — it's directly relevant to the deprecation
tracking in #78, and it's a silent data loss if nobody notices.

### Sample

[`data/provider-leaderboard-sample.csv`](./data/provider-leaderboard-sample.csv) — **26 rows, 53
columns** (51 + the two extracted slugs), covering Claude Opus 5 (3 providers), Kimi K3 (10),
Qwen3.5 397B A17B reasoning (6) and non-reasoning (4), gpt-oss-120b (3).

Two real data points that show why (model × provider) is the right key — same model, same benchmark
scores, wildly different serving economics:

| | Kimi K3 @ Parasail | Kimi K3 @ Together AI |
|---|---|---|
| Cost per task | **$0.78** | $1.43 |
| Median tokens/s | **151** | 38 |
| Median first chunk | 1.96s | 3.42s |
| P95 first chunk | **2.32s** | 112.70s |
| Total response | **18.57s** | 69.94s |
| Intelligence Index | 60 | 60 (identical) |

...and a pathological one worth keeping as a fixture — **Qwen3.5 397B A17B @ DigitalOcean** reports
**10 tokens/s** and a **379.12s** total response against ~80 tok/s and ~47s for the same model on
Alibaba Cloud and Novita. Whether that's real contention or a measurement artefact, any
"cheapest provider wins" logic in the toolkit query layer (#79) would walk straight into it.

---

## (b) Openness Index

Also no API on the page; the table is server-rendered with **all 298 rows in the DOM**, single-depth
header, no pagination.

Columns: `Creator, Model, Openness Index, Intelligence Index, Model Availability, Model Transparency,
Pre-training Data Access, Pre-training Data License, Post-training Data Access, Post-training Data License`.

The spec PDF has been read in full and summarised for internal use in
**[`openness-index-methodology.md`](./openness-index-methodology.md)** — that's the reference doc
Federico asked for. Headlines:

- Six subcomponents, each 0–3, summed to **max 18**, then normalised to 0–100. Published percentages
  are therefore always `n/18` — `88.89` is 16/18, `38.89` is 7/18, `11.11` is 2/18.
- **The live table does not expose all six subcomponents.** Model Availability is published as an
  aggregate (Access + License), and the two *methodology* subcomponents aren't published at all —
  they're only recoverable as a residual (`Transparency − mean(data access) − mean(data license)`).
  We verified this arithmetic reconciles exactly on four models against the spec's own worked
  examples. The buttons labelled `Transparency - Methodology` etc. are **sort controls, not column
  toggles** — clicking them reveals nothing further. Verified.
- **Closed/proprietary models are in scope** (Claude Opus 4.5 scores 11.11 = 2/18), so this is a
  cross-cutting model attribute, not an open-weights-only leaderboard.
- Note the spec is stamped **PRELIMINARY DRAFT** on every page. Definitions may move; version any
  ingested data against "Spec V1.0".

Sample: [`data/openness-index-sample.csv`](./data/openness-index-sample.csv) — 7 models chosen to
overlap with (a), plus Olmo 3 7B Instruct as the rank-1 reference point.

---

## The join is the hard part

This is the finding I'd most want carried into whatever issue picks this up. It is **not** a
generic "names might not match" caveat — there is a specific structural mismatch.

**On the provider leaderboard**, reasoning variants are distinguished by **slug**, but their
**display names can be identical**:

| Display name | Model slug |
|---|---|
| `Qwen3.5 397B A17B` | `qwen3-5-397b-a17b` |
| `Qwen3.5 397B A17B` | `qwen3-5-397b-a17b-non-reasoning` |

**On the Openness Index**, the same two models are distinguished by **display name**, and there are
**no slugs at all** (zero anchors in the table body):

| Display name | Slug |
|---|---|
| `Qwen3.5 397B A17B (Reasoning)` | — none — |
| `Qwen3.5 397B A17B (Non-reasoning)` | — none — |

So each dataset carries the disambiguator in the field the *other* one lacks. A naive
`join on display_name` silently collapses the two Qwen variants into one on the (a) side, and a
naive `join on slug` is impossible on the (b) side. Neither dataset alone is sufficient.

It gets worse: **which effort level owns the bare slug varies per model.**

| Display name | Slug |
|---|---|
| `gpt-oss-120b (high)` | `gpt-oss-120b` |
| `gpt-oss-120b (low)` | `gpt-oss-120b-low` |
| `Claude Opus 5 (max)` | `claude-opus-5` |
| `Claude Opus 5 (xhigh)` | `claude-opus-5-xhigh` |
| `Claude Opus 5 (high)` | `claude-opus-5-high` |

For gpt-oss the bare slug is **high**; for Opus 5 it's **max**. You cannot derive the slug from
`name + effort` by rule — you must read the `href`. Across the leaderboard this shows up as
**221 distinct display names but only 183 distinct model slugs**.

This lands directly on **#74**'s (model × reasoning_effort × serving_platform) identity. AA's own
data model is internally inconsistent about where reasoning effort lives, so #74's normalisation
needs an explicit, tested mapping layer rather than a parsing convention.

**Recommended join strategy:** build an explicit `aa_model_slug → aa_openness_row` crosswalk,
seeded by normalising `display_name` + `Creator`, and **fail loudly on ambiguity** rather than
picking a winner. Expect genuine misses — coverage is not aligned: `Claude Opus 5` is on the
provider leaderboard but **only Opus 4.5 is in the Openness Index**. Absent must stay distinct from
zero (which #78 already argues for).

---

## Parsing gotchas (all observed, all in the sample)

- **Negative numbers use U+2212 MINUS SIGN (`−`), not ASCII hyphen.** `parseFloat("−31")` → `NaN`.
  Omniscience Index goes negative routinely (`−31`, `−38`, `−49`), so this will bite.
- **Trailing asterisk = estimated/partial score** (`33*`). Preserve the flag; don't strip silently.
- **Em dash `--` / `—` means "no data"**, and is not zero.
- Thousands separators inside values (`1,715`) — must be CSV-quoted.
- Context window is human-rendered: `1M`, `1.05M`, `262k`, `205k`.
- Prices carry `$`, benchmark scores carry `%`.
- Header row is **two-deep** (group row + column row); flatten and slice, don't assume depth 1.
- Some `API ID` values are full URLs rather than model strings (Clarifai).
- The same model can report **different context windows per provider** (Kimi K3: 1.05M on most,
  1M on Together AI, **205k** on Databricks) — that's a per-offering attribute, not per-model.

---

## The awkward part: this data is a paid product

Worth stating plainly before anyone schedules a weekly job.

AA **does** publish an official API (`artificialanalysis.ai/api/v2`, `x-api-key` header). But both
things we want are behind paid tiers:

| Tier | Limit | Relevant access |
|---|---|---|
| **Free** | 100 req/24h | `/language/models/free` — headline indices, median performance, input/output pricing. **Model-keyed only.** |
| **Pro** | 500 req/24h | Full model detail incl. **Openness Index breakdown** (weights access, weights license, data, methodology) — i.e. **(b)** |
| **Commercial** | custom | **Provider-level data**, percentiles, performance over time, raw measurements — i.e. **(a)** |

So the framing "AA's free API is insufficient" is correct, and precisely so: **(a) is Commercial
tier, (b) is Pro tier.** The free tier gives neither the model×provider key nor the openness
components.

Which means the honest read on this spike is: *scraping the public pages works perfectly and gets us
data that AA sells access to.* That's a commercial/ToS question, not a technical one, and it isn't
mine to decide. Two concrete notes for whoever does decide:

- **Attribution is not the blocker.** Federico has confirmed we're fine crediting AA publicly —
  badge, references, links, all fine. Any surface built on this should carry
  "Data source: Artificial Analysis (artificialanalysis.ai)" and link the spec PDF. But attribution
  doesn't by itself resolve the paid-tier boundary.
- **Recommend pricing the Pro/Commercial tiers before building the scraper.** The Pro tier in
  particular may be cheap enough to make (b) a non-issue, and an API contract is enormously more
  stable than a DOM. AA are contactable at `hello@artificialanalysis.ai`. Worst case they say no and
  we've lost a week; best case we skip the fragile half of this entirely.

The rest of this document assumes the scraping route is chosen, because that's what was asked for —
but I'd flag the above as a real decision, not a formality.

---

## Recommendation: how a tuned weekly workload should be designed

**Volume is a non-issue.** This is the single most important sizing fact: capturing *everything* is
**2 page loads per week** — 512 provider rows and 298 openness rows, no pagination, no lazy-load, no
per-model detail fetches. The instinct that "the full provider leaderboard is a lot of rows, a naive
scrape needs tuning" turns out not to apply: the rows are free once the page is up. There is nothing
to rate-limit, because there is nothing to iterate.

Concretely:

1. **Headless browser, not HTTP.** Playwright. `curl` cannot reach the expanded columns. Two
   `page.goto()` calls, one synthetic-pointer button press, two `page.evaluate()` extractions.
   Budget ~30s total. Weekly cron, off-peak, single run, no concurrency, no backoff needed.
2. **Be a good citizen anyway.** Realistic UA, respect `robots.txt`, one visit per page per week,
   no parallel tabs. Politeness here is trivial because the volume is trivial.
3. **Capture raw, parse separately.** Save the raw `table.outerHTML` for both pages as the
   immutable artefact, then parse from that with tested code. This is the pattern
   `services/sync` already uses and it matters more than usual here: when AA restructures the page,
   we want the failing input on disk. It also lets us re-derive fields we didn't originally extract
   without re-scraping.
4. **Assert the shape, fail the job loudly.** Guard on: expanded header count (`51`), presence of
   the specific expected column names, row count within a sane band (`>400` for providers, `>250`
   for openness), and non-zero anchors on the provider table. A silent partial capture that writes
   a collapsed 11-column table into `database/` is the realistic failure mode, not a 429.
5. **Detect the expand failure explicitly.** If after the pointer sequence the label isn't
   "Collapse Columns" and the header count isn't 51, abort — do not write.
6. **Snapshot the filter state.** Record that `Status: Current` was active (or deliberately flip it
   and record that instead). Store it as metadata on the capture.
7. **Store raw subcomponents, derive percentages.** For openness, persist the 0–18 integers and the
   residual-derived methodology total; compute the 0–100 figure on read. Version the record against
   "Openness Spec V1.0" since the spec is a draft.
8. **Model the join as data, not as logic.** A checked-in crosswalk file with an explicit
   `unmatched` list, reviewed when it changes. Never silently fuzzy-match.
9. **Label provenance rigorously** — every latency/throughput figure here is **third-party measured
   by AA**, not vendor-published and not measured by us. #78 already demands this distinction; AA
   data slots in as a third *origin* value, and its measurement conditions (AA's own harness) should
   be recorded.

**Fragility assessment:** medium-low. The DOM contract we depend on is small — one `<table>`, the
`Expand Columns` button label, and `/models/` + `/providers/` href prefixes. The realistic break is
AA restyling the leaderboard, which the shape assertions in (4) will catch on the next run.

---

## Files

| File | What |
|---|---|
| [`README.md`](./README.md) | this writeup |
| [`openness-index-methodology.md`](./openness-index-methodology.md) | internal reference for the Openness Index spec V1.0 |
| [`extract.js`](./extract.js) | the extraction snippets actually used, incl. the pointer-event workaround and parsers for the gotchas |
| [`data/provider-leaderboard-sample.csv`](./data/provider-leaderboard-sample.csv) | 26 rows × 53 cols, expanded view |
| [`data/openness-index-sample.csv`](./data/openness-index-sample.csv) | 7 models × 10 cols |

Data © Artificial Analysis, Inc. Captured 2026-08-13 for internal feasibility assessment.
