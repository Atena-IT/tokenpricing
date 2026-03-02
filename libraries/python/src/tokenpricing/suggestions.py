"""Suggestions utilities for helpful "Did you mean?" error messages.

Provides fuzzy string matching using thefuzz library with high thresholds
to suggest likely intended values when exact lookups fail. This is NOT for
automatic approximate matching—lookups remain exact, but errors become
more informative.
"""

from __future__ import annotations

from dataclasses import dataclass

from thefuzz import fuzz, process


# Default minimum score threshold for fuzzy matches (0-100)
DEFAULT_SCORE_THRESHOLD = 60


@dataclass
class FuzzyMatch:
    """Result of a fuzzy match operation."""

    query: str
    match: str
    score: int

    @property
    def is_exact(self) -> bool:
        """Return True if this is an exact match (score 100)."""
        return self.score == 100


def suggest_match(
    query: str,
    choices: list[str],
    threshold: int = DEFAULT_SCORE_THRESHOLD,
    scorer=fuzz.WRatio,
) -> FuzzyMatch | None:
    """Suggest the best match for query among choices (for error messages).

    Uses weighted ratio scoring by default which handles partial matches,
    token reordering, and partial token matches well.

    Args:
        query: The string the user provided.
        choices: List of valid candidate strings.
        threshold: Minimum score (0-100) for a suggestion to be offered.
        scorer: The scoring function to use (default: fuzz.WRatio).

    Returns:
        FuzzyMatch with the best suggestion if score >= threshold, else None.
    """
    if not choices:
        return None

    # Check for exact match first (case-insensitive)
    query_lower = query.lower()
    for choice in choices:
        if choice.lower() == query_lower:
            return FuzzyMatch(query=query, match=choice, score=100)

    # Use thefuzz's extractOne for best match
    result = process.extractOne(query, choices, scorer=scorer, score_cutoff=threshold)
    if result is None:
        return None

    match_str, score = result[0], result[1]
    return FuzzyMatch(query=query, match=match_str, score=score)


def suggest_model(
    query: str,
    model_ids: list[str],
    display_names: dict[str, str] | None = None,
    threshold: int = DEFAULT_SCORE_THRESHOLD,
) -> FuzzyMatch | None:
    """Suggest a model for "Did you mean?" error messages.

    Searches both model IDs and display names (if provided) for suggestions.
    Used when an exact model lookup fails to provide helpful error context.

    Args:
        query: The model identifier the user provided.
        model_ids: List of valid model IDs (e.g., 'openai/gpt-4').
        display_names: Optional dict mapping model_id -> display_name.
        threshold: Minimum score (0-100) for a suggestion to be offered.

    Returns:
        FuzzyMatch where 'match' is the suggested model_id, else None.
    """
    if not model_ids:
        return None

    # Fuzzy match on model IDs
    model_result = process.extractOne(
        query, model_ids, scorer=fuzz.WRatio, score_cutoff=threshold
    )

    # Also try fuzzy match on display names
    display_result = None
    if display_names:
        name_to_id = {v: k for k, v in display_names.items()}
        names = list(name_to_id.keys())
        name_match = process.extractOne(
            query, names, scorer=fuzz.WRatio, score_cutoff=threshold
        )
        if name_match:
            matched_name, score = name_match[0], name_match[1]
            display_result = (name_to_id[matched_name], score)

    # Return best suggestion between model_id and display_name matches
    if model_result and display_result:
        if model_result[1] >= display_result[1]:
            return FuzzyMatch(query=query, match=model_result[0], score=model_result[1])
        else:
            return FuzzyMatch(
                query=query, match=display_result[0], score=display_result[1]
            )
    elif model_result:
        return FuzzyMatch(query=query, match=model_result[0], score=model_result[1])
    elif display_result:
        return FuzzyMatch(query=query, match=display_result[0], score=display_result[1])

    return None


def suggest_currency(
    query: str,
    currency_codes: list[str],
    threshold: int = 60,
) -> FuzzyMatch | None:
    """Suggest a currency code for "Did you mean?" error messages.

    Currency codes are typically 3-letter uppercase strings (ISO 4217).
    Uses a moderate threshold to catch common typos in short codes.

    Args:
        query: The currency code the user provided.
        currency_codes: List of valid currency codes.
        threshold: Minimum score for a suggestion (default: 60).

    Returns:
        FuzzyMatch where 'match' is the suggested currency code, else None.
    """
    if not currency_codes:
        return None

    # Normalize query
    query_upper = query.upper().strip()

    # For short queries (like currency codes), use simple ratio
    # Get all matches above threshold to consider all options
    matches = process.extract(
        query_upper,
        [c.upper() for c in currency_codes],
        scorer=fuzz.ratio,
        limit=None,  # No limit - check all currencies
    )

    # Filter by threshold
    matches = [(m, s) for m, s, *_ in matches if s >= threshold]

    if not matches:
        return None

    # Among equal scores, prefer common currencies
    common_currencies = {"USD", "EUR", "GBP", "JPY", "CNY", "CAD", "AUD", "CHF", "INR"}
    best_match = None
    best_score = 0

    for matched_upper, score in matches:
        # Prefer higher score
        if score > best_score:
            best_score = score
            best_match = matched_upper
        # Among equal scores, prefer common currencies
        elif score == best_score and matched_upper in common_currencies:
            if best_match not in common_currencies:
                best_match = matched_upper

    if best_match is None:
        return None

    # Find original case version
    for code in currency_codes:
        if code.upper() == best_match:
            return FuzzyMatch(query=query, match=code, score=best_score)

    return None
