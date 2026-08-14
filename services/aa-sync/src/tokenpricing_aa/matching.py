"""Join between the provider offering rows and the Openness Index rows.

The two AA datasets carry their model identity differently, and neither is
sufficient alone:

* Provider pages have a stable ``/models/<slug>`` anchor **and** an effort-suffixed
  display name (``GPT-5.6 Sol (xhigh)``).
* The Openness Index has no anchors at all — its only identity is the rendered
  display name plus a ``Creator`` column, and it disambiguates variants
  differently (``(Reasoning)`` / ``(Non-reasoning)``, sometimes
  ``(Reasoning, Max Effort)``).

So the join runs on a normalised name key, not on slugs and not on raw strings.
The parenthetical suffix space is wider than reasoning effort alone: it also
carries quantisation (``FP8``, ``NVFP4``), serving tier (``FAST``, ``Turbo``),
hosting platform (``Vertex``, ``AI Studio``) and snapshot dates. Openness is a
property of the *model*, not of how a given provider serves it, so those
serving-side tokens are dropped from the key while reasoning identity is kept.

Ambiguity is never resolved by guessing: candidates that disagree are reported
as ambiguous and left unmatched.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Reasoning-effort levels. These are part of model identity for openness purposes
# only insofar as AA publishes separate rows for them; where AA does not, the
# effort level is dropped by the tier-2 fallback below.
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

REASONING_TOKENS = {"reasoning": "reasoning", "non-reasoning": "non-reasoning"}

# Serving-side variation: quantisation, serving tier, hosting platform, snapshot
# labels. None of these change a model's openness, so they are not part of the key.
SERVING_TOKENS = {
    "fp4",
    "fp8",
    "fp16",
    "bf16",
    "int4",
    "int8",
    "nvfp4",
    "mxfp4",
    "mxfp8",
    "awq",
    "gptq",
    "fast",
    "turbo",
    "base",
    "preview",
    "exp",
    "experimental",
    "with fallback",
    "ai studio",
    "vertex",
    "bedrock",
    "chatgpt",
    "vision",
    "standard",
    "batch",
}

_MONTHS = (
    "jan|feb|mar|apr|may|jun|june|jul|july|aug|sep|sept|oct|nov|dec"
)
_DATE_TOKEN = re.compile(rf"^({_MONTHS})\b[\s'’]*\d{{0,4}}$", re.IGNORECASE)
_BARE_YEAR = re.compile(r"^'?\d{2,4}$")
_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Normalise a name to lowercase alphanumeric tokens.

    ``+`` is spelled out rather than stripped: ``Command A`` and ``Command A+``
    are different models, and folding the plus away silently merges them.
    """
    lowered = str(text or "").lower().replace("+", " plus ")
    return _NON_ALNUM.sub(" ", lowered).strip()


def normalize_creator(creator: str | None) -> str | None:
    """Creators are compared without spacing or punctuation (``Z AI`` -> ``zai``)."""
    if not creator:
        return None
    return _NON_ALNUM.sub("", str(creator).lower()) or None


def _is_serving_token(token: str) -> bool:
    if token in SERVING_TOKENS:
        return True
    if _DATE_TOKEN.match(token) or _BARE_YEAR.match(token):
        return True
    # "Sep '25", "Feb 2026"
    return bool(re.match(rf"^({_MONTHS})\s", token, re.IGNORECASE))


@dataclass(frozen=True)
class NameKey:
    """Normalised model identity used on both sides of the join."""

    base: str
    reasoning: str | None
    effort: str | None
    #: Serving-side suffixes recognised as safe to drop from the key.
    dropped: tuple[str, ...] = ()
    #: Suffixes that matched no known vocabulary. Also dropped from the key, but
    #: surfaced in dataset metadata so a new AA suffix type gets noticed rather
    #: than silently changing what the join considers the same model.
    unknown: tuple[str, ...] = ()


