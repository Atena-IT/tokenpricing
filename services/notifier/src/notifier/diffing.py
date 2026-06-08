from __future__ import annotations

from datetime import datetime, timezone

from notifier.models import DetectedEvent, EventType, ModelStatus, NormalizedModel


def detect_events(
    previous_models: dict[str, NormalizedModel],
    current_models: dict[str, NormalizedModel],
    *,
    occurred_at: datetime | None = None,
) -> list[DetectedEvent]:
    event_time = occurred_at or datetime.now(timezone.utc)
    events: list[DetectedEvent] = []

    for model_id, current in current_models.items():
        previous = previous_models.get(model_id)
        if previous is None:
            events.append(
                DetectedEvent(
                    type=EventType.MODEL_ADDED,
                    occurred_at=event_time,
                    model=current,
                    payload={"after": current.model_dump(mode="json")},
                )
            )
            continue

        price_changed = (
            current.input_per_million != previous.input_per_million
            or current.output_per_million != previous.output_per_million
        )
        if price_changed:
            before = {
                "input_per_million": previous.input_per_million,
                "output_per_million": previous.output_per_million,
                "currency": previous.currency,
            }
            after = {
                "input_per_million": current.input_per_million,
                "output_per_million": current.output_per_million,
                "currency": current.currency,
            }
            events.append(
                DetectedEvent(
                    type=EventType.PRICING_CHANGED,
                    occurred_at=event_time,
                    model=current,
                    payload={"before": before, "after": after},
                )
            )
            current_total = current.input_per_million + current.output_per_million
            previous_total = previous.input_per_million + previous.output_per_million
            if current_total > previous_total:
                events.append(
                    DetectedEvent(
                        type=EventType.PRICING_INCREASED,
                        occurred_at=event_time,
                        model=current,
                        payload={"before": before, "after": after},
                    )
                )
            elif current_total < previous_total:
                events.append(
                    DetectedEvent(
                        type=EventType.PRICING_DECREASED,
                        occurred_at=event_time,
                        model=current,
                        payload={"before": before, "after": after},
                    )
                )

        cache_changed = (
            current.cache_read_per_million != previous.cache_read_per_million
            or current.cache_creation_per_million != previous.cache_creation_per_million
        )
        if cache_changed:
            events.append(
                DetectedEvent(
                    type=EventType.CACHE_PRICE_CHANGED,
                    occurred_at=event_time,
                    model=current,
                    payload={
                        "before": {
                            "cache_read_per_million": previous.cache_read_per_million,
                            "cache_creation_per_million": previous.cache_creation_per_million,
                            "currency": previous.currency,
                        },
                        "after": {
                            "cache_read_per_million": current.cache_read_per_million,
                            "cache_creation_per_million": current.cache_creation_per_million,
                            "currency": current.currency,
                        },
                    },
                )
            )

        if (
            previous.status != ModelStatus.DEPRECATED
            and current.status == ModelStatus.DEPRECATED
        ):
            events.append(
                DetectedEvent(
                    type=EventType.MODEL_DEPRECATED,
                    occurred_at=event_time,
                    model=current,
                    payload={
                        "before_status": previous.status.value,
                        "after_status": current.status.value,
                    },
                )
            )

    for model_id, previous in previous_models.items():
        if model_id in current_models:
            continue
        removed_model = previous.model_copy(update={"status": ModelStatus.REMOVED})
        events.append(
            DetectedEvent(
                type=EventType.MODEL_REMOVED,
                occurred_at=event_time,
                model=removed_model,
                payload={"before": previous.model_dump(mode="json")},
            )
        )

    return events
