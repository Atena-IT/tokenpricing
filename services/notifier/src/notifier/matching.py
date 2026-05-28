from __future__ import annotations

from notifier.models import DetectedEvent, SubscriptionRecord, SubscriptionStatus


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower()


def subscription_matches_event(
    subscription: SubscriptionRecord,
    event: DetectedEvent,
) -> bool:
    if subscription.status != SubscriptionStatus.ACTIVE:
        return False

    filters = subscription.filters
    if filters.event_types and event.type not in filters.event_types:
        return False

    if filters.model_id and filters.model_id != event.model.model_id:
        return False
    if _normalize_text(filters.provider) not in {None, _normalize_text(event.model.provider)}:
        return False
    if _normalize_text(filters.model_family) not in {
        None,
        _normalize_text(event.model.model_family),
    }:
        return False
    if _normalize_text(filters.model_type) not in {
        None,
        _normalize_text(event.model.model_type),
    }:
        return False
    if _normalize_text(filters.category) not in {
        None,
        _normalize_text(event.model.category),
    }:
        return False
    if (
        filters.supports_vision is not None
        and filters.supports_vision != event.model.supports_vision
    ):
        return False
    if (
        filters.supports_function_calling is not None
        and filters.supports_function_calling != event.model.supports_function_calling
    ):
        return False
    return True
