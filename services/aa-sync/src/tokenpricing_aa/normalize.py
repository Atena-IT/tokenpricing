"""Build the Artificial Analysis dataset from raw captured pages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from tokenpricing_aa.matching import join_openness, parse_variant
from tokenpricing_aa.modeling import (
    AADataset,
    AAMetadata,
    DriftSummary,
    Offering,
    OpennessBreakdown,
    UnmatchedOffering,
)
from tokenpricing_aa.parse import (
    offering_objects,
    parse_leaderboard,
    parse_openness,
)
from tokenpricing_aa.schema import DriftReport, check_drift

logger = logging.getLogger(__name__)

# Shape guards. A silent partial capture writing a truncated dataset into
# database/ is the realistic failure mode here, not an HTTP error, so the job
# fails loudly instead of publishing a thin snapshot. Baselines from the
# 2026-08-14 capture: 1082 offerings, 58 providers, 298 openness rows.
MIN_PROVIDERS = 45
MIN_OFFERINGS = 850
MIN_OPENNESS_ROWS = 250
MIN_SLUG_COVERAGE = 0.95


class ShapeError(RuntimeError):
    """Raised when a capture is too far from the expected shape to publish."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ShapeError(message)


def normalize_sources(
    leaderboard_payload: dict[str, Any],
    openness_payload: dict[str, Any],
    drift: DriftReport | None = None,
) -> AADataset:
    """Project both captured pages into the published dataset.

    ``drift`` is the manifest comparison for this run, recorded in the dataset's
    metadata so a snapshot carries the evidence that its shape was checked.
    """
    page = leaderboard_payload["page"]
    rows = parse_leaderboard(page)

    _check(
        len(rows) >= MIN_OFFERINGS,
        f"only {len(rows)} offerings parsed, expected >= {MIN_OFFERINGS}",
    )
    providers = {row["provider_slug"] for row in rows if row.get("provider_slug")}
    _check(
        len(providers) >= MIN_PROVIDERS,
        f"only {len(providers)} providers in the payload, expected >= {MIN_PROVIDERS}",
    )
    with_slug = sum(1 for row in rows if row.get("model_slug"))
    coverage = with_slug / len(rows)
    _check(
        coverage >= MIN_SLUG_COVERAGE,
        f"only {coverage:.1%} of offerings carry a model slug, "
        f"expected >= {MIN_SLUG_COVERAGE:.0%}",
    )

    ids = [row["offering_id"] for row in rows]
    _check(
        len(set(ids)) == len(ids),
        f"offering_id is not unique: {len(ids) - len(set(ids))} duplicate(s)",
    )

    openness_rows = parse_openness(openness_payload["page"])
    _check(
        len(openness_rows) >= MIN_OPENNESS_ROWS,
        f"only {len(openness_rows)} openness rows parsed, "
        f"expected >= {MIN_OPENNESS_ROWS}",
    )

    if drift is None:
        drift = check_drift(offering_objects(page))

    join = join_openness(rows, openness_rows)

    offerings: list[Offering] = []
    for row in rows:
        variant = parse_variant(
            row.get("display_name") or "",
            row.get("model_slug"),
            row.get("reasoning_model"),
        )
        openness = row.get("openness")
        offerings.append(
            Offering(
                **{k: v for k, v in row.items() if k != "openness"},
                reasoning_mode=variant.reasoning_mode,
                reasoning_effort=variant.reasoning_effort,
                openness=OpennessBreakdown(**openness) if openness else None,
            )
        )

    logger.info(
        "%s offerings over %s providers; openness matched %s, unmatched %s, "
        "ambiguous %s; %s scored models served by nobody",
        len(offerings),
        len(providers),
        join.matched,
        len(join.unmatched),
        len(join.ambiguous),
        len(join.openness_without_offering),
    )
    for entry in join.ambiguous:
        logger.warning(
            "openness ambiguous: %s @ %s -> %s",
            entry["display_name"],
            entry["provider_slug"],
            entry["candidates"],
        )

    fetched_at = max(
        datetime.fromisoformat(str(leaderboard_payload["fetched_at"])),
        datetime.fromisoformat(str(openness_payload["fetched_at"])),
    )

    return AADataset(
        generated_at=datetime.now(UTC),
        metadata=AAMetadata(
            fetched_at=fetched_at,
            sources=[
                str(leaderboard_payload.get("source_url")),
                str(openness_payload.get("source_url")),
            ],
            provider_count=len(providers),
            offering_count=len(offerings),
            deprecated_offering_count=sum(1 for o in offerings if o.deprecated),
            openness_row_count=len(openness_rows),
            openness_matched=join.matched,
            openness_unmatched=len(join.unmatched),
            openness_ambiguous=len(join.ambiguous),
            openness_without_offering=len(join.openness_without_offering),
            drift=DriftSummary(
                breaking=drift.breaking,
                missing=sorted(drift.missing),
                type_changed=sorted(drift.type_changed),
                range_shifted=sorted(drift.range_shifted),
                new=sorted(drift.new),
            ),
        ),
        offerings=offerings,
        openness_index=openness_rows,
        unmatched=[UnmatchedOffering(**entry) for entry in join.unmatched],
        ambiguous=[UnmatchedOffering(**entry) for entry in join.ambiguous],
    )
