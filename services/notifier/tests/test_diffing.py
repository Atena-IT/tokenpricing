from datetime import datetime, timezone

from notifier.diffing import detect_events
from notifier.models import EventType, ModelStatus, NormalizedModel


def build_model(**overrides):
    values = {
        "model_id": "openai/gpt-5.2",
        "provider": "openai",
        "display_name": "GPT-5.2",
        "model_family": "gpt-5.2",
        "model_type": "chat",
        "category": "flagship",
        "supports_vision": True,
        "supports_function_calling": True,
        "input_per_million": 1.0,
        "output_per_million": 2.0,
        "currency": "USD",
        "status": ModelStatus.ACTIVE,
    }
    values.update(overrides)
    return NormalizedModel(**values)


def test_detect_events_for_price_change_and_removal() -> None:
    previous = {
        "openai/gpt-5.2": build_model(),
        "openai/old-model": build_model(
            model_id="openai/old-model",
            model_family="old-model",
        ),
    }
    current = {
        "openai/gpt-5.2": build_model(input_per_million=1.5),
    }

    events = detect_events(previous, current, occurred_at=datetime.now(timezone.utc))
    event_types = {event.type for event in events}

    assert EventType.PRICING_CHANGED in event_types
    assert EventType.PRICING_INCREASED in event_types
    assert EventType.MODEL_REMOVED in event_types


def test_detect_events_for_add_deprecate_and_price_decrease() -> None:
    previous = {
        "openai/gpt-5.2": build_model(
            input_per_million=2.0,
            status=ModelStatus.ACTIVE,
        ),
    }
    current = {
        "openai/gpt-5.2": build_model(
            input_per_million=1.0,
            status=ModelStatus.DEPRECATED,
        ),
        "openai/new-model": build_model(
            model_id="openai/new-model",
            model_family="new-model",
        ),
    }

    events = detect_events(previous, current, occurred_at=datetime.now(timezone.utc))
    event_types = {event.type for event in events}

    assert EventType.MODEL_ADDED in event_types
    assert EventType.MODEL_DEPRECATED in event_types
    assert EventType.PRICING_CHANGED in event_types
    assert EventType.PRICING_DECREASED in event_types


def test_detect_events_uses_total_price_for_direction() -> None:
    previous = {
        "openai/gpt-5.2": build_model(
            input_per_million=1.0,
            output_per_million=2.0,
        ),
    }
    current = {
        "openai/gpt-5.2": build_model(
            input_per_million=2.0,
            output_per_million=1.5,
        ),
    }

    events = detect_events(previous, current, occurred_at=datetime.now(timezone.utc))
    event_types = {event.type for event in events}

    assert EventType.PRICING_CHANGED in event_types
    assert EventType.PRICING_INCREASED in event_types
    assert EventType.PRICING_DECREASED not in event_types
