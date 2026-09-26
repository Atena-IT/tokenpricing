"""Projection of payload objects into flat records."""

from __future__ import annotations

import pytest

from tests.factories import leaderboard_page, make_page, offering, openness_page
from tokenpricing_aa.parse import (
    OFFERING_FIELDS,
    ParseError,
    dig,
    parse_leaderboard,
    parse_openness,
)


def test_projects_every_declared_field():
    (row,) = parse_leaderboard(leaderboard_page())
    assert set(row) == {name for name, _ in OFFERING_FIELDS}


def test_reads_values_at_full_precision():
    """No rounding, no currency stripping: the payload is already typed."""
    (row,) = parse_leaderboard(leaderboard_page())
    assert row["intelligence_index"] == 45.1382483763163
    assert row["input_price_usd_per_1m"] == 0.95
    assert row["output_price_usd_per_1m"] == 4
    assert row["cost_per_task_usd"] == 0.7586225879503231
    assert row["context_window"] == 262144


def test_reads_booleans_as_booleans():
    (row,) = parse_leaderboard(leaderboard_page())
    assert row["intelligence_index_estimated"] is False
    assert row["supports_function_calling"] is True
    assert row["deprecated"] is True
    assert row["is_open_weights"] is True


def test_carries_identity_fields_the_rendered_table_lacks():
    (row,) = parse_leaderboard(leaderboard_page())
    assert row["offering_id"] == "10b47ef3-f0b9-4d9e-808a-9ed9ad14e73f"
    assert row["host_api_id"] == "moonshotai/Kimi-K2.6"
    assert row["omniscience_index"] == 5.3
    assert row["p95_output_tokens_per_second"] == 330.205485545576


def test_absent_nested_values_become_none_not_zero():
    row_obj = offering(model={"livecodebench": None}, pricing={"cacheHitPrice": None})
    (row,) = parse_leaderboard(leaderboard_page([row_obj]))
    assert row["livecodebench"] is None
    assert row["cache_hit_price_usd_per_1m"] is None


def test_nested_path_reads_through_sub_objects():
    (row,) = parse_leaderboard(leaderboard_page())
    assert row["briefcase_elo"] == 818.82
    assert row["creator"] == "Kimi"
    assert row["provider_slug"] == "nebius"


def test_dig_dead_ends_to_none_rather_than_raising():
    assert dig({"a": {"b": 1}}, ("a", "b")) == 1
    assert dig({"a": {"b": 1}}, ("a", "missing")) is None
    assert dig({"a": 1}, ("a", "b")) is None
    assert dig(None, ("a",)) is None


def test_payload_without_offerings_is_a_parse_error():
    html = make_page({"data": [{"unrelated": True}]})
    with pytest.raises(ParseError, match="no offering objects"):
        parse_leaderboard(html)


def test_offerings_without_ids_are_a_parse_error():
    html = leaderboard_page([offering(id=None)])
    with pytest.raises(ParseError, match="no id"):
        parse_leaderboard(html)


# --- openness ------------------------------------------------------------- #

# The default fixture entity has this id; "dangling" deliberately points nowhere.
_RESOLVABLE_MODEL_ID = "f0083258-8646-45b8-8082-7aaf6c2ea82a"


def _score(record_id: str = "resolvable", index: float = 38.888888888888886):
    return {
        "id": record_id,
        "modelId": _RESOLVABLE_MODEL_ID if record_id == "resolvable" else "nowhere",
        "opennessIndex": index,
        "modelAvailability": 6,
        "modelTransparency": 1,
        "dataPretrainAccess": 0,
        "dataPretrainLicense": 0,
        "dataPosttrainAccess": 0,
        "dataPosttrainLicense": 0,
        "transparencyMethodology": 1,
        "transparencyPreTrainingData": 0,
        "transparencyPostTrainingData": 0,
    }


def test_openness_resolves_each_score_to_a_model_slug():
    (row,) = parse_openness(openness_page())
    assert row["model_slug"] == "kimi-k2-6"
    assert row["display_name"] == "Kimi K2.6"
    assert row["openness_index"] == 38.888888888888886


def test_openness_includes_components_absent_from_the_rendered_table():
    (row,) = parse_openness(openness_page())
    assert row["transparency_methodology"] == 1
    assert row["transparency_pre_training_data"] == 0
    assert row["transparency_post_training_data"] == 0


def test_openness_record_with_unresolvable_model_id_keeps_its_score():
    """One dangling modelId must not discard its score, nor fail the run."""
    rows = parse_openness(openness_page(records=[_score(), _score("dangling", 12.5)]))
    by_id = {row["openness_record_id"]: row for row in rows}
    assert by_id["dangling"]["model_slug"] is None
    assert by_id["dangling"]["openness_index"] == 12.5
    assert by_id["resolvable"]["model_slug"] == "kimi-k2-6"


def test_openness_with_no_resolvable_models_at_all_is_a_parse_error():
    page = openness_page(entities=[{"id": "other", "slug": None, "name": "X"}])
    with pytest.raises(ParseError, match="modelId -> model relationship"):
        parse_openness(page)


def test_openness_without_score_records_is_a_parse_error():
    with pytest.raises(ParseError, match="no 'opennessIndex' records"):
        parse_openness(make_page({"models": [{"id": "a", "slug": "b"}]}))
