"""Reasoning-variant identification and the exact-slug Openness join."""

from __future__ import annotations

import pytest

from tokenpricing_aa.matching import join_openness, parse_variant


def test_reasoning_mode_is_read_from_the_boolean_not_the_name():
    assert parse_variant("Kimi K2.6", "kimi-k2-6", True).reasoning_mode == "reasoning"
    assert (
        parse_variant("Kimi K2.6", "kimi-k2-6", False).reasoning_mode
        == "non-reasoning"
    )
    assert parse_variant("Kimi K2.6", "kimi-k2-6", None).reasoning_mode is None


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("claude-opus-5-low", "low"),
        ("claude-opus-5-medium", "medium"),
        ("claude-opus-5-high", "high"),
        ("claude-opus-5-xhigh", "xhigh"),
        ("gpt-5-nano-minimal", "minimal"),
    ],
)
def test_effort_comes_from_the_slug_suffix(slug, expected):
    assert parse_variant("whatever", slug, True).reasoning_effort == expected


def test_max_effort_is_the_unsuffixed_slug_and_read_from_the_label():
    """claude-opus-5 is max; only the label says so."""
    variant = parse_variant("Claude Opus 5 (max)", "claude-opus-5", True)
    assert variant.reasoning_effort == "max"


def test_effort_falls_back_to_the_label_parenthetical():
    variant = parse_variant("GPT-5.2 Codex (xhigh)", "gpt-5-2-codex", True)
    assert variant.reasoning_effort == "xhigh"


def test_non_reasoning_slug_suffix_overrides_the_boolean():
    variant = parse_variant("GPT-5.6 Sol (Non-reasoning)", "gpt-5-6-sol-non-reasoning", None)
    assert variant.reasoning_mode == "non-reasoning"


def test_serving_side_parentheticals_are_not_efforts():
    """Quantisation and platform tags used to need a whole vocabulary to exclude."""
    for name in (
        "GLM-5.2 (FP4)",
        "Gemini 2.5 Flash (AI Studio)",
        "Hermes 4 405B (FP8)",
        "Llama 3.3 70B Base",
    ):
        assert parse_variant(name, "some-model", True).reasoning_effort is None


def test_no_effort_where_aa_publishes_no_variant():
    assert parse_variant("Nemotron 3 Ultra", "nemotron-3-ultra", True).reasoning_effort is None


# --- the openness join ----------------------------------------------------- #


def _offering(**kw):
    base = {
        "provider_slug": "nebius",
        "model_slug": "kimi-k2-6",
        "display_name": "Kimi K2.6",
        "creator": "Kimi",
    }
    base.update(kw)
    return base


def _openness(slug="kimi-k2-6", **kw):
    row = {
        "model_slug": slug,
        "display_name": "Kimi K2.6",
        "openness_index": 38.9,
        "model_availability": 6,
        "model_transparency": 1,
        "pre_training_data_access": 0,
        "pre_training_data_license": 0,
        "post_training_data_access": 0,
        "post_training_data_license": 0,
        "transparency_methodology": 1,
        "transparency_pre_training_data": 0,
        "transparency_post_training_data": 0,
    }
    row.update(kw)
    return row


def test_exact_slug_match_attaches_the_breakdown():
    offerings = [_offering()]
    result = join_openness(offerings, [_openness()])
    assert result.matched == 1
    assert offerings[0]["openness"]["openness_index"] == 38.9
    assert offerings[0]["openness"]["transparency_methodology"] == 1


def test_model_with_no_openness_row_is_recorded_not_guessed():
    offerings = [_offering(model_slug="unscored-model")]
    result = join_openness(offerings, [_openness()])
    assert result.matched == 0
    assert offerings[0]["openness"] is None
    assert result.unmatched[0]["model_slug"] == "unscored-model"


def test_display_name_differences_do_not_affect_the_join():
    """The old join normalised names; this one never looks at them."""
    offerings = [_offering(display_name="Kimi K2.6 (FP8, Turbo) Sept '26")]
    result = join_openness(offerings, [_openness()])
    assert result.matched == 1


def test_every_offering_of_a_model_gets_the_same_breakdown():
    offerings = [
        _offering(provider_slug="nebius"),
        _offering(provider_slug="azure"),
        _offering(provider_slug="novita"),
    ]
    result = join_openness(offerings, [_openness()])
    assert result.matched == 3
    assert all(o["openness"]["openness_index"] == 38.9 for o in offerings)


def test_duplicate_openness_slugs_are_ambiguous_not_arbitrary():
    offerings = [_offering()]
    result = join_openness(offerings, [_openness(), _openness(openness_index=12.0)])
    assert result.matched == 0
    assert len(result.ambiguous) == 1
    assert offerings[0]["openness"] is None


def test_scored_models_nobody_serves_are_reported():
    result = join_openness([_offering()], [_openness(), _openness(slug="orphan")])
    assert result.openness_without_offering == ["orphan"]


def test_offering_without_a_slug_is_unmatched_rather_than_crashing():
    offerings = [_offering(model_slug=None)]
    result = join_openness(offerings, [_openness()])
    assert result.matched == 0
    assert len(result.unmatched) == 1
