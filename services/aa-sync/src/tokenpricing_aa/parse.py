"""Projection of the Artificial Analysis flight payload into flat records.

There is no HTML table parsing here and no value cleaning. The payload carries
typed JSON -- floats at full precision, real booleans, explicit ``null`` -- so the
em-dash / U+2212 / currency-symbol / thousands-separator / trailing-asterisk
handling that a table-scraping parser needs has no counterpart in this module.

Two things AA's own table cannot express survive here:

* ``intelligence_index_estimated`` is a real boolean field rather than a trailing
  asterisk on a rendered score.
* ``deprecated`` distinguishes superseded offerings, which the leaderboard's
  ``Status: Current`` view hides but the payload retains.
"""

from __future__ import annotations

from typing import Any

from tokenpricing_aa.flight import (
    PayloadNotFoundError,
    clean,
    objects_with_key,
    reconstruct_payload,
)

# Marker keys used to locate each record type in the payload stream.
OFFERING_MARKER = "hostApiId"
OPENNESS_MARKER = "opennessIndex"

# (output field, path into the offering object). The single source of truth for
# the projection; ``schema.py`` builds its drift manifest from these paths, so a
# field cannot be read here without being covered there.
OFFERING_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("offering_id", ("id",)),
    ("display_name", ("label",)),
    ("host_api_id", ("hostApiId",)),
    ("footnotes", ("footnotes",)),
    ("provider_slug", ("host", "slug")),
    ("provider_name", ("host", "name")),
    ("model_slug", ("model", "slug")),
    ("creator", ("model", "creator", "name")),
    ("is_open_weights", ("model", "isOpenWeights")),
    ("deprecated", ("model", "deprecated")),
    ("reasoning_model", ("model", "reasoningModel")),
    ("size_class", ("model", "sizeClass")),
    ("context_window", ("features", "contextWindowTokens")),
    ("supports_function_calling", ("features", "functionCalling")),
    ("supports_json_mode", ("features", "jsonMode")),
    ("openai_compatible", ("features", "openaiCompatible")),
    # Intelligence
    ("intelligence_index", ("model", "intelligenceIndex")),
    ("intelligence_index_estimated", ("model", "intelligenceIndexIsEstimated")),
    ("omniscience_index", ("model", "omniscience")),
    ("omniscience_accuracy", ("model", "omniscienceAccuracy")),
    ("omniscience_non_hallucination", ("model", "omniscienceNonHallucination")),
    ("gdpval_normalized", ("model", "gdpvalNormalized")),
    ("briefcase_elo", ("model", "briefcase", "elo")),
    ("terminalbench_hard", ("model", "terminalbenchHard")),
    ("terminalbench_v21", ("model", "terminalbenchV21")),
    ("tau2_bench_telecom", ("model", "tau2")),
    ("tau3_banking", ("model", "tauBanking")),
    ("aa_lcr", ("model", "lcr")),
    ("humanitys_last_exam", ("model", "hle")),
    ("gpqa_diamond", ("model", "gpqa")),
    ("scicode", ("model", "scicode")),
    ("ifbench", ("model", "ifbench")),
    ("critpt", ("model", "critpt")),
    ("apex_agents", ("model", "apexAgents")),
    ("itbench_sre", ("model", "itbenchSre")),
    ("mmmu_pro", ("model", "mmmuPro")),
    ("livecodebench", ("model", "livecodebench")),
    ("aime_2025", ("model", "aime25")),
    ("automation_bench", ("model", "automationBench")),
    ("harvey_lab", ("model", "harveyLab")),
    # Price
    ("cost_per_task_usd", ("pricing", "costPerTask")),
    ("price_class", ("pricing", "priceClass")),
    ("input_price_usd_per_1m", ("pricing", "price1mInputTokens")),
    ("output_price_usd_per_1m", ("pricing", "price1mOutputTokens")),
    ("cache_hit_price_usd_per_1m", ("pricing", "cacheHitPrice")),
    ("cache_write_price_usd_per_1m", ("pricing", "cacheWritePrice")),
    # Speed
    ("median_output_tokens_per_second", ("performance", "medianOutputTokensPerSecond")),
    ("p5_output_tokens_per_second", ("performance", "percentile05OutputTokensPerSecond")),
    ("p25_output_tokens_per_second", ("performance", "quartile25OutputTokensPerSecond")),
    ("p75_output_tokens_per_second", ("performance", "quartile75OutputTokensPerSecond")),
    ("p95_output_tokens_per_second", ("performance", "percentile95OutputTokensPerSecond")),
    # Latency
    ("median_first_chunk_seconds", ("performance", "medianTimeToFirstTokenSeconds")),
    ("p5_first_chunk_seconds", ("performance", "percentile05TimeToFirstTokenSeconds")),
    ("p25_first_chunk_seconds", ("performance", "quartile25TimeToFirstTokenSeconds")),
    ("p75_first_chunk_seconds", ("performance", "quartile75TimeToFirstTokenSeconds")),
    ("p95_first_chunk_seconds", ("performance", "percentile95TimeToFirstTokenSeconds")),
    (
        "first_answer_token_seconds",
        ("performance", "medianTimeToFirstAnswerTokenSeconds"),
    ),
    ("total_response_seconds", ("performance", "medianEndToEndResponseTimeSeconds")),
    ("reasoning_time_seconds", ("performance", "medianReasoningTimeSeconds")),
)

