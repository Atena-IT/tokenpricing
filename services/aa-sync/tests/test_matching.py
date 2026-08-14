from typing import Any

from tokenpricing_aa.matching import (
    enrich_key_from_slug,
    join_openness,
    normalize_creator,
    parse_display_name,
)


def openness_row(
    display_name: str,
    creator: str = "Alibaba",
    openness_index: float = 66.67,
    availability: float = 6.0,
    transparency: float = 6.0,
) -> dict[str, Any]:
    return {
        "rank": 1,
        "creator": creator,
        "display_name": display_name,
        "openness_index": openness_index,
        "intelligence_index": 50.0,
        "model_availability": availability,
        "model_transparency": transparency,
        "pre_training_data_access": 1.0,
        "pre_training_data_license": 1.0,
        "post_training_data_access": 1.0,
        "post_training_data_license": 1.0,
    }


def offering(
    display_name: str, creator: str = "Alibaba", provider: str = "fireworks"
) -> dict[str, Any]:
    return {
        "provider_slug": provider,
        "model_slug": "some-slug",
        "display_name": display_name,
        "creator": creator,
    }


class TestParseDisplayName:
    def test_reasoning_effort_is_captured(self) -> None:
        key = parse_display_name("GPT-5.6 Sol (xhigh)")
        assert key.base == "gpt 5 6 sol"
        assert key.effort == "xhigh"
        assert key.reasoning == "reasoning"

    def test_non_reasoning_is_captured(self) -> None:
        key = parse_display_name("Qwen3.5 397B A17B (Non-reasoning)")
        assert key.reasoning == "non-reasoning"
        assert key.effort is None

    def test_bare_reasoning_token(self) -> None:
        assert parse_display_name("Nemotron 3 Ultra (Reasoning)").reasoning == "reasoning"

    def test_compound_reasoning_and_effort(self) -> None:
        key = parse_display_name("K2-V2 (Reasoning, Max Effort)")
        assert key.reasoning == "reasoning"
        assert key.effort == "max"

    def test_explicit_non_reasoning_beats_effort_implication(self) -> None:
        """AA emits "(Non-reasoning, high)"; the stated mode must win."""
        key = parse_display_name("Some Model (Non-reasoning, high)")
        assert key.reasoning == "non-reasoning"
        assert key.effort == "high"

    def test_quantisation_and_serving_tokens_are_dropped_not_part_of_identity(
        self,
    ) -> None:
        """Openness is a model property; quantisation and serving tier are not."""
        for name in (
            "Llama 4 Maverick (FP8)",
            "Llama 4 Maverick (NVFP4)",
            "Llama 4 Maverick (Turbo, FP8)",
            "Llama 4 Maverick (FAST)",
        ):
            key = parse_display_name(name)
            assert key.base == "llama 4 maverick", name
            assert key.effort is None, name

    def test_platform_and_snapshot_tokens_are_dropped(self) -> None:
        for name in (
            "Gemini 3 Pro (AI Studio)",
            "Gemini 3 Pro (Vertex)",
            "Gemini 3 Pro (Sep '25)",
            "Gemini 3 Pro (Feb 2026)",
        ):
            assert parse_display_name(name).base == "gemini 3 pro", name

    def test_known_serving_tokens_are_classified_separately_from_unknown_ones(
        self,
    ) -> None:
        """An unrecognised suffix is still dropped from the key, but flagged so a
        new AA suffix type does not change join behaviour unnoticed."""
        known = parse_display_name("Some Model (FP8)")
        assert known.dropped == ("FP8",)
        assert known.unknown == ()

        novel = parse_display_name("Some Model (Warp Drive)")
        assert novel.dropped == ()
        assert novel.unknown == ("Warp Drive",)
        assert novel.base == "some model"

    def test_effort_survives_alongside_dropped_tokens(self) -> None:
        key = parse_display_name("Kimi K3 (max) (FAST)")
        assert key.base == "kimi k3"
        assert key.effort == "max"
        assert "FAST" in key.dropped

    def test_plus_suffix_is_significant_not_stripped(self) -> None:
        """``Command A`` and ``Command A+`` are different Cohere models."""
        assert parse_display_name("Command A").base == "command a"
        assert parse_display_name("Command A+").base == "command a plus"
        assert (
            parse_display_name("Command A").base != parse_display_name("Command A+").base
        )

    def test_bare_name_has_no_variant_identity(self) -> None:
        key = parse_display_name("Kimi K2.6")
        assert key.base == "kimi k2 6"
        assert key.reasoning is None
        assert key.effort is None


