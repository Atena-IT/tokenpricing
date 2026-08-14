"""Build the Artificial Analysis dataset from raw captured pages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from tokenpricing_aa.matching import (
    enrich_key_from_slug,
    join_openness,
    parse_display_name,
)
from tokenpricing_aa.modeling import (
    AADataset,
    AAMetadata,
    Offering,
    OpennessBreakdown,
    OpennessMatch,
    UnmatchedOffering,
)
from tokenpricing_aa.parse import parse_openness_page, parse_provider_page

logger = logging.getLogger(__name__)

# Shape guards. A silent partial capture writing a truncated dataset into
# database/ is the realistic failure mode here, not an HTTP error, so the job
# fails loudly instead of publishing a thin snapshot.
MIN_PROVIDERS = 40
MIN_OFFERINGS = 800
MIN_OPENNESS_ROWS = 250
MIN_SLUG_COVERAGE = 0.95


class ShapeError(RuntimeError):
    """Raised when a capture is too far from the expected shape to publish."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ShapeError(message)


def normalize_sources(
    providers_payload: dict[str, Any], openness_payload: dict[str, Any]
) -> AADataset:
    pages: dict[str, str] = providers_payload.get("pages") or {}
    _check(
        len(pages) >= MIN_PROVIDERS,
        f"only {len(pages)} provider pages captured, expected >= {MIN_PROVIDERS}",
    )

    raw_offerings: list[dict[str, Any]] = []
    for slug in sorted(pages):
        rows = parse_provider_page(pages[slug], slug)
        if not rows:
            logger.warning("provider page %s parsed to zero rows", slug)
        raw_offerings.extend(rows)

    _check(
        len(raw_offerings) >= MIN_OFFERINGS,
        f"only {len(raw_offerings)} offerings parsed, expected >= {MIN_OFFERINGS}",
    )
    with_slug = sum(1 for row in raw_offerings if row.get("model_slug"))
    coverage = with_slug / len(raw_offerings)
    _check(
        coverage >= MIN_SLUG_COVERAGE,
        f"only {coverage:.1%} of offerings carry a /models/ anchor, "
        f"expected >= {MIN_SLUG_COVERAGE:.0%}",
    )

    openness_rows = parse_openness_page(openness_payload["page"])
    _check(
        len(openness_rows) >= MIN_OPENNESS_ROWS,
        f"only {len(openness_rows)} openness rows parsed, "
        f"expected >= {MIN_OPENNESS_ROWS}",
    )

    join = join_openness(raw_offerings, openness_rows)

    offerings: list[Offering] = []
    for row in raw_offerings:
        key = enrich_key_from_slug(
            parse_display_name(row["display_name"]), row.get("model_slug")
        )
        openness = row.get("openness")
        match = row.get("openness_match")
        offerings.append(
            Offering(
                **{
                    name: row[name]
                    for name in (
                        "provider_slug",
                        "model_slug",
                        "display_name",
                        "creator",
                        "context_window",
                        "supports_function_calling",
                        "supports_json_mode",
                        "license",
                        "intelligence_index",
                        "intelligence_index_estimated",
                        "cost_per_task_usd",
                        "cost_per_task_estimated",
                        "median_output_tokens_per_second",
                        "median_first_chunk_seconds",
                        "total_response_seconds",
                        "reasoning_time_seconds",
                    )
                },
                reasoning_mode=key.reasoning,
                reasoning_effort=key.effort,
                variant_tokens=list(key.dropped),
                unclassified_variant_tokens=list(key.unknown),
                openness=OpennessBreakdown(**openness) if openness else None,
                openness_match=OpennessMatch(**match) if match else None,
            )
        )

    for entry in join.unmatched:
        logger.info(
            "openness unmatched: %s @ %s (%s)",
            entry["display_name"],
            entry["provider_slug"],
            entry["reason"],
        )
    for entry in join.ambiguous:
        logger.warning(
            "openness ambiguous: %s @ %s -> %s",
            entry["display_name"],
            entry["provider_slug"],
            entry["candidates"],
        )

    fetched_at = max(
        datetime.fromisoformat(str(providers_payload["fetched_at"])),
        datetime.fromisoformat(str(openness_payload["fetched_at"])),
    )
    unreachable = [
        str(item.get("slug"))
        for item in providers_payload.get("unreachable_slugs") or []
    ]
    unclassified = sorted(
        {token for offering in offerings for token in offering.unclassified_variant_tokens}
    )
    if unclassified:
        logger.warning(
            "unclassified name suffixes (dropped from the join key): %s", unclassified
        )

    return AADataset(
        generated_at=datetime.now(UTC),
        metadata=AAMetadata(
            fetched_at=fetched_at,
            sources=[
                str(providers_payload.get("source_url")),
                str(openness_payload.get("source_url")),
            ],
            provider_count=len(pages),
            offering_count=len(offerings),
            openness_row_count=len(openness_rows),
            openness_matched=join.matched,
            openness_unmatched=len(join.unmatched),
            openness_ambiguous=len(join.ambiguous),
            match_tiers=dict(sorted(join.tiers.items())),
            unreachable_provider_slugs=sorted(unreachable),
            unclassified_variant_tokens=unclassified,
        ),
        offerings=offerings,
        openness_index=[
            {name: value for name, value in row.items() if not name.startswith("_")}
            for row in openness_rows
        ],
        unmatched=[UnmatchedOffering(**entry) for entry in join.unmatched],
        ambiguous=[UnmatchedOffering(**entry) for entry in join.ambiguous],
    )