OPENNESS_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("openness_record_id", ("id",)),
    ("model_id", ("modelId",)),
    ("openness_index", ("opennessIndex",)),
    ("model_availability", ("modelAvailability",)),
    ("model_transparency", ("modelTransparency",)),
    ("pre_training_data_access", ("dataPretrainAccess",)),
    ("pre_training_data_license", ("dataPretrainLicense",)),
    ("post_training_data_access", ("dataPosttrainAccess",)),
    ("post_training_data_license", ("dataPosttrainLicense",)),
    # Published in the payload but absent from the rendered table.
    ("transparency_methodology", ("transparencyMethodology",)),
    ("transparency_pre_training_data", ("transparencyPreTrainingData",)),
    ("transparency_post_training_data", ("transparencyPostTrainingData",)),
)


class ParseError(ValueError):
    """The payload was found and decoded but does not hold the expected records."""


def dig(obj: Any, path: tuple[str, ...]) -> Any:
    """Follow ``path`` through nested dicts, returning ``None`` if it dead-ends."""
    cursor: Any = obj
    for part in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(part)
    return cursor


def project(obj: dict[str, Any], fields: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, Any]:
    return {name: dig(obj, path) for name, path in fields}


def offering_objects(html: str) -> list[dict[str, Any]]:
    """Raw offering objects from a page's payload, ``$undefined`` normalised away."""
    payload = reconstruct_payload(html)
    objects = [clean(obj) for obj in objects_with_key(payload, OFFERING_MARKER)]
    if not objects:
        raise ParseError(
            "payload reconstructed but contains no offering objects "
            f"(no {OFFERING_MARKER!r} records)"
        )
    return objects


def parse_leaderboard(html: str) -> list[dict[str, Any]]:
    """Project every offering on the provider leaderboard into a flat record.

    One offering is one (provider x model x reasoning variant x serving endpoint).
    ``offering_id`` is AA's own uuid and the only field unique across the set --
    see ``docs/database.md`` for why no composite of the human-readable fields is.
    """
    records = [project(obj, OFFERING_FIELDS) for obj in offering_objects(html)]
    missing = [r for r in records if not r.get("offering_id")]
    if missing:
        raise ParseError(f"{len(missing)} offering records carry no id")
    return records


def parse_openness(html: str) -> list[dict[str, Any]]:
    """Project the Openness Index, resolving each score to its model slug.

    Openness records live in their own id space and reference a model by
    ``modelId``; that uuid does not appear anywhere in the leaderboard payload, so
    the cross-dataset join runs on the model *slug* the openness page itself
    supplies for each scored model.
    """
    payload = reconstruct_payload(html)
    records = [clean(obj) for obj in objects_with_key(payload, OPENNESS_MARKER)]
    if not records:
        raise ParseError(
            f"openness payload contains no {OPENNESS_MARKER!r} records"
        )

    entities = {
        obj["id"]: obj
        for obj in objects_with_key(payload, "slug")
        if obj.get("id") and obj.get("slug")
    }

    rows: list[dict[str, Any]] = []
    unresolved = 0
    for record in records:
        row = project(record, OPENNESS_FIELDS)
        entity = entities.get(str(row.get("model_id")))
        if entity is None:
            unresolved += 1
            row["model_slug"] = None
            row["display_name"] = None
        else:
            row["model_slug"] = entity.get("slug")
            row["display_name"] = entity.get("name")
            row["model_family_slug"] = entity.get("model_family_slug")
        rows.append(row)

    if unresolved == len(rows):
        raise ParseError(
            f"none of the {len(rows)} openness records resolved to a model entity; "
            "the modelId -> model relationship has changed"
        )
    return rows


__all__ = [
    "OFFERING_FIELDS",
    "OPENNESS_FIELDS",
    "ParseError",
    "PayloadNotFoundError",
    "dig",
    "offering_objects",
    "parse_leaderboard",
    "parse_openness",
    "project",
]
