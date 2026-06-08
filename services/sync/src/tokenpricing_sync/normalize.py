from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
    SourceInfo,
)


def parse_price_per_million(value: Any) -> float | None:
    if value in (None, "", 0, "0"):
        return None
    return round(float(value) * 1_000_000, 6)


def extract_provider(model_id: str, raw_provider: str | None = None) -> str:
    if raw_provider:
        return raw_provider.lower().replace(" ", "-")
    if "/" in model_id:
        return model_id.split("/", 1)[0].lower()
    model_lower = model_id.lower()
    if model_lower.startswith(("gpt-", "o1-", "o3-", "o4-", "ada", "babbage", "davinci", "curie")):
        return "openai"
    if "claude" in model_lower:
        return "anthropic"
    if "gemini" in model_lower:
        return "google"
    if "mistral" in model_lower or "mixtral" in model_lower:
        return "mistral"
    return "unknown"


def infer_model_type(raw_mode: str | None, model_id: str, display_name: str) -> str:
    mode = (raw_mode or "").lower().replace("_", "-")
    if mode in {"chat", "completion", "responses", "language"}:
        return "chat"
    if mode in {"embedding", "embeddings"}:
        return "embedding"
    if mode in {"image-generation", "image-edit", "image", "images"}:
        return "image-generation"
    if mode in {"audio", "audio-transcription", "audio-speech", "transcription"}:
        return "transcription"
    if mode in {"rerank", "reranking"}:
        return "reranking"
    if mode == "video":
        return "video"
    haystack = f"{model_id} {display_name}".lower()
    if any(token in haystack for token in ("embed", "embedding")):
        return "embedding"
    if any(token in haystack for token in ("image", "flux", "sdxl", "midjourney")):
        return "image-generation"
    if any(token in haystack for token in ("transcribe", "whisper", "speech", "tts", "stt")):
        return "transcription"
    if any(token in haystack for token in ("rerank", "reranker")):
        return "reranking"
    return "chat"


def infer_category(model_id: str, display_name: str) -> str:
    haystack = f"{model_id} {display_name}".lower()
    if any(token in haystack for token in ("mini", "nano", "small", "flash", "haiku", "lite")):
        return "budget"
    if any(token in haystack for token in ("opus", "sonnet", "pro", "ultra", "flagship", "o3", "o4", "gpt-5", "gemini-2.5-pro", "gemini-3")):
        return "flagship"
    return "standard"


def infer_supports_vision(raw: dict[str, Any], model_type: str, haystack: str) -> bool:
    if raw.get("supports_vision") is True:
        return True
    if model_type == "image-generation":
        return True
    modality = str(raw.get("modality") or raw.get("architecture", {}).get("modality") or "").lower()
    return "vision" in haystack or "image" in haystack or "image" in modality


def infer_supports_function_calling(raw: dict[str, Any]) -> bool:
    if isinstance(raw.get("supports_function_calling"), bool):
        return bool(raw.get("supports_function_calling"))
    supported_parameters = raw.get("supported_parameters")
    if isinstance(supported_parameters, list):
        lowered = {str(item).lower() for item in supported_parameters}
        return bool({"tools", "tool_choice", "function_calling", "functions"} & lowered)
    return False


def infer_supports_streaming(raw: dict[str, Any]) -> bool:
    if isinstance(raw.get("supports_streaming"), bool):
        return bool(raw.get("supports_streaming"))
    return True

def parse_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def build_provider_info(provider_id: str, raw: dict[str, Any] | None = None) -> ProviderInfo:
    raw = raw or {}
    name = raw.get("name") or provider_id.replace("-", " ").title()
    website = raw.get("website") or raw.get("provider_website") or ""
    pricing_page = raw.get("pricing_page") or website or ""
    affiliate_link = raw.get("affiliate_link")
    return ProviderInfo(
        name=name,
        website=str(website),
        pricing_page=str(pricing_page),
        affiliate_link=str(affiliate_link) if affiliate_link else None,
    )


def normalize_openrouter_model(raw: dict[str, Any], fetched_at: str) -> ModelInfo | None:
    model_id = str(raw.get("id") or "").strip()
    if not model_id:
        return None
    display_name = str(raw.get("name") or model_id)
    provider = extract_provider(model_id, raw.get("provider"))
    pricing = raw.get("pricing") or {}
    top_provider = raw.get("top_provider") or {}
    model_type = infer_model_type(raw.get("architecture", {}).get("modality"), model_id, display_name)
    haystack = f"{model_id} {display_name}".lower()
    source = SourceInfo(
        price_input=parse_price_per_million(pricing.get("prompt")) or 0.0,
        price_output=parse_price_per_million(pricing.get("completion")) or 0.0,
        price_cache_read=parse_price_per_million(pricing.get("input_cache_read")),
        price_cache_creation=parse_price_per_million(pricing.get("input_cache_write")),
        last_updated=datetime.fromisoformat(fetched_at),
    )
    return ModelInfo(
        provider=provider,
        model_id=model_id,
        display_name=display_name,
        pricing=PricingInfo(
            input_per_million=source.price_input,
            output_per_million=source.price_output,
            cache_read_per_million=source.price_cache_read,
            cache_creation_per_million=source.price_cache_creation,
            currency="USD",
        ),
        context_window=parse_int(raw.get("context_length") or top_provider.get("context_length")),
        max_output_tokens=parse_int(top_provider.get("max_completion_tokens") or raw.get("top_provider", {}).get("max_output_tokens")),
        model_type=model_type,
        supports_vision=infer_supports_vision(raw, model_type, haystack),
        supports_function_calling=infer_supports_function_calling(raw),
        supports_streaming=infer_supports_streaming(raw),
        category=infer_category(model_id, display_name),
        sources={"openrouter": source},
        affiliate_links={},
    )


