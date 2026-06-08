from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from tokenpricing.modeling import PricingData
from tokenpricing.pricing import get_pricing_data

from notifier.diffing import detect_events
from notifier.families import derive_model_family
from notifier.matching import subscription_matches_event
from notifier.models import (
    DeliveryFlushResult,
    DeliveryRecord,
    DeliveryStatus,
    DetectedEvent,
    EventType,
    ModelStatus,
    NormalizedModel,
    SecretRotationResponse,
    SubscriptionCreate,
    SubscriptionRecord,
    SubscriptionUpdate,
    SyncResult,
)
from notifier.storage import NotifierStore, utcnow
from notifier.webhooks import dispatch_webhook, next_retry_time

PricingFetcher = Callable[[bool], Awaitable[PricingData]]
WebhookDispatcher = Callable[[DeliveryRecord, str], Awaitable]
DEPRECATED_STATUS_PATTERN = re.compile(
    r"(?<![\w-])(deprecated|legacy|retired|sunset|eol)(?![\w-])"
)


async def default_pricing_fetcher(force_refresh: bool = False) -> PricingData:
    return await get_pricing_data(force_refresh=force_refresh)


class NotifierService:
    def __init__(
        self,
        db_path: str | Path,
        *,
        pricing_fetcher: PricingFetcher = default_pricing_fetcher,
        webhook_dispatcher: WebhookDispatcher = dispatch_webhook,
    ):
        self.store = NotifierStore(db_path)
        self.pricing_fetcher = pricing_fetcher
        self.webhook_dispatcher = webhook_dispatcher

    def create_subscription(self, request: SubscriptionCreate) -> SubscriptionRecord:
        return self.store.create_subscription(request)

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        return self.store.list_subscriptions()

    def get_subscription(self, subscription_id: str) -> SubscriptionRecord:
        return self.store.get_subscription(subscription_id)

    def update_subscription(
        self,
        subscription_id: str,
        request: SubscriptionUpdate,
    ) -> SubscriptionRecord:
        return self.store.update_subscription(subscription_id, request)

    def delete_subscription(self, subscription_id: str) -> None:
        self.store.delete_subscription(subscription_id)

    def rotate_secret(self, subscription_id: str) -> SecretRotationResponse:
        return self.store.rotate_secret(subscription_id)

    async def verify_subscription(self, subscription_id: str) -> DeliveryFlushResult:
        self.get_subscription(subscription_id)
        subscription = self.store.mark_verified(subscription_id)
        await self._enqueue_test_delivery(subscription, event_type=EventType.TEST)
        return await self.flush_deliveries()

    async def send_test_notification(self, subscription_id: str) -> DeliveryFlushResult:
        subscription = self.get_subscription(subscription_id)
        await self._enqueue_test_delivery(subscription, event_type=EventType.TEST)
        return await self.flush_deliveries()

    async def _enqueue_test_delivery(
        self,
        subscription: SubscriptionRecord,
        *,
        event_type: EventType,
    ) -> None:
        now = utcnow()
        event = DetectedEvent(
            type=event_type,
            occurred_at=now,
            model=NormalizedModel(
                model_id=subscription.filters.model_id or "tokenpricing/notifier-test",
                provider=subscription.filters.provider or "tokenpricing",
                display_name="Notifier test event",
                model_family=subscription.filters.model_family or "notifier-test",
                model_type=subscription.filters.model_type or "service",
                category=subscription.filters.category or "test",
                supports_vision=subscription.filters.supports_vision is True,
                supports_function_calling=(
                    subscription.filters.supports_function_calling is True
                ),
                input_per_million=0.0,
                output_per_million=0.0,
                cache_read_per_million=0.0,
                cache_creation_per_million=0.0,
                currency="USD",
                status=ModelStatus.ACTIVE,
            ),
            payload={"message": "tokenpricing notifier webhook test"},
        )
        persisted = self.store.save_events(None, [event])[0]
        self.store.enqueue_deliveries(
            [self._build_delivery(subscription, persisted, now)]
        )

    async def sync_once(self, *, force_refresh: bool = False) -> SyncResult:
        latest_snapshot = self.store.get_latest_snapshot_models()
        previous_models = (
            {model.model_id: model for model in latest_snapshot[1]}
            if latest_snapshot
            else {}
        )
        data = await self.pricing_fetcher(force_refresh)
        current_models_list = normalize_pricing_data(data)
        snapshot_id = self.store.create_snapshot(data.generated_at, current_models_list)
        if not previous_models:
            return SyncResult(
                snapshot_id=snapshot_id,
                models_processed=len(current_models_list),
                events_detected=0,
                deliveries_enqueued=0,
            )

        current_models = {model.model_id: model for model in current_models_list}
        events = detect_events(previous_models, current_models, occurred_at=utcnow())
        events = self.store.save_events(snapshot_id, events)
        subscriptions = self.store.list_subscriptions()
        deliveries = self._match_and_queue(events, subscriptions)
        return SyncResult(
            snapshot_id=snapshot_id,
            models_processed=len(current_models_list),
            events_detected=len(events),
            deliveries_enqueued=len(deliveries),
        )

    def _match_and_queue(
        self,
        events: list[DetectedEvent],
        subscriptions: list[SubscriptionRecord],
    ) -> list[DeliveryRecord]:
        now = utcnow()
        deliveries: list[DeliveryRecord] = []
        for event in events:
            for subscription in subscriptions:
                if subscription_matches_event(subscription, event):
                    deliveries.append(self._build_delivery(subscription, event, now))
        return self.store.enqueue_deliveries(deliveries)

    def _build_delivery(
        self,
        subscription: SubscriptionRecord,
        event: DetectedEvent,
        now: datetime,
    ) -> DeliveryRecord:
        payload = {
            "delivery_id": None,
            "subscription_id": subscription.id,
            "event": {
                "id": event.id,
                "type": event.type.value,
                "occurred_at": event.occurred_at.isoformat(),
                "model": event.model.model_dump(mode="json"),
                "payload": event.payload,
            },
        }
        delivery = DeliveryRecord(
            event_id=event.id,
            subscription_id=subscription.id,
            webhook_url=subscription.webhook_url,
            next_attempt_at=now,
            created_at=now,
            payload=payload,
        )
        delivery.payload["delivery_id"] = delivery.id
        return delivery

    async def flush_deliveries(self) -> DeliveryFlushResult:
        deliveries = self.store.get_due_deliveries()
        attempted = sent = failed = 0
        subscription_cache: dict[str, SubscriptionRecord | None] = {}
        for delivery in deliveries:
            attempted += 1
            attempt_time = utcnow()
            if delivery.subscription_id not in subscription_cache:
                try:
                    subscription_cache[delivery.subscription_id] = (
                        self.get_subscription(delivery.subscription_id)
                    )
                except KeyError:
                    subscription_cache[delivery.subscription_id] = None
            subscription = subscription_cache[delivery.subscription_id]
            if subscription is None:
                failed += 1
                self.store.update_delivery(
                    delivery.id,
                    status=DeliveryStatus.DEAD_LETTER,
                    attempts=delivery.attempts + 1,
                    next_attempt_at=attempt_time,
                    last_attempt_at=attempt_time,
                    delivered_at=None,
                    last_error="subscription deleted before delivery",
                    response_status=None,
                )
                continue
            result = await self.webhook_dispatcher(delivery, subscription.secret)
            next_attempt = next_retry_time(attempt_time, delivery.attempts + 1)
            if result.success:
                sent += 1
                self.store.update_delivery(
                    delivery.id,
                    status=DeliveryStatus.SENT,
                    attempts=delivery.attempts + 1,
                    next_attempt_at=next_attempt,
                    last_attempt_at=attempt_time,
                    delivered_at=attempt_time,
                    last_error=None,
                    response_status=result.status_code,
                )
                continue

            failed += 1
            status = (
                DeliveryStatus.DEAD_LETTER
                if delivery.attempts + 1 >= delivery.max_attempts
                else DeliveryStatus.FAILED
            )
            self.store.update_delivery(
                delivery.id,
                status=status,
                attempts=delivery.attempts + 1,
                next_attempt_at=next_attempt,
                last_attempt_at=attempt_time,
                delivered_at=None,
                last_error=result.error,
                response_status=result.status_code,
            )
        return DeliveryFlushResult(attempted=attempted, sent=sent, failed=failed)


def normalize_pricing_data(data: PricingData) -> list[NormalizedModel]:
    models: list[NormalizedModel] = []
    for model in data.models.values():
        status = infer_model_status(
            model.display_name,
            model.category,
            model.model_type,
        )
        models.append(
            NormalizedModel(
                model_id=model.model_id,
                provider=model.provider,
                display_name=model.display_name,
                model_family=derive_model_family(model.model_id, model.display_name),
                model_type=model.model_type,
                category=model.category,
                supports_vision=model.supports_vision,
                supports_function_calling=model.supports_function_calling,
                input_per_million=model.pricing.input_per_million,
                output_per_million=model.pricing.output_per_million,
                cache_read_per_million=model.pricing.cache_read_per_million,
                cache_creation_per_million=model.pricing.cache_creation_per_million,
                currency=model.pricing.currency,
                status=status,
            )
        )
    return sorted(models, key=lambda model: model.model_id)


def infer_model_status(*fields: str) -> ModelStatus:
    joined = " ".join(field.lower() for field in fields)
    if DEPRECATED_STATUS_PATTERN.search(joined):
        return ModelStatus.DEPRECATED
    return ModelStatus.ACTIVE