class TestEnrichKeyFromSlug:
    def test_slug_supplies_reasoning_mode_the_name_omits(self) -> None:
        key = enrich_key_from_slug(
            parse_display_name("Grok 4 Fast"), "grok-4-fast-reasoning"
        )
        assert key.reasoning == "reasoning"

    def test_slug_supplies_non_reasoning_mode(self) -> None:
        key = enrich_key_from_slug(
            parse_display_name("GPT-5.1"), "gpt-5-1-non-reasoning"
        )
        assert key.reasoning == "non-reasoning"

    def test_slug_supplies_effort_level(self) -> None:
        key = enrich_key_from_slug(parse_display_name("GPT-5.1"), "gpt-5-1-high")
        assert key.effort == "high"
        assert key.reasoning == "reasoning"

    def test_display_name_wins_over_slug(self) -> None:
        key = enrich_key_from_slug(
            parse_display_name("Some Model (Non-reasoning)"), "some-model-reasoning"
        )
        assert key.reasoning == "non-reasoning"

    def test_bare_slug_effort_is_never_guessed(self) -> None:
        """Which effort owns the unsuffixed slug varies per model, so it is not
        derivable by rule — gpt-oss-120b is high, claude-opus-5 is max."""
        for slug in ("gpt-oss-120b", "claude-opus-5"):
            key = enrich_key_from_slug(parse_display_name("Whatever"), slug)
            assert key.effort is None, slug

    def test_missing_slug_leaves_key_untouched(self) -> None:
        original = parse_display_name("Kimi K3 (max)")
        assert enrich_key_from_slug(original, None) is original
        assert enrich_key_from_slug(original, "") is original


class TestNormalizeCreator:
    def test_spacing_and_case_are_ignored(self) -> None:
        assert normalize_creator("Z AI") == normalize_creator("ZAI") == "zai"

    def test_missing_creator_is_none(self) -> None:
        assert normalize_creator(None) is None
        assert normalize_creator("") is None


