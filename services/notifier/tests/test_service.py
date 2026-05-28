from __future__ import annotations

from datetime import datetime

from tokenpricing.modeling import (
    MetadataInfo,
    ModelInfo,
    PricingData,
    PricingInfo,
    ProviderInfo,
)

from notifier.models import EventType, SubscriptionCreate, SubscriptionFilters
from notifier.service import NotifierService


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