def normalize_litellm_model(model_id: str, raw: dict[str, Any], fetched_at: str) -> ModelInfo | None:
    if not model_id:
        return None
    display_name = str(raw.get("label") or raw.get("litellm_provider") or model_id)
    provider = extract_provider(model_id, raw.get("litellm_provider"))
    model_type = infer_model_type(raw.get("mode"), model_id, display_name)
    haystack = f"{model_id} {display_name}".lower()
    source = SourceInfo(
        price_input=parse_price_per_million(raw.get("input_cost_per_token")) or 0.0,
        price_output=parse_price_per_million(raw.get("output_cost_per_token")) or 0.0,
        price_cache_read=parse_price_per_million(raw.get("cache_read_input_token_cost")),
        price_cache_creation=parse_price_per_million(raw.get("cache_creation_input_token_cost")),
        last_updated=datetime.fromisoformat(fetched_at),
    )
    return ModelInfo(
        provider=provider,
        model_id=model_id,
        display_name=display_name,
        pricing=PricingInfo(
            input_per_million=source.price_input,
            output_per_million=source.price_output,
            cache_read_per_million=source.price_cache_read,
            cache_creation_per_million=source.price_cache_creation,
            currency="USD",
        ),
        context_window=parse_int(raw.get("max_input_tokens") or raw.get("max_tokens")),
        max_output_tokens=parse_int(raw.get("max_output_tokens") or raw.get("max_tokens")),
        model_type=model_type,
        supports_vision=infer_supports_vision(raw, model_type, haystack),
        supports_function_calling=bool(raw.get("supports_function_calling", False)),
        supports_streaming=bool(raw.get("supports_streaming", True)),
        category=infer_category(model_id, display_name),
        sources={"litellm": source},
        affiliate_links={},
    )


def merge_model(existing: ModelInfo, incoming: ModelInfo) -> ModelInfo:
    merged_sources = {**existing.sources, **incoming.sources}
    pricing = PricingInfo(
        input_per_million=existing.pricing.input_per_million or incoming.pricing.input_per_million,
        output_per_million=existing.pricing.output_per_million or incoming.pricing.output_per_million,
        cache_read_per_million=existing.pricing.cache_read_per_million if existing.pricing.cache_read_per_million is not None else incoming.pricing.cache_read_per_million,
        cache_creation_per_million=existing.pricing.cache_creation_per_million if existing.pricing.cache_creation_per_million is not None else incoming.pricing.cache_creation_per_million,
        currency="USD",
    )
    return existing.model_copy(
        update={
            "display_name": existing.display_name if existing.display_name != existing.model_id else incoming.display_name,
            "pricing": pricing,
            "context_window": max(existing.context_window, incoming.context_window),
            "max_output_tokens": max(existing.max_output_tokens, incoming.max_output_tokens),
            "supports_vision": existing.supports_vision or incoming.supports_vision,
            "supports_function_calling": existing.supports_function_calling or incoming.supports_function_calling,
            "supports_streaming": existing.supports_streaming or incoming.supports_streaming,
            "sources": merged_sources,
            "category": existing.category if existing.category != "standard" else incoming.category,
        }
    )


def normalize_sources(openrouter_payload: dict[str, Any], litellm_payload: dict[str, Any]) -> PricingData:
    models: dict[str, ModelInfo] = {}
    providers: dict[str, ProviderInfo] = {}

    openrouter_fetched_at = str(openrouter_payload["fetched_at"])
    last_scrape = datetime.fromisoformat(openrouter_fetched_at)
    openrouter_data = openrouter_payload.get("data", [])
    if isinstance(openrouter_data, dict):
        openrouter_models = openrouter_data.get("data", [])
    else:
        openrouter_models = openrouter_data
    for raw in openrouter_models:
        model = normalize_openrouter_model(raw, openrouter_fetched_at)
        if model is None:
            continue
        models[model.model_id] = model if model.model_id not in models else merge_model(models[model.model_id], model)
        providers.setdefault(model.provider, build_provider_info(model.provider, raw.get("top_provider") or raw))
    litellm_fetched_at = str(litellm_payload["fetched_at"])
    last_scrape = max(last_scrape, datetime.fromisoformat(litellm_fetched_at))
    litellm_models = litellm_payload.get("data", {})
    for model_id, raw in litellm_models.items():
        if not isinstance(raw, dict):
            continue
        model = normalize_litellm_model(model_id, raw, litellm_fetched_at)
        if model is None:
            continue
        models[model.model_id] = model if model.model_id not in models else merge_model(models[model.model_id], model)
        providers.setdefault(model.provider, build_provider_info(model.provider, raw))
    category_counts = Counter(model.category for model in models.values())
    return PricingData(
        generated_at=datetime.now(timezone.utc),
        models=dict(sorted(models.items())),
        providers=dict(sorted(providers.items())),
        metadata=MetadataInfo(
            total_models=len(models),
            sources=["openrouter", "litellm"],
            last_scrape=last_scrape,
            categories=dict(sorted(category_counts.items())),
        ),
    )