def parse_display_name(name: str) -> NameKey:
    """Split an AA display name into a base name and its classified suffixes."""
    raw_tokens: list[str] = []
    for group in _PARENTHETICAL.findall(name or ""):
        # "(Turbo, FP8)" and "(Reasoning, Max Effort)" pack several tokens in one group.
        raw_tokens.extend(part.strip() for part in group.split(",") if part.strip())

    base = _slugify(_PARENTHETICAL.sub(" ", name or ""))

    effort: str | None = None
    reasoning: str | None = None
    dropped: list[str] = []
    unknown: list[str] = []
    for token in raw_tokens:
        lowered = token.strip().lower()
        if lowered in REASONING_TOKENS:
            reasoning = REASONING_TOKENS[lowered]
        elif lowered in EFFORT_TOKENS:
            effort = EFFORT_TOKENS[lowered]
            # An explicit effort level implies the model is reasoning, unless the
            # name also says otherwise (AA emits "(Non-reasoning, high)").
            if reasoning is None:
                reasoning = "reasoning"
        elif _is_serving_token(lowered):
            dropped.append(token)
        else:
            unknown.append(token)

    # "(Non-reasoning, high)" — the explicit mode wins over the effort implication.
    for token in raw_tokens:
        if token.strip().lower() == "non-reasoning":
            reasoning = "non-reasoning"

    return NameKey(
        base=base,
        reasoning=reasoning,
        effort=effort,
        dropped=tuple(dropped),
        unknown=tuple(unknown),
    )


# Order matters: "-non-reasoning" must be tested before "-reasoning".
_SLUG_REASONING_SUFFIXES = (
    ("-non-reasoning", "non-reasoning"),
    ("-nonreasoning", "non-reasoning"),
    ("-reasoning", "reasoning"),
)


def enrich_key_from_slug(key: NameKey, model_slug: str | None) -> NameKey:
    """Fill in variant identity the display name omits but the slug states.

    Provider pages sometimes render a bare name (``Grok 4 Fast``) while the
    ``/models/`` href spells the variant out (``grok-4-fast-reasoning``). The
    Openness Index splits those models into ``(Reasoning)`` / ``(Non-reasoning)``
    rows, so without this the row is only resolvable as ambiguous.

    This reads variant identity **only** from an explicit trailing suffix. It
    never infers effort from a bare slug: which effort level owns the
    unsuffixed slug varies per model (``gpt-oss-120b`` is high, ``claude-opus-5``
    is max), so that is not derivable by rule.
    """
    if not model_slug:
        return key
    slug = model_slug.lower()
    reasoning, effort = key.reasoning, key.effort

    if reasoning is None:
        for suffix, mode in _SLUG_REASONING_SUFFIXES:
            if slug.endswith(suffix):
                reasoning = mode
                break

    if effort is None:
        for level in EFFORT_TOKENS:
            if " " in level:
                continue
            if slug.endswith(f"-{level}"):
                effort = level
                if reasoning is None:
                    reasoning = "reasoning"
                break

    if reasoning == key.reasoning and effort == key.effort:
        return key
    return NameKey(
        base=key.base,
        reasoning=reasoning,
        effort=effort,
        dropped=key.dropped,
        unknown=key.unknown,
    )


def _strip_creator_prefix(base: str, creator: str | None) -> str | None:
    """Drop a leading creator name from a base name, if it is spelled there.

    ``NVIDIA Nemotron 3 Nano 30B A3B`` and ``Nemotron 3 Ultra 550B A55B`` both
    appear in the Openness Index, so the creator prefix cannot be assumed either
    way and both spellings have to be tried.
    """
    wanted = normalize_creator(creator)
    if not wanted:
        return None
    words = base.split()
    accumulated = ""
    for index, word in enumerate(words):
        accumulated += _NON_ALNUM.sub("", word)
        if not wanted.startswith(accumulated):
            return None
        if accumulated == wanted and index + 1 < len(words):
            return " ".join(words[index + 1 :])
    return None


def _base_variants(key: NameKey, creator: str | None) -> list[str]:
    """Openness sometimes prefixes the creator onto the model name, sometimes not."""
    variants = [key.base]
    trimmed = _strip_creator_prefix(key.base, creator)
    if trimmed:
        variants.append(trimmed)
    return variants


OPENNESS_COMPONENTS = (
    "openness_index",
    "model_availability",
    "model_transparency",
    "pre_training_data_access",
    "pre_training_data_license",
    "post_training_data_access",
    "post_training_data_license",
)


def _component_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(field_name) for field_name in OPENNESS_COMPONENTS)


