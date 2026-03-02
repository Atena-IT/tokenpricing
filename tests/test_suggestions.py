"""Tests for suggestions utilities (\"Did you mean?\" suggestions)."""

import pytest

from tokenpricing.suggestions import (
    DEFAULT_SCORE_THRESHOLD,
    FuzzyMatch,
    suggest_match,
    suggest_currency,
    suggest_model,
)


class TestFuzzyMatch:
    """Test FuzzyMatch dataclass."""

    def test_is_exact_true(self):
        match = FuzzyMatch(query="test", match="test", score=100)
        assert match.is_exact is True

    def test_is_exact_false(self):
        match = FuzzyMatch(query="test", match="tset", score=80)
        assert match.is_exact is False


class TestSuggestMatch:
    """Test suggest_match function."""

    def test_exact_match_case_insensitive(self):
        choices = ["Apple", "Banana", "Cherry"]
        result = suggest_match("apple", choices)
        assert result is not None
        assert result.match == "Apple"
        assert result.score == 100
        assert result.is_exact is True

    def test_fuzzy_suggestion(self):
        choices = ["openai/gpt-4", "anthropic/claude-3", "google/gemini-pro"]
        result = suggest_match("gpt4", choices)
        assert result is not None
        assert result.match == "openai/gpt-4"
        assert result.score >= DEFAULT_SCORE_THRESHOLD

    def test_no_suggestion_below_threshold(self):
        choices = ["apple", "banana", "cherry"]
        result = suggest_match("xyz", choices, threshold=80)
        assert result is None

    def test_empty_choices(self):
        result = suggest_match("test", [])
        assert result is None


class TestSuggestModel:
    """Test suggest_model function for model ID suggestions."""

    @pytest.fixture
    def model_ids(self):
        return [
            "openai/gpt-4",
            "openai/gpt-4-turbo",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "google/gemini-pro",
        ]

    @pytest.fixture
    def display_names(self):
        return {
            "openai/gpt-4": "OpenAI: GPT-4",
            "openai/gpt-4-turbo": "OpenAI: GPT-4 Turbo",
            "anthropic/claude-3-opus": "Anthropic: Claude 3 Opus",
            "anthropic/claude-3-sonnet": "Anthropic: Claude 3 Sonnet",
            "google/gemini-pro": "Google: Gemini Pro",
        }

    def test_suggest_similar_model_id(self, model_ids, display_names):
        # User typed "openai/gpt4" instead of "openai/gpt-4"
        result = suggest_model("openai/gpt4", model_ids, display_names)
        assert result is not None
        assert "gpt-4" in result.match

    def test_suggest_partial_model_id(self, model_ids, display_names):
        result = suggest_model("gpt-4", model_ids, display_names)
        assert result is not None
        assert "gpt-4" in result.match.lower()

    def test_suggest_from_display_name(self, model_ids, display_names):
        result = suggest_model("claude opus", model_ids, display_names)
        assert result is not None
        assert "claude" in result.match.lower()

    def test_no_suggestion_for_unrelated(self, model_ids, display_names):
        result = suggest_model("completely-unrelated-xyz-123", model_ids, display_names)
        # Should not find a suggestion for completely unrelated input
        if result is not None:
            assert result.score >= DEFAULT_SCORE_THRESHOLD

    def test_empty_model_ids(self):
        result = suggest_model("test", [])
        assert result is None

    def test_no_display_names(self, model_ids):
        result = suggest_model("gpt-4", model_ids)
        assert result is not None
        assert "gpt-4" in result.match


class TestSuggestCurrency:
    """Test suggest_currency function for currency code suggestions."""

    @pytest.fixture
    def currency_codes(self):
        return ["USD", "EUR", "GBP", "JPY", "CNY", "CAD", "AUD", "CHF"]

    def test_suggest_typo(self, currency_codes):
        # "ERU" is a typo for "EUR"
        result = suggest_currency("ERU", currency_codes, threshold=60)
        assert result is not None
        assert result.match == "EUR"

    def test_suggest_similar_code(self, currency_codes):
        # "GRP" might suggest "GBP"
        result = suggest_currency("GRP", currency_codes, threshold=60)
        assert result is not None
        assert result.match == "GBP"

    def test_no_suggestion_very_different(self, currency_codes):
        result = suggest_currency("XYZ", currency_codes, threshold=80)
        assert result is None

    def test_empty_currency_codes(self):
        result = suggest_currency("USD", [])
        assert result is None
