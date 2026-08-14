import pytest

from tokenpricing_aa.parse import (
    OPENNESS_COLUMNS,
    PROVIDER_COLUMNS,
    ParseError,
    is_estimated,
    parse_context_window,
    parse_number,
    parse_openness_page,
    parse_provider_page,
)

GROUP_HEADER = [
    "",
    "Features",
    "Model Intelligence",
    "Price",
    "Speed",
    "Latency",
    "End-to-End Response Time",
    "",
]

CHECK_ICON = '<svg aria-label="Yes" class="lucide lucide-check-line"></svg>'


def provider_html(rows: list[list[str]], columns: tuple[str, ...] = PROVIDER_COLUMNS) -> str:
    group = "".join(f"<th>{cell}</th>" for cell in GROUP_HEADER)
    header = "".join(f"<th>{cell}</th>" for cell in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        f"<table><thead><tr>{group}</tr><tr>{header}</tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def offering_row(
    name: str = "Kimi K3 (max)",
    slug: str = "kimi-k3",
    creator: str = "Kimi",
    context: str = "1.05M",
    function_calling: str = CHECK_ICON,
    json_mode: str = CHECK_ICON,
    license_: str = "Open",
    intelligence: str = "60",
    cost: str = "$0.89",
    tokens_per_second: str = "48",
    first_chunk: str = "1.26",
    total: str = "53.76",
    reasoning: str = "42.00",
) -> list[str]:
    model_cell = (
        f'<div><img alt="{creator} logo" src="/img.jpg"/>{name}'
        f'<a href="/models/{slug}"></a></div>'
    )
    return [
        model_cell,
        context,
        function_calling,
        json_mode,
        license_,
        intelligence,
        cost,
        tokens_per_second,
        first_chunk,
        total,
        reasoning,
        '<a href="/models/x">Model Provider</a>',
    ]


class TestParseNumber:
    def test_unicode_minus_sign_parses_as_negative(self) -> None:
        """AA renders negatives with U+2212, which float() rejects outright."""
        with pytest.raises(ValueError):
            float("−31")
        assert parse_number("−31") == -31.0
        assert parse_number("−38.5") == -38.5

    def test_ascii_hyphen_still_parses(self) -> None:
        assert parse_number("-31") == -31.0

    def test_no_data_is_none_not_zero(self) -> None:
        for value in ("--", "—", "–", "", "N/A", None):
            assert parse_number(value) is None

    def test_zero_is_preserved_as_zero(self) -> None:
        assert parse_number("0") == 0.0

    def test_strips_currency_percent_and_thousands_separators(self) -> None:
        assert parse_number("$0.89") == 0.89
        assert parse_number("67%") == 67.0
        assert parse_number("1,715") == 1715.0

    def test_estimated_asterisk_is_stripped_but_flagged(self) -> None:
        assert parse_number("33*") == 33.0
        assert is_estimated("33*") is True
        assert is_estimated("33") is False

    def test_unparseable_text_is_none(self) -> None:
        assert parse_number("coming soon") is None


class TestParseContextWindow:
    @pytest.mark.parametrize(
        ("rendered", "expected"),
        [
            ("1M", 1_000_000),
            ("1.05M", 1_050_000),
            ("262k", 262_000),
            ("205k", 205_000),
            ("128K", 128_000),
        ],
    )
    def test_human_readable_suffixes(self, rendered: str, expected: int) -> None:
        assert parse_context_window(rendered) == expected

    def test_missing_is_none(self) -> None:
        assert parse_context_window("--") is None
        assert parse_context_window(None) is None


class TestParseProviderPage:
    def test_extracts_offering_fields(self) -> None:
        (row,) = parse_provider_page(provider_html([offering_row()]), "fireworks")

        assert row["provider_slug"] == "fireworks"
        assert row["model_slug"] == "kimi-k3"
        assert row["display_name"] == "Kimi K3 (max)"
        assert row["creator"] == "Kimi"
        assert row["context_window"] == 1_050_000
        assert row["license"] == "Open"
        assert row["intelligence_index"] == 60.0
        assert row["cost_per_task_usd"] == 0.89
        assert row["median_output_tokens_per_second"] == 48.0
        assert row["reasoning_time_seconds"] == 42.0

    def test_check_icon_presence_drives_feature_flags(self) -> None:
        """AA emits a check icon for yes and renders nothing at all for no."""
        (yes,) = parse_provider_page(provider_html([offering_row()]), "p")
        assert yes["supports_function_calling"] is True
        assert yes["supports_json_mode"] is True

        (no,) = parse_provider_page(
            provider_html([offering_row(function_calling="", json_mode="")]), "p"
        )
        assert no["supports_function_calling"] is False
        assert no["supports_json_mode"] is False

    def test_missing_reasoning_time_is_none(self) -> None:
        (row,) = parse_provider_page(
            provider_html([offering_row(reasoning="--")]), "openai"
        )
        assert row["reasoning_time_seconds"] is None

    def test_same_slug_twice_is_kept_as_two_offerings(self) -> None:
        """A provider can serve one model under several serving tiers."""
        rows = parse_provider_page(
            provider_html(
                [
                    offering_row(name="Kimi K3 (max)"),
                    offering_row(name="Kimi K3 (max) (FAST)", cost="$1.34"),
                ]
            ),
            "fireworks",
        )
        assert len(rows) == 2
        assert {row["display_name"] for row in rows} == {
            "Kimi K3 (max)",
            "Kimi K3 (max) (FAST)",
        }

    def test_changed_columns_fail_loudly(self) -> None:
        mutated = ("Model", "Context Window", "Surprise") + PROVIDER_COLUMNS[3:]
        with pytest.raises(ParseError, match="columns changed"):
            parse_provider_page(provider_html([], columns=mutated), "p")

    def test_missing_table_fails_loudly(self) -> None:
        with pytest.raises(ParseError, match="no <table>"):
            parse_provider_page("<html><body>nope</body></html>", "p")


def openness_html(rows: list[list[str]]) -> str:
    header = "".join(f"<th>{cell}</th>" for cell in ("", *OPENNESS_COLUMNS))
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


class TestParseOpennessPage:
    def test_extracts_components(self) -> None:
        (row,) = parse_openness_page(
            openness_html(
                [
                    [
                        "1",
                        "Allen Institute for AI",
                        "Olmo 3.1 32B Think",
                        "88.89",
                        "7.90",
                        "6.00",
                        "10.00",
                        "3.00",
                        "1.00",
                        "3.00",
                        "1.00",
                    ]
                ]
            )
        )

        assert row["rank"] == 1
        assert row["creator"] == "Allen Institute for AI"
        assert row["display_name"] == "Olmo 3.1 32B Think"
        assert row["openness_index"] == 88.89
        assert row["pre_training_data_access"] == 3.0
        assert row["post_training_data_license"] == 1.0

    def test_changed_columns_fail_loudly(self) -> None:
        header = "".join(
            f"<th>{cell}</th>" for cell in ("", "Creator", "Model", "Something Else")
        )
        with pytest.raises(ParseError, match="columns changed"):
            parse_openness_page(f"<table><thead><tr>{header}</tr></thead></table>")
