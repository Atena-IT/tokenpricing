"""Reasoning-variant identification and the Openness Index join.

Both jobs used to be hard because the only identifiers available from the rendered
tables were display names, so joining meant normalising human-readable strings and
hoping. The payload removes that:

* ``model.reasoningModel`` is a boolean, so reasoning mode is read, not inferred.
* Every offering carries ``model.slug``, and the Openness Index page carries a slug
  for each scored model, so the cross-dataset join is an exact slug match. The
  three-tier confidence matching, creator-prefix stripping, quantisation and
  snapshot-token vocabularies, and date-token recognition that the display-name
  join needed are all gone.

Reasoning *effort* is the one thing still read from names, because AA encodes it in
the slug suffix and the label parenthetical rather than as a field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# AA's effort vocabulary. ``max`` is the unsuffixed slug: claude-opus-5 is max,
# claude-opus-5-high is high.
EFFORT_TOKENS = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": "max",
    "max effort": "max",
    "high effort": "high",
    "medium effort": "medium",
    "low effort": "low",
    "xhigh effort": "xhigh",
}

_SLUG_EFFORT_SUFFIXES = ("minimal", "low", "medium", "high", "xhigh")
_PARENTHETICAL = re.compile(r"\(([^)]*)\)")


@dataclass(frozen=True)
class Variant:
    reasoning_mode: str | None
    """``reasoning`` or ``non-reasoning``, read from the payload's boolean."""
    reasoning_effort: str | None
    """``minimal``..``max``, or ``None`` where AA publishes no effort variant."""


def parse_variant(
    display_name: str, model_slug: str | None, reasoning_model: Any
) -> Variant:
    """Identify the reasoning variant of one offering."""
    mode: str | None = None
    if reasoning_model is True:
        mode = "reasoning"
    elif reasoning_model is False:
        mode = "non-reasoning"

    slug = (model_slug or "").lower()
    if slug.endswith("-non-reasoning"):
        mode = "non-reasoning"

    effort: str | None = None
    for suffix in _SLUG_EFFORT_SUFFIXES:
        if slug.endswith(f"-{suffix}"):
            effort = suffix
            break

    if effort is None:
        for group in _PARENTHETICAL.findall(display_name or ""):
            token = group.strip().lower()
            if token in EFFORT_TOKENS:
                effort = EFFORT_TOKENS[token]
                break

    return Variant(reasoning_mode=mode, reasoning_effort=effort)


BREAKDOWN_FIELDS = (
    "openness_index",
    "model_availability",
    "model_transparency",
    "pre_training_data_access",
    "pre_training_data_license",
    "post_training_data_access",
    "post_training_data_license",
    "transparency_methodology",
    "transparency_pre_training_data",
    "transparency_post_training_data",
)


@dataclass
class JoinResult:
    matched: int = 0
    """Offerings that received an openness breakdown."""
    unmatched: list[dict[str, Any]] = field(default_factory=list)
    """Offerings whose model has no Openness Index row."""
    ambiguous: list[dict[str, Any]] = field(default_factory=list)
    """Offerings whose model slug maps to more than one openness row."""
    openness_without_offering: list[str] = field(default_factory=list)
    """Scored models no tracked provider serves."""


def join_openness(
    offerings: list[dict[str, Any]], openness_rows: list[dict[str, Any]]
) -> JoinResult:
    """Attach openness breakdowns to offerings by exact model slug.

    Mutates each offering in place, setting ``openness`` where a row exists. A
    model with no openness row is normal -- AA scores far fewer models than
    providers serve -- so it is recorded rather than warned about.
    """
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for row in openness_rows:
        slug = row.get("model_slug")
        if slug:
            by_slug.setdefault(str(slug), []).append(row)

    result = JoinResult()
    used: set[str] = set()

    for offering in offerings:
        slug = offering.get("model_slug")
        candidates = by_slug.get(str(slug), []) if slug else []

        if not candidates:
            offering["openness"] = None
            result.unmatched.append(
                {
                    "provider_slug": offering.get("provider_slug"),
                    "model_slug": slug,
                    "display_name": offering.get("display_name"),
                    "creator": offering.get("creator"),
                    "reason": "no openness row for this model slug",
                }
            )
            continue

        if len(candidates) > 1:
            offering["openness"] = None
            result.ambiguous.append(
                {
                    "provider_slug": offering.get("provider_slug"),
                    "model_slug": slug,
                    "display_name": offering.get("display_name"),
                    "creator": offering.get("creator"),
                    "candidates": [str(c.get("display_name")) for c in candidates],
                    "reason": "model slug maps to multiple openness rows",
                }
            )
            continue

        row = candidates[0]
        offering["openness"] = {name: row.get(name) for name in BREAKDOWN_FIELDS}
        used.add(str(slug))
        result.matched += 1

    result.openness_without_offering = sorted(set(by_slug) - used)
    return result
