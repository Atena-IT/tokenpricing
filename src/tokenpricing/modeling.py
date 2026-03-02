"""Data models for LLM pricing information from LLMTracker."""

from datetime import datetime

from pydantic import BaseModel, Field


class PricingInfo(BaseModel):
    """Pricing information for a model."""

    input_per_million: float = Field(
        description="Price per million input tokens in the specified currency"
    )
    output_per_million: float = Field(
        description="Price per million output tokens in the specified currency"
    )
    currency: str = Field(default="USD", description="Currency code (e.g., USD, EUR)")


class SourceInfo(BaseModel):
    """Information about a pricing source."""

    price_input: float
    price_output: float
    last_updated: datetime


class ModelInfo(BaseModel):
    """Complete information about an LLM model."""

    provider: str = Field(description="Provider identifier (e.g., openai, anthropic)")
    model_id: str = Field(description="Unique model identifier")
    display_name: str = Field(description="Human-readable model name")
    pricing: PricingInfo
    context_window: int = Field(description="Maximum context window size in tokens")
    max_output_tokens: int = Field(description="Maximum output tokens")
    model_type: str = Field(description="Type of model (e.g., chat, embedding)")
    supports_vision: bool = Field(default=False)
    supports_function_calling: bool = Field(default=False)
    supports_streaming: bool = Field(default=False)
    category: str = Field(
        description="Model category (e.g., standard, flagship, budget)"
    )
    sources: dict[str, SourceInfo] = Field(default_factory=dict)
    affiliate_links: dict[str, str] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    """Information about an LLM provider."""

    name: str = Field(description="Provider display name")
    website: str = Field(description="Provider website URL")
    pricing_page: str = Field(description="URL to provider's pricing page")
    affiliate_link: str = Field(description="Affiliate or signup link")


class MetadataInfo(BaseModel):
    """Metadata about the pricing dataset."""

    total_models: int = Field(description="Total number of models in dataset")
    sources: list[str] = Field(description="List of data sources")
    last_scrape: datetime = Field(description="Timestamp of last data scrape")
    categories: dict[str, int] = Field(
        default_factory=dict, description="Model count per category"
    )


class PricingData(BaseModel):
    """Complete pricing dataset from LLMTracker."""

    generated_at: datetime = Field(description="Timestamp when data was generated")
    models: dict[str, ModelInfo] = Field(
        description="Dictionary of model_id to ModelInfo"
    )
    providers: dict[str, ProviderInfo] = Field(
        description="Dictionary of provider_id to ProviderInfo"
    )
    metadata: MetadataInfo = Field(description="Dataset metadata")

    def get_model(self, model_id: str) -> ModelInfo | None:
        """Get model information by model ID.

        Args:
            model_id: The model identifier (e.g., 'openai/gpt-4')

        Returns:
            ModelInfo if found, None otherwise
        """
        return self.models.get(model_id)

    def suggest_model(self, query: str) -> str | None:
        """Suggest a model ID for a failed lookup (for error messages).

        Args:
            query: The model identifier the user provided.

        Returns:
            Suggested model_id string if a close match is found, else None.
        """
        from tokenpricing.suggestions import suggest_model

        display_names = {m.model_id: m.display_name for m in self.models.values()}
        match = suggest_model(
            query=query,
            model_ids=list(self.models.keys()),
            display_names=display_names,
        )
        if match is not None:
            return match.match
        return None

    def get_provider(self, provider_id: str) -> ProviderInfo | None:
        """Get provider information by provider ID.

        Args:
            provider_id: The provider identifier (e.g., 'openai')

        Returns:
            ProviderInfo if found, None otherwise
        """
        return self.providers.get(provider_id)

    def search_models(
        self,
        provider: str | None = None,
        category: str | None = None,
        supports_vision: bool | None = None,
        supports_function_calling: bool | None = None,
    ) -> list[ModelInfo]:
        """Search for models matching specified criteria.

        Args:
            provider: Filter by provider (e.g., 'openai')
            category: Filter by category (e.g., 'flagship', 'budget')
            supports_vision: Filter by vision support
            supports_function_calling: Filter by function calling support

        Returns:
            List of matching ModelInfo objects
        """
        results = list(self.models.values())

        if provider is not None:
            results = [m for m in results if m.provider == provider]

        if category is not None:
            results = [m for m in results if m.category == category]

        if supports_vision is not None:
            results = [m for m in results if m.supports_vision == supports_vision]

        if supports_function_calling is not None:
            results = [
                m
                for m in results
                if m.supports_function_calling == supports_function_calling
            ]

        return results
