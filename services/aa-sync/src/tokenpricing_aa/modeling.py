"""Pydantic models for the Artificial Analysis dataset.

These live in the service rather than in ``libraries/python`` (the public SDK)
for two reasons:

* The grain differs. ``tokenpricing.modeling.ModelInfo`` is keyed by model with a
  single provider and a single price; AA's data is one row per
  (model x reasoning variant x serving platform) — 1045 rows over 51 providers.
* AA's public pages carry no per-token pricing at all (only ``Cost per Task USD``),
  so these rows cannot populate ``PricingInfo``/``SourceInfo``, whose
  ``input_per_million``/``output_per_million`` are required.

The dataset therefore sits alongside the canonical database and links to it by
``model_slug``/``display_name`` rather than trying to impersonate ``ModelInfo``.
The SDK's public API is unchanged.

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
    """Openness Index components as published, on their raw published scales.

    The live table publishes ``Model Availability`` as an aggregate and does not
    publish the two methodology subcomponents at all, so this is what AA exposes
    rather than the full six-part 0-18 breakdown described in the spec.
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


class OpennessMatch(BaseModel):
    """How an offering was matched to its Openness Index row."""

    tier: str = Field(
        description="Confidence tier that produced the match: exact, base+mode, or base"
    )
    openness_display_name: str
    openness_creator: str | None = None


class Offering(BaseModel):
    """One model as served by one provider, as measured by Artificial Analysis."""

    provider_slug: str
    model_slug: str
    display_name: str
    creator: str | None = None
    context_window: int | None = None
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    license: str | None = None
    intelligence_index: float | None = None
    intelligence_index_estimated: bool = False
    cost_per_task_usd: float | None = None
    cost_per_task_estimated: bool = False
    median_output_tokens_per_second: float | None = None
    median_first_chunk_seconds: float | None = None
    total_response_seconds: float | None = None
    reasoning_time_seconds: float | None = None
    reasoning_mode: str | None = Field(
        default=None, description="reasoning, non-reasoning, or None when unspecified"
    )
    reasoning_effort: str | None = Field(
        default=None, description="minimal, low, medium, high, xhigh, or max"
    )
    variant_tokens: list[str] = Field(
        default_factory=list,
        description="Serving-side name suffixes (quantisation, tier, platform, snapshot)",
    )
    unclassified_variant_tokens: list[str] = Field(
        default_factory=list,
        description="Name suffixes matching no known vocabulary; dropped from the join key",
    )
    openness: OpennessBreakdown | None = None
    openness_match: OpennessMatch | None = None


class UnmatchedOffering(BaseModel):
    provider_slug: str | None = None
    model_slug: str | None = None
    display_name: str
    creator: str | None = None
    normalized_base: str | None = None
    candidates: list[str] = Field(default_factory=list)
    reason: str


class AAMetadata(BaseModel):
    fetched_at: datetime
    sources: list[str]
    attribution: str = ATTRIBUTION
    openness_spec_version: str = OPENNESS_SPEC_VERSION
    provider_count: int
    offering_count: int
    openness_row_count: int
    openness_matched: int
    openness_unmatched: int
    openness_ambiguous: int
    match_tiers: dict[str, int] = Field(default_factory=dict)
    unreachable_provider_slugs: list[str] = Field(default_factory=list)
    unclassified_variant_tokens: list[str] = Field(
        default_factory=list,
        description=(
            "Distinct name suffixes matching no known vocabulary. A new entry here "
            "means AA introduced a suffix type the join key does not account for."
        ),
    )


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