class TestJoin:
    def test_exact_variant_match(self) -> None:
        offerings = [offering("Qwen3.5 397B A17B (Non-reasoning)")]
        rows = [
            openness_row("Qwen3.5 397B A17B (Reasoning)", openness_index=66.67),
            openness_row("Qwen3.5 397B A17B (Non-reasoning)", openness_index=55.55),
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 1
        assert result.tiers == {"exact": 1}
        assert offerings[0]["openness"]["openness_index"] == 55.55
        assert offerings[0]["openness_match"]["tier"] == "exact"

    def test_reasoning_variants_are_not_collapsed(self) -> None:
        """The spike's headline risk: a naive name join merges these two."""
        offerings = [
            offering("Qwen3.5 397B A17B (max)"),
            offering("Qwen3.5 397B A17B (Non-reasoning)"),
        ]
        rows = [
            openness_row("Qwen3.5 397B A17B (Reasoning)", openness_index=66.67),
            openness_row("Qwen3.5 397B A17B (Non-reasoning)", openness_index=55.55),
        ]

        join_openness(offerings, rows)

        assert offerings[0]["openness"]["openness_index"] == 66.67
        assert offerings[1]["openness"]["openness_index"] == 55.55

    def test_effort_is_dropped_when_openness_publishes_one_row_per_model(self) -> None:
        """AA usually publishes a single openness row for all effort levels."""
        offerings = [offering("GPT-5.6 Sol (xhigh)", creator="OpenAI")]
        rows = [openness_row("GPT-5.6 Sol (Reasoning)", creator="OpenAI")]

        result = join_openness(offerings, rows)

        assert result.matched == 1
        assert result.tiers == {"base+mode": 1}

    def test_quantisation_variants_all_match_the_same_openness_row(self) -> None:
        offerings = [
            offering("Llama 4 Maverick (FP8)", creator="Meta"),
            offering("Llama 4 Maverick (NVFP4)", creator="Meta"),
            offering("Llama 4 Maverick", creator="Meta"),
        ]
        rows = [openness_row("Llama 4 Maverick", creator="Meta", openness_index=77.78)]

        result = join_openness(offerings, rows)

        assert result.matched == 3
        assert all(o["openness"]["openness_index"] == 77.78 for o in offerings)

    def test_creator_prefix_on_openness_side_still_matches(self) -> None:
        offerings = [offering("Nemotron 3 Nano 30B A3B (Non-reasoning)", creator="NVIDIA")]
        rows = [
            openness_row(
                "NVIDIA Nemotron 3 Nano 30B A3B (Non-reasoning)", creator="NVIDIA"
            )
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 1

    def test_different_creators_are_never_merged(self) -> None:
        offerings = [offering("Nova Pro", creator="Amazon")]
        rows = [openness_row("Nova Pro", creator="Some Other Lab")]

        result = join_openness(offerings, rows)

        assert result.matched == 0
        assert len(result.unmatched) == 1

    def test_plus_variant_does_not_borrow_the_base_models_openness(self) -> None:
        offerings = [offering("Command A+", creator="Cohere")]
        rows = [
            openness_row("Command A", creator="Cohere", openness_index=33.33),
            openness_row("Command A+", creator="Cohere", openness_index=22.22),
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 1
        assert offerings[0]["openness"]["openness_index"] == 22.22

    def test_bare_name_against_split_reasoning_rows_is_ambiguous(self) -> None:
        """Observed live: provider pages list a bare ``GPT-5.1`` while the
        Openness Index splits it into ``(Non-reasoning)`` and ``(high)``."""
        offerings = [offering("GPT-5.1", creator="OpenAI")]
        rows = [
            openness_row("GPT-5.1 (Non-reasoning)", creator="OpenAI", openness_index=11.11),
            openness_row("GPT-5.1 (high)", creator="OpenAI", openness_index=22.22),
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 0
        assert len(result.ambiguous) == 1
        assert offerings[0]["openness"] is None

    def test_slug_resolves_what_the_display_name_leaves_ambiguous(self) -> None:
        """Observed live: azure lists a bare ``Grok 4 Fast`` under the slug
        ``grok-4-fast-reasoning``, which resolves the split openness rows."""
        offer = offering("Grok 4 Fast", creator="SpaceXAI")
        offer["model_slug"] = "grok-4-fast-reasoning"
        rows = [
            openness_row("Grok 4 Fast (Reasoning)", creator="SpaceXAI", openness_index=22.22),
            openness_row(
                "Grok 4 Fast (Non-reasoning)", creator="SpaceXAI", openness_index=11.11
            ),
        ]

        result = join_openness([offer], rows)

        assert result.matched == 1
        assert result.ambiguous == []
        assert offer["openness"]["openness_index"] == 22.22

    def test_disagreeing_candidates_are_reported_ambiguous_not_guessed(self) -> None:
        offerings = [offering("Mystery Model")]
        rows = [
            openness_row("Mystery Model (Reasoning)", openness_index=88.89),
            openness_row("Mystery Model (Non-reasoning)", openness_index=11.11),
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 0
        assert len(result.ambiguous) == 1
        entry = result.ambiguous[0]
        assert entry["candidates"] == [
            "Mystery Model (Non-reasoning)",
            "Mystery Model (Reasoning)",
        ]
        assert offerings[0]["openness"] is None

    def test_agreeing_candidates_collapse_to_a_match(self) -> None:
        offerings = [offering("Agreeable Model")]
        rows = [
            openness_row("Agreeable Model (Reasoning)", openness_index=44.44),
            openness_row("Agreeable Model (Non-reasoning)", openness_index=44.44),
        ]

        result = join_openness(offerings, rows)

        assert result.matched == 1
        assert offerings[0]["openness"]["openness_index"] == 44.44

    def test_absent_openness_is_recorded_not_zeroed(self) -> None:
        """Coverage genuinely differs between the two datasets."""
        offerings = [offering("Claude Opus 5 (max)", creator="Anthropic")]
        rows = [openness_row("Claude Opus 4.5", creator="Anthropic")]

        result = join_openness(offerings, rows)

        assert result.matched == 0
        assert offerings[0]["openness"] is None
        entry = result.unmatched[0]
        assert entry["display_name"] == "Claude Opus 5 (max)"
        assert entry["normalized_base"] == "claude opus 5"
        assert entry["reason"] == "no openness row for this model"

    def test_unmatched_rows_are_never_dropped_from_the_dataset(self) -> None:
        offerings = [
            offering("Known Model", creator="Alibaba"),
            offering("Unknown Model", creator="Alibaba"),
        ]
        rows = [openness_row("Known Model", creator="Alibaba")]

        result = join_openness(offerings, rows)

        assert result.matched == 1
        assert len(result.unmatched) == 1
        assert len(offerings) == 2
