"""Tests for public API: get_pricing and compute_cost, with caching behavior."""

from unittest.mock import Mock, patch

import pytest

from tokenpricing import compute_cost, get_pricing


@pytest.fixture
def sample_llmtracker_response() -> dict:
    """Sample response from LLMTracker API."""
    return {
        "generated_at": "2026-01-20T06:05:10.791612+00:00",
        "models": {
            "openai/gpt-4": {
                "provider": "openai",
                "model_id": "openai/gpt-4",
                "display_name": "OpenAI: GPT-4",
                "pricing": {
                    "input_per_million": 30.0,
                    "output_per_million": 60.0,
                    "currency": "USD",
                },
                "context_window": 8192,
                "max_output_tokens": 4096,
                "model_type": "chat",
                "supports_vision": False,
                "supports_function_calling": True,
                "supports_streaming": True,
                "category": "flagship",
                "sources": {
                    "openrouter": {
                        "price_input": 30.0,
                        "price_output": 60.0,
                        "last_updated": "2026-01-20T06:05:10.392249+00:00",
                    }
                },
                "affiliate_links": {
                    "openai": "https://platform.openai.com/signup",
                    "openrouter": "https://openrouter.ai/",
                },
            }
        },
        "providers": {
            "openai": {
                "name": "OpenAI",
                "website": "https://openai.com",
                "pricing_page": "https://openai.com/pricing",
                "affiliate_link": "https://platform.openai.com/signup",
            }
        },
        "metadata": {
            "total_models": 1,
            "sources": ["openrouter"],
            "last_scrape": "2026-01-20T06:05:10.791612+00:00",
            "categories": {"flagship": 1},
        },
    }


class TestPublicAPI:
    @pytest.mark.asyncio
    async def test_get_pricing_success(self, sample_llmtracker_response: dict):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_llmtracker_response

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            pricing = await get_pricing("openai/gpt-4")
            assert pricing.input_per_million == 30.0
            assert pricing.output_per_million == 60.0
            assert pricing.currency == "USD"

    @pytest.mark.asyncio
    async def test_get_pricing_not_found(self, sample_llmtracker_response: dict):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_llmtracker_response

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with pytest.raises(ValueError):
                await get_pricing("unknown/model")

    @pytest.mark.asyncio
    async def test_compute_cost(self, sample_llmtracker_response: dict):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_llmtracker_response

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            # 1000 input @ $30/M + 500 output @ $60/M = 0.03 + 0.03
            total = await compute_cost("openai/gpt-4", 1000, 500)
            assert pytest.approx(total, rel=1e-6) == 0.06

    @pytest.mark.asyncio
    async def test_compute_cost_negative_tokens(self, sample_llmtracker_response: dict):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_llmtracker_response

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with pytest.raises(ValueError):
                await compute_cost("openai/gpt-4", -1, 100)

    @pytest.mark.asyncio
    async def test_caching_under_the_hood(self, sample_llmtracker_response: dict):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_llmtracker_response

        with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
            # First call should fetch
            pricing1 = await get_pricing("openai/gpt-4")
            assert pricing1.input_per_million == 30.0

            # Second call should be served from cache
            pricing2 = await get_pricing("openai/gpt-4")
            assert pricing2.output_per_million == 60.0

            # Depending on prior cache state, this may be 0 (already cached) or 1 (first fetch in this run).
            assert mock_get.call_count <= 1
