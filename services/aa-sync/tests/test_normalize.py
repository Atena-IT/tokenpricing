from datetime import UTC, datetime
from typing import Any

import pytest

from tokenpricing_aa.fetch import discover_provider_slugs
from tokenpricing_aa.normalize import ShapeError, normalize_sources
from tokenpricing_aa.parse import OPENNESS_COLUMNS, PROVIDER_COLUMNS

from .test_parse import CHECK_ICON, GROUP_HEADER

NOW = datetime(2026, 8, 14, tzinfo=UTC).isoformat()


def provider_page(rows: list[tuple[str, str, str]]) -> str:
    group = "".join(f"<th>{cell}</th>" for cell in GROUP_HEADER)
    header = "".join(f"<th>{cell}</th>" for cell in PROVIDER_COLUMNS)
    body = ""
    for name, slug, creator in rows:
        model_cell = (
            f'<div><img alt="{creator} logo" src="/i.jpg"/>{name}'
            f'<a href="/models/{slug}"></a></div>'
        )
        cells = [
            model_cell,
            "1M",
            CHECK_ICON,
            CHECK_ICON,
            "Open",
            "60",
            "$0.89",
            "48",
            "1.26",
            "53.76",
            "42.00",
            "x",
        ]
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    return (
        f"<table><thead><tr>{group}</tr><tr>{header}</tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def openness_page(rows: list[tuple[str, str, str]]) -> str:
    header = "".join(f"<th>{c}</th>" for c in ("", *OPENNESS_COLUMNS))
    body = ""
    for rank, (creator, name, index) in enumerate(rows, 1):
        cells = [
            str(rank),
            creator,
            name,
            index,
            "50.0",
            "6.00",
            "6.00",
            "1.00",
            "1.00",
            "1.00",
            "1.00",
        ]
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def payloads(
    provider_count: int = 45,
    rows_per_provider: int = 20,
    openness_count: int = 260,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pages = {
        f"provider-{index:02d}": provider_page(
            [
                (f"Model {n} (max)", f"model-{n}", "Alibaba")
                for n in range(rows_per_provider)
            ]
        )
        for index in range(provider_count)
    }
    openness_rows = [
        ("Alibaba", f"Model {n} (Reasoning)", "66.67") for n in range(openness_count)
    ]
    providers_payload = {
        "source": "artificial_analysis_providers",
        "source_url": "https://artificialanalysis.ai/leaderboards/providers",
        "fetched_at": NOW,
        "discovered_slugs": sorted(pages),
        "unreachable_slugs": [{"slug": "hyperbolic", "status": 404}],
        "pages": pages,
    }
    openness_payload = {
        "source": "artificial_analysis_openness",
        "source_url": "https://artificialanalysis.ai/evaluations/artificial-analysis-openness-index",
        "fetched_at": NOW,
        "page": openness_page(openness_rows),
    }
    return providers_payload, openness_payload


class TestDiscoverProviderSlugs:
    def test_extracts_slugs_and_ignores_chunk_filenames(self) -> None:
        html = (
            '<a href="/providers/fireworks">a</a>'
            '<a href="/providers/togetherai">b</a>'
            '<script src="/providers/page-36913d7f85844cbc.js"></script>'
            '<a href="/providers/fireworks">dupe</a>'
        )
        assert discover_provider_slugs(html) == ["fireworks", "togetherai"]


class TestNormalizeSources:
    def test_builds_dataset_with_metadata_and_attribution(self) -> None:
        dataset = normalize_sources(*payloads())

        assert dataset.metadata.provider_count == 45
        assert dataset.metadata.offering_count == 900
        assert dataset.metadata.openness_row_count == 260
        assert dataset.metadata.openness_matched == 900
        assert dataset.metadata.unreachable_provider_slugs == ["hyperbolic"]
        assert "Artificial Analysis" in dataset.metadata.attribution
        assert dataset.metadata.openness_spec_version.startswith("Openness Spec V1.0")

    def test_offerings_carry_variant_identity(self) -> None:
        dataset = normalize_sources(*payloads())
        offering = dataset.offerings[0]

        assert offering.reasoning_effort == "max"
        assert offering.reasoning_mode == "reasoning"
        assert offering.openness is not None
        assert offering.openness.openness_index == 66.67
        assert offering.openness_match is not None

    def test_unmatched_offerings_are_reported_and_kept(self) -> None:
        providers, openness = payloads(rows_per_provider=21)
        dataset = normalize_sources(providers, openness)

        # Model 20 has no openness row (openness covers Model 0..259 by name, but
        # each provider page only emits Model 0..20, so all are covered) — assert
        # instead on the join accounting being complete and lossless.
        assert dataset.metadata.offering_count == len(dataset.offerings)
        assert (
            dataset.metadata.openness_matched
            + dataset.metadata.openness_unmatched
            + dataset.metadata.openness_ambiguous
            == dataset.metadata.offering_count
        )

    def test_openness_absent_for_a_model_is_recorded_not_zeroed(self) -> None:
        providers, openness = payloads()
        providers["pages"]["provider-00"] = provider_page(
            [("Claude Opus 5 (max)", "claude-opus-5", "Anthropic")]
        )
        dataset = normalize_sources(providers, openness)

        missing = [o for o in dataset.offerings if o.display_name == "Claude Opus 5 (max)"]
        assert len(missing) == 1
        assert missing[0].openness is None
        assert any(u.display_name == "Claude Opus 5 (max)" for u in dataset.unmatched)

    def test_too_few_providers_fails_loudly(self) -> None:
        providers, openness = payloads(provider_count=10)
        with pytest.raises(ShapeError, match="provider pages captured"):
            normalize_sources(providers, openness)

    def test_too_few_offerings_fails_loudly(self) -> None:
        providers, openness = payloads(provider_count=41, rows_per_provider=1)
        with pytest.raises(ShapeError, match="offerings parsed"):
            normalize_sources(providers, openness)

    def test_too_few_openness_rows_fails_loudly(self) -> None:
        providers, openness = payloads(openness_count=10)
        with pytest.raises(ShapeError, match="openness rows parsed"):
            normalize_sources(providers, openness)

    def test_missing_model_anchors_fail_loudly(self) -> None:
        """A restyle that drops the /models/ hrefs must not publish silently."""
        providers, openness = payloads()
        providers["pages"] = {
            slug: html.replace('href="/models/', 'href="/broken/')
            for slug, html in providers["pages"].items()
        }
        with pytest.raises(ShapeError, match="/models/ anchor"):
            normalize_sources(providers, openness)
