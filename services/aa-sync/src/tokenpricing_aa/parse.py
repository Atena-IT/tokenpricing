"""HTML parsing for Artificial Analysis pages.

Every value parser here exists because of a rendering quirk observed in the
captured pages; see ``tests/test_parse.py`` for the fixtures behind each one.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Tag

# The per-provider offering table, after the two-deep header is flattened.
PROVIDER_COLUMNS = (
    "Model",
    "Context Window",
    "Function Calling",
    "JSON Mode",
    "License",
    "Artificial Analysis Intelligence Index",
    "Cost per Task USD",
    "Median Tokens/s",
    "Median First Chunk (s)",
    "Total Response (s)",
    "Reasoning Time (s)",
    "Further Analysis",
)

OPENNESS_COLUMNS = (
    "Creator",
    "Model",
    "Openness Index",
    "Intelligence Index",
    "Model Availability",
    "Model Transparency",
    "Pre-training Data Access",
    "Pre-training Data License",
    "Post-training Data Access",
    "Post-training Data License",
)

# AA renders "no data" as an em dash or a double hyphen. It is not zero.
_NO_DATA = {"", "--", "—", "–", "N/A", "n/a"}

# U+2212 MINUS SIGN, not ASCII hyphen. ``float("−31")`` raises ValueError.
_MINUS_SIGN = "−"


class ParseError(ValueError):
    """Raised when a page no longer matches the shape this module expects."""


def cell_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def is_estimated(value: str | None) -> bool:
    """A trailing asterisk marks an estimated / partial score."""
    return str(value or "").strip().endswith("*")


def parse_number(value: str | None) -> float | None:
    """Parse an AA-rendered numeric cell.

    Handles the U+2212 minus sign, currency and percent decoration, thousands
    separators, the estimated-score asterisk, and the several spellings of
    "no data". Returns ``None`` for absent values so that absent stays
    distinguishable from zero.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in _NO_DATA:
        return None
    text = (
        text.replace(_MINUS_SIGN, "-")
        .replace("$", "")
        .replace("%", "")
        .replace(",", "")
        .rstrip("*")
        .strip()
    )
    if text in _NO_DATA:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_context_window(value: str | None) -> int | None:
    """Context windows are rendered human-readable: ``1M``, ``1.05M``, ``262k``."""
    text = str(value or "").strip()
    if text in _NO_DATA:
        return None
    multiplier = 1
    if text[-1:] in {"M", "m"}:
        multiplier, text = 1_000_000, text[:-1]
    elif text[-1:] in {"k", "K"}:
        multiplier, text = 1_000, text[:-1]
    try:
        return round(float(text.replace(",", "")) * multiplier)
    except ValueError:
        return None


def parse_flag(cell: Tag | None) -> bool:
    """Feature columns render a check icon only when the feature is supported.

    AA emits ``<svg aria-label="Yes">`` for supported features and renders
    nothing at all otherwise — there is no "No" icon anywhere in the captured
    pages, so absence is the negative signal.
    """
    if cell is None:
        return False
    return any(
        svg.get("aria-label") == "Yes" for svg in cell.select("svg[aria-label]")
    )


def _creator_from_cell(cell: Tag | None) -> str | None:
    """The model cell carries the creator's logo; its alt text names the creator."""
    if cell is None:
        return None
    for img in cell.select("img[alt]"):
        alt = str(img.get("alt") or "").strip()
        if alt.lower().endswith(" logo"):
            return alt[: -len(" logo")].strip() or None
    return None


def _first_table(html: str) -> Tag:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ParseError("no <table> found in document")
    return table


def _columns_from(headers: list[str], expected: tuple[str, ...], what: str) -> None:
    if tuple(headers) != expected:
        raise ParseError(
            f"{what} columns changed: expected {list(expected)}, got {headers}"
        )


def parse_provider_page(html: str, provider_slug: str) -> list[dict[str, Any]]:
    """Parse one ``/providers/<slug>`` page into offering rows.

    The header is two-deep (a column-group row then the real column row); the
    real columns are located by finding the ``Model`` header rather than by
    assuming a fixed offset.
    """
    table = _first_table(html)
    headers = [cell_text(th) for th in table.select("thead th")]
    try:
        start = headers.index("Model")
    except ValueError as exc:  # pragma: no cover - guarded by shape test
        raise ParseError(
            f"{provider_slug}: no 'Model' column in header {headers}"
        ) from exc
    _columns_from(headers[start:], PROVIDER_COLUMNS, f"provider page {provider_slug}")

    rows: list[dict[str, Any]] = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False) or tr.select("td")
        if len(cells) < len(PROVIDER_COLUMNS):
            continue
        name_cell = cells[0]
        anchor = name_cell.select_one('a[href^="/models/"]') or tr.select_one(
            'a[href^="/models/"]'
        )
        model_slug = (
            str(anchor.get("href", "")).removeprefix("/models/") if anchor else ""
        )
        display_name = cell_text(name_cell)
        if not display_name:
            continue
        cost = cell_text(cells[6])
        intelligence = cell_text(cells[5])
        rows.append(
            {
                "provider_slug": provider_slug,
                "model_slug": model_slug,
                "display_name": display_name,
                "creator": _creator_from_cell(name_cell),
                "context_window": parse_context_window(cell_text(cells[1])),
                "supports_function_calling": parse_flag(cells[2]),
                "supports_json_mode": parse_flag(cells[3]),
                "license": cell_text(cells[4]) or None,
                "intelligence_index": parse_number(intelligence),
                "intelligence_index_estimated": is_estimated(intelligence),
                "cost_per_task_usd": parse_number(cost),
                "cost_per_task_estimated": is_estimated(cost),
                "median_output_tokens_per_second": parse_number(cell_text(cells[7])),
                "median_first_chunk_seconds": parse_number(cell_text(cells[8])),
                "total_response_seconds": parse_number(cell_text(cells[9])),
                "reasoning_time_seconds": parse_number(cell_text(cells[10])),
            }
        )
    return rows


def parse_openness_page(html: str) -> list[dict[str, Any]]:
    """Parse the Openness Index leaderboard.

    The table body carries no anchors at all — there are no model slugs on this
    page, which is why the join runs on normalised display names plus creator.
    """
    table = _first_table(html)
    headers = [cell_text(th) for th in table.select("thead th")]
    try:
        start = headers.index("Creator")
    except ValueError as exc:  # pragma: no cover - guarded by shape test
        raise ParseError(f"no 'Creator' column in openness header {headers}") from exc
    _columns_from(headers[start:], OPENNESS_COLUMNS, "openness index")

    rows: list[dict[str, Any]] = []
    for tr in table.select("tbody tr"):
        cells = [cell_text(td) for td in tr.select("td")]
        if len(cells) < len(OPENNESS_COLUMNS) + 1:
            continue
        rank, creator, name = cells[0], cells[1], cells[2]
        if not name:
            continue
        rows.append(
            {
                "rank": int(parse_number(rank) or 0) or None,
                "creator": creator or None,
                "display_name": name,
                "openness_index": parse_number(cells[3]),
                "intelligence_index": parse_number(cells[4]),
                "model_availability": parse_number(cells[5]),
                "model_transparency": parse_number(cells[6]),
                "pre_training_data_access": parse_number(cells[7]),
                "pre_training_data_license": parse_number(cells[8]),
                "post_training_data_access": parse_number(cells[9]),
                "post_training_data_license": parse_number(cells[10]),
            }
        )
    return rows
