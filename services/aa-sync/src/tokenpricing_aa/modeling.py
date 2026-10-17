"""Pydantic models for the Artificial Analysis dataset.

These live in the service rather than in ``libraries/python`` (the public SDK)
because the grain differs: ``tokenpricing.modeling.ModelInfo`` is keyed by model
with a single provider and a single price, while AA's data is one row per
(provider x model x reasoning variant x serving endpoint) -- 1082 rows over 58
providers as of 2026-08-14.

The dataset sits alongside the canonical database and links to it by
``model_slug``/``display_name`` rather than impersonating ``ModelInfo``. The SDK's
public API is unchanged.

Data source: Artificial Analysis (https://artificialanalysis.ai).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

ATTRIBUTION = (
    "Data source: Artificial Analysis (https://artificialanalysis.ai). "
    "Benchmark, latency and throughput figures are third-party measurements "
    "produced by Artificial Analysis, not vendor-published and not measured by "
    "tokenpricing."
)

OPENNESS_SPEC_VERSION = "Openness Spec V1.0 (preliminary draft)"


class OpennessBreakdown(BaseModel):
    """Openness Index components on their raw published scales.

    The payload carries the two methodology subcomponents that the rendered
    Openness Index table omits, so this is a fuller breakdown than the site shows.
    """

    openness_index: float | None = Field(
        default=None, description="Published Openness Index, 0-100"
    )
    model_availability: float | None = None
    model_transparency: float | None = None
    pre_training_data_access: float | None = None
    pre_training_data_license: float | None = None
    post_training_data_access: float | None = None
    post_training_data_license: float | None = None
    transparency_methodology: float | None = None
    transparency_pre_training_data: float | None = None
    transparency_post_training_data: float | None = None


class Offering(BaseModel):
    """One model as served by one provider at one reasoning effort.

    ``offering_id`` is AA's own uuid for the row and is the primary key. No
    composite of the human-readable fields is unique: verified over the full
    1082-row payload, ``(provider_slug, model_slug, host_api_id, display_name)``
    still collides on 4 groups, because AA publishes distinct endpoints that differ
    only in price and measured performance (``openai``/``o3`` appears at both
    $10/$40 and $2/$8 per 1M tokens under one ``host_api_id``).
    """

    offering_id: str
    provider_slug: str
    provider_name: str | None = None
    model_slug: str | None = None
    display_name: str
    host_api_id: str | None = None
    footnotes: str | None = None
    creator: str | None = None

    # Identity / lifecycle
    is_open_weights: bool | None = Field(
        default=None,
        description="AA's License column is the rendering of this boolean",
    )
    deprecated: bool | None = Field(
        default=None,
        description=(
            "Superseded offering. The leaderboard's Status: Current view hides "
            "these; the payload retains them, so price history stays continuous "
            "when a model is replaced. Filter at query time, not acquisition time."
        ),
    )
    reasoning_model: bool | None = None
    size_class: str | None = None
    reasoning_mode: str | None = Field(
        default=None, description="reasoning or non-reasoning"
    )
    reasoning_effort: str | None = Field(
        default=None, description="minimal, low, medium, high, xhigh, or max"
    )

    # Features
    context_window: int | None = None
    supports_function_calling: bool | None = None
    supports_json_mode: bool | None = None
    openai_compatible: bool | None = None

    # Intelligence
    intelligence_index: float | None = None
    intelligence_index_estimated: bool | None = None
    omniscience_index: float | None = None
    omniscience_accuracy: float | None = None
    omniscience_non_hallucination: float | None = None
    gdpval_normalized: float | None = None
    briefcase_elo: float | None = None
    terminalbench_hard: float | None = None
    terminalbench_v21: float | None = None
    tau2_bench_telecom: float | None = None
    tau3_banking: float | None = None
    aa_lcr: float | None = None
    humanitys_last_exam: float | None = None
    gpqa_diamond: float | None = None
    scicode: float | None = None
    ifbench: float | None = None
    critpt: float | None = None
    apex_agents: float | None = None
    itbench_sre: float | None = None
    mmmu_pro: float | None = None
    livecodebench: float | None = None
    aime_2025: float | None = None
    automation_bench: float | None = None
    harvey_lab: float | None = None

    # Price
    cost_per_task_usd: float | None = None
    price_class: str | None = None
    input_price_usd_per_1m: float | None = None
    output_price_usd_per_1m: float | None = None
    cache_hit_price_usd_per_1m: float | None = None
    cache_write_price_usd_per_1m: float | None = None

    # Speed
    median_output_tokens_per_second: float | None = None
    p5_output_tokens_per_second: float | None = None
    p25_output_tokens_per_second: float | None = None
    p75_output_tokens_per_second: float | None = None
    p95_output_tokens_per_second: float | None = None

    # Latency
    median_first_chunk_seconds: float | None = None
    p5_first_chunk_seconds: float | None = None
    p25_first_chunk_seconds: float | None = None
    p75_first_chunk_seconds: float | None = None
    p95_first_chunk_seconds: float | None = None
    first_answer_token_seconds: float | None = None
    total_response_seconds: float | None = None
    reasoning_time_seconds: float | None = None

    openness: OpennessBreakdown | None = None


class UnmatchedOffering(BaseModel):
    provider_slug: str | None = None
    model_slug: str | None = None
    display_name: str
    creator: str | None = None
    candidates: list[str] = Field(default_factory=list)
    reason: str


class DriftSummary(BaseModel):
    """Outcome of the manifest check for this run."""

    breaking: bool = False
    missing: list[str] = Field(default_factory=list)
    type_changed: list[str] = Field(default_factory=list)
    range_shifted: list[str] = Field(default_factory=list)
    new: list[str] = Field(default_factory=list)


class AAMetadata(BaseModel):
    fetched_at: datetime
    sources: list[str]
    attribution: str = ATTRIBUTION
    openness_spec_version: str = OPENNESS_SPEC_VERSION
    provider_count: int
    offering_count: int
    deprecated_offering_count: int = 0
    openness_row_count: int
    openness_matched: int
    openness_unmatched: int
    openness_ambiguous: int
    openness_without_offering: int = 0
    drift: DriftSummary = Field(default_factory=DriftSummary)


class AADataset(BaseModel):
    """Complete Artificial Analysis capture for one run."""

    generated_at: datetime
    metadata: AAMetadata
    offerings: list[Offering]
    openness_index: list[dict] = Field(
        default_factory=list, description="Openness Index rows exactly as published"
    )
    unmatched: list[UnmatchedOffering] = Field(default_factory=list)
    ambiguous: list[UnmatchedOffering] = Field(default_factory=list)
