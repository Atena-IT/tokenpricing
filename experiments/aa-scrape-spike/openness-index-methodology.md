# AA Openness Index — internal methodology reference

Source: [AA-Openness-Index-Spec_V1-0.pdf](https://artificialanalysis.ai/downloads/AA-Openness-Index-Spec_V1-0.pdf)
(Artificial Analysis, Inc., © 2025, marked **PRELIMINARY DRAFT** on every content page).
Live table: <https://artificialanalysis.ai/evaluations/artificial-analysis-openness-index>

This is our internal summary of how the index is constructed, so we can consume it correctly.
It is a paraphrase for engineering use — the PDF is authoritative.

## Shape of the index

Openness is scored on **two dimensions**, broken into **six subcomponents**, each scored `0–3`
against a best-fitting "archetype" with published definitions.

| Dimension | Subcomponent | Range |
|---|---|---|
| 1. Model availability | Access | 0–3 |
| 1. Model availability | License | 0–3 |
| 2. Model transparency | Data — Access | 0–3 |
| 2. Model transparency | Data — License (most restrictive) | 0–3 |
| 2. Model transparency | Methodology — Disclosure | 0–3 |
| 2. Model transparency | Methodology — License/Tooling (most restrictive) | 0–3 |

**Aggregation, per the spec:**

1. Data elements are **averaged between pre-training and post-training**
   (so pre/post collapse into a single 0–3 Access score and a single 0–3 License score).
2. Component scores are **summed**, maximum **18/18**.
3. The sum is **normalized to a 0–100 scale**.

So: `Openness Index (0–100) = (sum of 6 subcomponents) / 18 × 100`.

This is why the published figures land on repeating values — `88.89` is `16/18`,
`38.89` is `7/18`, `11.11` is `2/18`. Treat the published percentage as a rendering of
an integer-ish `n/18`, not as a continuous score.

> Note on "scale 0–18": both framings are right. The *raw* score is 0–18; the *published*
> column is that value normalized to 0–100. Our schema should store the raw subcomponents
> and derive the percentage, not the other way round.

## Scoring archetypes

### 1. Model availability

**Access** — *"Can I run this model on my own hardware?"*

| Score | Archetype | Spec examples |
|---|---|---|
| 0 | Closed weights, no API | Grok 4 Heavy, Windsurf SWE-1.5 |
| 1 | Closed weights, API limits token visibility (e.g. no raw reasoning tokens) | GPT-5.1, Gemini 3 Pro |
| 2 | Closed weights, API available showing all output tokens | Claude Sonnet 4.5, Qwen3 Max |
| 3 | Open weights — publicly available for download | Llama 4, DeepSeek v3.2, OLMo 3 |

**License** — *"Can I use it commercially, and do I owe attribution?"*

| Score | Archetype | Spec examples |
|---|---|---|
| 0 | Closed weights, or license disallows commercial use (research-only) | GPT-5.1, Llama 1 |
| 1 | Commercial use, attribution required | Llama 2–4, Kimi K2 |
| 2 | Commercial use, no attribution (other limitations may apply) | NVIDIA Nemotron Nano 9B v2 |
| 3 | No meaningful limitations (MIT / Apache 2.0) | gpt-oss-120b, GLM-4.6, OLMo 3 |

### 2. Model transparency — Data (scored separately pre- and post-training, then averaged)

**Data Access**

| Score | Archetype (pre-training) | Archetype (post-training) |
|---|---|---|
| 0 | No or limited disclosure | No or limited disclosure |
| 1 | Partial source detail / categorization disclosed | Partial source detail / categorization disclosed |
| 2 | Full data mix disclosure **+ >1T tokens of pre-training data released** | Full data mix disclosure **+ significant partial release usable for training** |
| 3 | Full data shared — everything needed to reproduce the final checkpoint given the training code | same |

⚠️ The **level-2 threshold differs between pre- and post-training** (a token count for
pre-training, a qualitative "enables independent reuse" test for post-training). The spec
flags this explicitly. Do not model level 2 as one shared definition.

**Data License (most restrictive)** — reflects the most restrictive license across shared
data components.

| Score | Archetype |
|---|---|
| 0 | No commercial use / no substantial data released |
| 1 | Commercial use, attribution required |
| 2 | Commercial use, no attribution required |
| 3 | No meaningful limitations |

At V1.0 **no model scores 2 or 3 on either data-license subcomponent** — the spec's example
columns for those rows are empty. Expect a heavily skewed distribution here.

### 2. Model transparency — Methodology

**Disclosure**

| Score | Archetype | Spec examples |
|---|---|---|
| 0 | No or limited disclosure | Grok 4, GPT-5, Gemini 2.5, Claude 4.5 |
| 1 | Model architecture disclosed (transformer variant, params, layers) | Qwen3 family, GLM-4.6 |
| 2 | Limited general technical disclosure (qualitative, partial hyperparameters) | DeepSeek v3.2, Llama 3.3 70B |
| 3 | Full technical details — optimization, hyperparameters, RL algorithms | Nemotron Nano 9B v2, GLM-4.5, OLMo 3 |

**License/Tooling (most restrictive)**

| Score | Archetype | Spec examples |
|---|---|---|
| 0 | No training code, frameworks or implementation details released | GPT-5, Claude 4.5, Gemini 2.5 |
| 1 | Frameworks/dependencies disclosed and openly available for commercial use | Nemotron Nano 9B v2 |
| 2 | End-to-end training pipeline code or guide released | — (none at V1.0) |
| 3 | E2E pipeline released **and** commercial use permitted | OLMo 3 |

## What the live table exposes vs. what the spec defines

The live leaderboard publishes **7 numeric columns**, which do **not** map 1:1 onto the six
spec subcomponents:

| Live column | Relation to spec |
|---|---|
| `Openness Index` | the normalized 0–100 total |
| `Model Availability` | **aggregate** of Access + License (max 6) |
| `Model Transparency` | **aggregate** of Data Access + Data License + Methodology Disclosure + Methodology License/Tooling (max 12) |
| `Pre-training Data Access` | raw pre-training value, *before* averaging |
| `Pre-training Data License` | raw pre-training value, *before* averaging |
| `Post-training Data Access` | raw post-training value, *before* averaging |
| `Post-training Data License` | raw post-training value, *before* averaging |

Consequences we have to live with:

- **The two Model-availability subcomponents are not separable.** `Model Availability = 6`
  could be Access 3 + License 3; `4` could be 3+1 or 2+2. We cannot recover the split from
  the table alone.
- **The two Methodology subcomponents are not published at all.** They are only recoverable
  as a *residual*:

  ```
  methodology_total = Model Transparency
                    − mean(Pre Data Access,  Post Data Access)
                    − mean(Pre Data License, Post Data License)
  ```

  This gives the combined 0–6 methodology figure, but not the Disclosure vs License/Tooling split.
- The page has buttons labelled `Transparency - Methodology`, `Model Availability` etc.
  These are **sort controls, not column toggles** — clicking them does not reveal extra
  columns. Verified in this spike.

### Worked verification (from our captured sample)

| Model | Avail. | Transp. | Pre A/L | Post A/L | Derived methodology | Total | Published |
|---|---|---|---|---|---|---|---|
| Olmo 3 7B Instruct | 6 | 10 | 3 / 1 | 3 / 1 | 10 − 3 − 1 = **6** | 16/18 | **88.89** ✓ |
| gpt-oss-120b (high) | 6 | 1 | 0 / 0 | 0 / 0 | 1 − 0 − 0 = **1** | 7/18 | **38.89** ✓ |
| Kimi K3 (max) | 4 | 3 | 0 / 0 | 0 / 0 | 3 − 0 − 0 = **3** | 7/18 | **38.89** ✓ |
| Claude Opus 4.5 (Reasoning) | 2 | 0 | 0 / 0 | 0 / 0 | **0** | 2/18 | **11.11** ✓ |

All four reconcile exactly against the spec's aggregation rule, and the archetype
assignments match the spec's own worked examples (Kimi K2 → license 1; gpt-oss-120b →
license 3, pre/post data 0; Claude 4.5 → availability 2, methodology 0). We can treat the
residual-derivation above as sound.

## Coverage notes

- **298 models** in the index at time of capture, spanning **47 creators**.
- **Closed/proprietary models are included** (Claude Opus 4.5 = 11.11, i.e. 2/18) — this is
  not an open-weights-only leaderboard.
- Coverage is *not* aligned with the provider leaderboard. Frontier models can be missing:
  at capture time `Claude Opus 5` appears on the provider leaderboard but **only Opus 4.5 is
  in the Openness Index**. Any join must tolerate misses on the openness side.
- Reasoning variants are scored separately and can differ on `Intelligence Index` while
  sharing an identical openness score (`Kimi K3 (max)` and `Kimi K3 (low)` are both 38.89).

## Attribution

Federico has confirmed we are fine to credit AA publicly as the data source. Any surface
built on this should carry an explicit "Data source: Artificial Analysis
(artificialanalysis.ai)" credit plus a link to the spec PDF, and should note the index is a
**preliminary draft (V1.0)** whose definitions may move.
