"""Tests for data models."""

from datetime import datetime

import pytest

from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
    SourceInfo,
)


class TestPricingInfo:
    """Test PricingInfo model."""

    def test_pricing_info_creation(self):
        pricing = PricingInfo(
            input_per_million=2.5, output_per_million=10.0, currency="USD"
        )
        assert pricing.input_per_million == 2.5
        assert pricing.output_per_million == 10.0
        assert pricing.currency == "USD"

    def test_pricing_info_default_currency(self):
        pricing = PricingInfo(input_per_million=2.5, output_per_million=10.0)
        assert pricing.currency == "USD"


class TestSourceInfo:
    """Test SourceInfo model."""

    def test_source_info_creation(self):
        now = datetime.now()
        source = SourceInfo(price_input=2.5, price_output=10.0, last_updated=now)
        assert source.price_input == 2.5
        assert source.price_output == 10.0
        assert source.last_updated == now


class TestModelInfo:
    """Test ModelInfo model."""

    def test_model_info_creation(self):
        pricing = PricingInfo(
            input_per_million=2.5, output_per_million=10.0, currency="USD"
        )
        model = ModelInfo(
            provider="openai",
            model_id="openai/gpt-4",
            display_name="OpenAI: GPT-4",
            pricing=pricing,
            context_window=128000,
            max_output_tokens=4096,
            model_type="chat",
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            category="flagship",
        )
        assert model.provider == "openai"
        assert model.model_id == "openai/gpt-4"
        assert model.display_name == "OpenAI: GPT-4"
        assert model.context_window == 128000
        assert model.supports_vision is True

    def test_model_info_defaults(self):
        pricing = PricingInfo(
            input_per_million=2.5, output_per_million=10.0, currency="USD"
        )
        model = ModelInfo(
            provider="openai",
            model_id="openai/gpt-4",
            display_name="OpenAI: GPT-4",
            pricing=pricing,
            context_window=128000,
            max_output_tokens=4096,
            model_type="chat",
            category="flagship",
        )
        assert model.supports_vision is False
        assert model.supports_function_calling is False
        assert model.supports_streaming is False
        assert model.sources == {}
        assert model.affiliate_links == {}


class TestProviderInfo:
    """Test ProviderInfo model."""

    def test_provider_info_creation(self):
        provider = ProviderInfo(
            name="OpenAI",
            website="https://openai.com",
            pricing_page="https://openai.com/pricing",
            affiliate_link="https://platform.openai.com/signup",
        )
        assert provider.name == "OpenAI"
        assert provider.website == "https://openai.com"


class TestMetadataInfo:
    """Test MetadataInfo model."""

    def test_metadata_info_creation(self):
        now = datetime.now()
        metadata = MetadataInfo(
            total_models=2230,
            sources=["openrouter", "litellm"],
            last_scrape=now,
            categories={"standard": 751, "budget": 1017, "flagship": 268},
        )
        assert metadata.total_models == 2230
        assert "openrouter" in metadata.sources
        assert metadata.categories["flagship"] == 268


