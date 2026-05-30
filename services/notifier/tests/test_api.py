from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
)

from notifier.api import create_app
from notifier.service import NotifierService


class StaticFetcher:
    def __init__(self, dataset: PricingData):
        self.dataset = dataset

    async def __call__(self, force_refresh: bool = False) -> PricingData:
        return self.dataset


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, delivery, secret: str):
        self.calls += 1
        from notifier.models import DeliveryAttemptResult

        return DeliveryAttemptResult(success=True, status_code=204)


def build_dataset() -> PricingData:
    now = datetime(2026, 5, 28)
    model = ModelInfo(
        provider="openai",
        model_id="openai/gpt-5.2",
        display_name="OpenAI GPT-5.2",
        pricing=PricingInfo(
            input_per_million=1.0,
            output_per_million=2.0,
            currency="USD",
        ),
        context_window=128000,
        max_output_tokens=8192,
        model_type="chat",
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        category="flagship",
    )
    return PricingData(
        generated_at=now,
        models={model.model_id: model},
        providers={
            "openai": ProviderInfo(
                name="OpenAI",
                website="https://openai.com",
                pricing_page="https://openai.com/pricing",
                affiliate_link="https://platform.openai.com",
            )
        },
        metadata=MetadataInfo(
            total_models=1,
            sources=["test"],
            last_scrape=now,
            categories={"flagship": 1},
        ),
    )


def test_subscription_endpoints_and_test_delivery(tmp_path) -> None:
    dispatcher = RecordingDispatcher()
    service = NotifierService(
        tmp_path / "notifier.db",
        pricing_fetcher=StaticFetcher(build_dataset()),
        webhook_dispatcher=dispatcher,
    )
    client = TestClient(create_app(service=service))

    create_response = client.post(
        "/subscriptions",
        json={
            "webhook_url": "https://example.com/webhook",
            "filters": {"provider": "openai"},
        },
    )
    assert create_response.status_code == 201
    subscription_id = create_response.json()["id"]

    verify_response = client.post(f"/subscriptions/{subscription_id}/verify")
    assert verify_response.status_code == 200
    assert verify_response.json()["sent"] == 1

    sync_response = client.post("/sync")
    assert sync_response.status_code == 200
    assert sync_response.json()["models_processed"] == 1

    events_response = client.get("/events")
    assert events_response.status_code == 200
    assert dispatcher.calls == 1
