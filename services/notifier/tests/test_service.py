from __future__ import annotations

from datetime import datetime

import pytest
from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
)

from notifier.models import (
    DeliveryStatus,
    EventType,
    ModelStatus,
    SubscriptionCreate,
    SubscriptionFilters,
)
from notifier.service import NotifierService, infer_model_status, normalize_pricing_data


class SequenceFetcher:
    def __init__(self, *datasets: PricingData):
        self.datasets = list(datasets)
        self.index = 0

    async def __call__(self, force_refresh: bool = False) -> PricingData:
        dataset = self.datasets[min(self.index, len(self.datasets) - 1)]
        self.index += 1
        return dataset


class RecordingDispatcher:
    def __init__(self) -> None:
        self.deliveries = []

    async def __call__(self, delivery, secret: str):
        self.deliveries.append((delivery, secret))
        from notifier.models import DeliveryAttemptResult

        return DeliveryAttemptResult(success=True, status_code=202)


def build_dataset(input_price: float) -> PricingData:
    now = datetime(2026, 5, 28)
    model = ModelInfo(
        provider="openai",
        model_id="openai/gpt-5.2",
        display_name="OpenAI GPT-5.2",
        pricing=PricingInfo(
            input_per_million=input_price,
            output_per_million=2.0,
            cache_read_per_million=0.5,
            cache_creation_per_million=1.5,
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


@pytest.mark.asyncio
async def test_sync_and_delivery_flow(tmp_path) -> None:
    dispatcher = RecordingDispatcher()
    service = NotifierService(
        tmp_path / "notifier.db",
        pricing_fetcher=SequenceFetcher(build_dataset(1.0), build_dataset(1.5)),
        webhook_dispatcher=dispatcher,
    )
    subscription = service.create_subscription(
        SubscriptionCreate(
            webhook_url="https://example.com/webhook",
            filters=SubscriptionFilters(
                provider="openai",
                event_types=[EventType.PRICING_CHANGED],
            ),
        )
    )

    first_sync = await service.sync_once()
    second_sync = await service.sync_once()
    flush_result = await service.flush_deliveries()

    assert first_sync.events_detected == 0
    assert second_sync.events_detected == 2
    assert second_sync.deliveries_enqueued == 1
    assert flush_result.sent == 1
    assert dispatcher.deliveries[0][1] == subscription.secret


@pytest.mark.asyncio
async def test_flush_deliveries_dead_letters_deleted_subscriptions(tmp_path) -> None:
    dispatcher = RecordingDispatcher()
    service = NotifierService(
        tmp_path / "notifier.db",
        pricing_fetcher=SequenceFetcher(build_dataset(1.0), build_dataset(1.5)),
        webhook_dispatcher=dispatcher,
    )
    deleted_subscription = service.create_subscription(
        SubscriptionCreate(
            webhook_url="https://example.com/deleted",
            filters=SubscriptionFilters(
                provider="openai",
                event_types=[EventType.PRICING_CHANGED],
            ),
        )
    )
    active_subscription = service.create_subscription(
        SubscriptionCreate(
            webhook_url="https://example.com/active",
            filters=SubscriptionFilters(
                provider="openai",
                event_types=[EventType.PRICING_CHANGED],
            ),
        )
    )

    await service.sync_once()
    await service.sync_once()
    service.delete_subscription(deleted_subscription.id)

    flush_result = await service.flush_deliveries()
    deliveries = service.store.list_deliveries()
    deleted_delivery = next(
        item for item in deliveries if item.subscription_id == deleted_subscription.id
    )
    active_delivery = next(
        item for item in deliveries if item.subscription_id == active_subscription.id
    )

    assert flush_result.attempted == 2
    assert flush_result.sent == 1
    assert flush_result.failed == 1
    assert len(dispatcher.deliveries) == 1
    assert dispatcher.deliveries[0][1] == active_subscription.secret
    assert active_delivery.status == DeliveryStatus.SENT.value
    assert deleted_delivery.status == DeliveryStatus.DEAD_LETTER.value
    assert deleted_delivery.last_error == "subscription deleted before delivery"


def test_infer_model_status_uses_word_boundaries() -> None:
    assert infer_model_status("non-deprecated") == ModelStatus.ACTIVE
    assert infer_model_status("Legacy model", "", "") == ModelStatus.DEPRECATED


def test_normalize_pricing_data_preserves_cache_prices() -> None:
    data = build_dataset(1.0)
    normalized = normalize_pricing_data(data)

    assert normalized[0].cache_read_per_million == 0.5
    assert normalized[0].cache_creation_per_million == 1.5