class TestPricingData:
    """Test PricingData model with search functionality."""

    @pytest.fixture
    def sample_pricing_data(self) -> PricingData:
        """Create sample pricing data for testing."""
        now = datetime.now()

        gpt4_pricing = PricingInfo(
            input_per_million=30.0, output_per_million=60.0, currency="USD"
        )
        gpt4_model = ModelInfo(
            provider="openai",
            model_id="openai/gpt-4",
            display_name="OpenAI: GPT-4",
            pricing=gpt4_pricing,
            context_window=8192,
            max_output_tokens=4096,
            model_type="chat",
            supports_vision=False,
            supports_function_calling=True,
            supports_streaming=True,
            category="flagship",
        )

        gpt4v_pricing = PricingInfo(
            input_per_million=30.0, output_per_million=60.0, currency="USD"
        )
        gpt4v_model = ModelInfo(
            provider="openai",
            model_id="openai/gpt-4-vision",
            display_name="OpenAI: GPT-4 Vision",
            pricing=gpt4v_pricing,
            context_window=128000,
            max_output_tokens=4096,
            model_type="chat",
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            category="flagship",
        )

        claude_pricing = PricingInfo(
            input_per_million=15.0, output_per_million=75.0, currency="USD"
        )
        claude_model = ModelInfo(
            provider="anthropic",
            model_id="anthropic/claude-3-opus",
            display_name="Anthropic: Claude 3 Opus",
            pricing=claude_pricing,
            context_window=200000,
            max_output_tokens=4096,
            model_type="chat",
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            category="flagship",
        )

        openai_provider = ProviderInfo(
            name="OpenAI",
            website="https://openai.com",
            pricing_page="https://openai.com/pricing",
            affiliate_link="https://platform.openai.com/signup",
        )

        anthropic_provider = ProviderInfo(
            name="Anthropic",
            website="https://anthropic.com",
            pricing_page="https://anthropic.com/pricing",
            affiliate_link="https://console.anthropic.com/",
        )

        metadata = MetadataInfo(
            total_models=3,
            sources=["openrouter"],
            last_scrape=now,
            categories={"flagship": 3},
        )

        return PricingData(
            generated_at=now,
            models={
                "openai/gpt-4": gpt4_model,
                "openai/gpt-4-vision": gpt4v_model,
                "anthropic/claude-3-opus": claude_model,
            },
            providers={
                "openai": openai_provider,
                "anthropic": anthropic_provider,
            },
            metadata=metadata,
        )

    def test_get_model(self, sample_pricing_data: PricingData):
        """Test getting a model by ID."""
        model = sample_pricing_data.get_model("openai/gpt-4")
        assert model is not None
        assert model.model_id == "openai/gpt-4"
        assert model.provider == "openai"

    def test_get_model_not_found(self, sample_pricing_data: PricingData):
        """Test getting a non-existent model."""
        model = sample_pricing_data.get_model("nonexistent/model")
        assert model is None

    def test_get_provider(self, sample_pricing_data: PricingData):
        """Test getting a provider by ID."""
        provider = sample_pricing_data.get_provider("openai")
        assert provider is not None
        assert provider.name == "OpenAI"

    def test_get_provider_not_found(self, sample_pricing_data: PricingData):
        """Test getting a non-existent provider."""
        provider = sample_pricing_data.get_provider("nonexistent")
        assert provider is None

    def test_search_models_all(self, sample_pricing_data: PricingData):
        """Test searching for all models."""
        models = sample_pricing_data.search_models()
        assert len(models) == 3

    def test_search_models_by_provider(self, sample_pricing_data: PricingData):
        """Test searching models by provider."""
        models = sample_pricing_data.search_models(provider="openai")
        assert len(models) == 2
        assert all(m.provider == "openai" for m in models)

    def test_search_models_by_category(self, sample_pricing_data: PricingData):
        """Test searching models by category."""
        models = sample_pricing_data.search_models(category="flagship")
        assert len(models) == 3

    def test_search_models_by_vision_support(self, sample_pricing_data: PricingData):
        """Test searching models by vision support."""
        models = sample_pricing_data.search_models(supports_vision=True)
        assert len(models) == 2
        assert all(m.supports_vision for m in models)

    def test_search_models_by_function_calling(self, sample_pricing_data: PricingData):
        """Test searching models by function calling support."""
        models = sample_pricing_data.search_models(supports_function_calling=True)
        assert len(models) == 3

    def test_search_models_combined_filters(self, sample_pricing_data: PricingData):
        """Test searching with multiple filters."""
        models = sample_pricing_data.search_models(
            provider="openai", supports_vision=True
        )
        assert len(models) == 1
        assert models[0].model_id == "openai/gpt-4-vision"