@dataclass
class OpennessIndexTable:
    """Lookup structure over the Openness Index rows."""

    rows: list[dict[str, Any]]
    _exact: dict[tuple[str, str | None, str | None], list[dict[str, Any]]] = field(
        default_factory=dict
    )
    _by_base_mode: dict[tuple[str, str | None], list[dict[str, Any]]] = field(
        default_factory=dict
    )
    _by_base: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for row in self.rows:
            key = parse_display_name(row["display_name"])
            row.setdefault("_key", key)
            for base in _base_variants(key, row.get("creator")):
                self._exact.setdefault((base, key.reasoning, key.effort), []).append(row)
                self._by_base_mode.setdefault((base, key.reasoning), []).append(row)
                self._by_base.setdefault(base, []).append(row)

    def candidates(self, tier: str, bases: list[str], key: NameKey) -> list[dict[str, Any]]:
        """Look up candidate openness rows for one confidence tier."""
        found: list[dict[str, Any]] = []
        for base in bases:
            if tier == "exact":
                found.extend(self._exact.get((base, key.reasoning, key.effort), []))
            elif tier == "base+mode":
                found.extend(self._by_base_mode.get((base, key.reasoning), []))
            else:
                found.extend(self._by_base.get(base, []))
        # The same row can be reached through several base variants.
        unique: list[dict[str, Any]] = []
        for row in found:
            if not any(row is seen for seen in unique):
                unique.append(row)
        return unique

    @staticmethod
    def collapse(
        candidates: Iterable[dict[str, Any]], creator: str | None
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Return a single row when candidates agree on every openness component.

        A creator, when known on both sides, is a hard filter: two different
        creators shipping a similarly named model must never be merged.
        """
        pool = list(candidates)
        wanted = normalize_creator(creator)
        if wanted:
            filtered = [
                row for row in pool if normalize_creator(row.get("creator")) == wanted
            ]
            if filtered:
                pool = filtered
            elif any(normalize_creator(row.get("creator")) for row in pool):
                # Every candidate names a different creator: same model name,
                # different lab. Reject outright rather than falling back.
                return None, []
        if not pool:
            return None, []
        signatures = {_component_signature(row) for row in pool}
        if len(signatures) == 1:
            return pool[0], pool
        return None, pool


@dataclass
class JoinResult:
    matched: int = 0
    unmatched: list[dict[str, Any]] = field(default_factory=list)
    ambiguous: list[dict[str, Any]] = field(default_factory=list)
    tiers: dict[str, int] = field(default_factory=dict)


def join_openness(
    offerings: list[dict[str, Any]], openness_rows: list[dict[str, Any]]
) -> JoinResult:
    """Attach openness components to offering rows in place.

    Matching runs in descending order of confidence:

    1. base name + reasoning mode + effort level
    2. base name + reasoning mode, when every candidate agrees on the components
       (AA frequently publishes one openness row for all effort levels)
    3. base name alone, when every candidate agrees

    Anything that survives all three without a unique, self-consistent answer is
    recorded as ambiguous or unmatched — never guessed.
    """
    table = OpennessIndexTable(openness_rows)
    result = JoinResult()

    for offering in offerings:
        key = enrich_key_from_slug(
            parse_display_name(offering["display_name"]), offering.get("model_slug")
        )
        creator = offering.get("creator")
        offering["openness"] = None
        offering["openness_match"] = None

        chosen: dict[str, Any] | None = None
        tier_used: str | None = None
        pool: list[dict[str, Any]] = []

        bases = _base_variants(key, creator)
        for tier in ("exact", "base+mode", "base"):
            candidates = table.candidates(tier, bases, key)
            if not candidates:
                continue
            chosen, pool = table.collapse(candidates, creator)
            if chosen is not None:
                tier_used = tier
                break
            if pool:
                # Candidates exist but disagree: stop here rather than falling
                # through to a looser tier that would only be more ambiguous.
                break

        if chosen is not None and tier_used is not None:
            offering["openness"] = {
                name: chosen.get(name) for name in OPENNESS_COMPONENTS
            }
            offering["openness_match"] = {
                "tier": tier_used,
                "openness_display_name": chosen["display_name"],
                "openness_creator": chosen.get("creator"),
            }
            result.matched += 1
            result.tiers[tier_used] = result.tiers.get(tier_used, 0) + 1
        elif pool:
            result.ambiguous.append(
                {
                    "provider_slug": offering.get("provider_slug"),
                    "model_slug": offering.get("model_slug"),
                    "display_name": offering["display_name"],
                    "creator": creator,
                    "normalized_base": key.base,
                    "candidates": sorted({row["display_name"] for row in pool}),
                    "reason": "candidates disagree on openness components",
                }
            )
        else:
            result.unmatched.append(
                {
                    "provider_slug": offering.get("provider_slug"),
                    "model_slug": offering.get("model_slug"),
                    "display_name": offering["display_name"],
                    "creator": creator,
                    "normalized_base": key.base,
                    "reason": "no openness row for this model",
                }
            )

    return result
