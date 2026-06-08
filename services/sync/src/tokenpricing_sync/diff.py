from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tokenpricing.modeling import PricingData


def compare_datasets(previous: PricingData | None, current: PricingData) -> dict[str, Any]:
    if previous is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "model_additions": 0,
                "model_removals": 0,
                "pricing_changes": 0,
                "cache_price_changes": 0,
            },
            "changes": [],
        }

    changes: list[dict[str, Any]] = []
    previous_models = previous.models
    current_models = current.models

    for model_id, current_model in current_models.items():
        previous_model = previous_models.get(model_id)
        if previous_model is None:
            changes.append({
                "type": "model_added",
                "model_id": model_id,
                "model_type": current_model.model_type,
                "after": current_model.model_dump(mode="json"),
            })
            continue

        if (
            current_model.pricing.input_per_million != previous_model.pricing.input_per_million
            or current_model.pricing.output_per_million != previous_model.pricing.output_per_million
        ):
            changes.append({
                "type": "pricing_changed",
                "model_id": model_id,
                "model_type": current_model.model_type,
                "before": previous_model.pricing.model_dump(mode="json"),
                "after": current_model.pricing.model_dump(mode="json"),
            })
        if (
            current_model.pricing.cache_read_per_million != previous_model.pricing.cache_read_per_million
            or current_model.pricing.cache_creation_per_million != previous_model.pricing.cache_creation_per_million
        ):
            changes.append({
                "type": "cache_price_changed",
                "model_id": model_id,
                "model_type": current_model.model_type,
                "before": {
                    "cache_read_per_million": previous_model.pricing.cache_read_per_million,
                    "cache_creation_per_million": previous_model.pricing.cache_creation_per_million,
                },
                "after": {
                    "cache_read_per_million": current_model.pricing.cache_read_per_million,
                    "cache_creation_per_million": current_model.pricing.cache_creation_per_million,
                },
            })

    for model_id, previous_model in previous_models.items():
        if model_id not in current_models:
            changes.append({
                "type": "model_removed",
                "model_id": model_id,
                "model_type": previous_model.model_type,
                "before": previous_model.model_dump(mode="json"),
            })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "model_additions": sum(1 for change in changes if change["type"] == "model_added"),
            "model_removals": sum(1 for change in changes if change["type"] == "model_removed"),
            "pricing_changes": sum(1 for change in changes if change["type"] == "pricing_changed"),
            "cache_price_changes": sum(1 for change in changes if change["type"] == "cache_price_changed"),
        },
        "changes": changes[:500],
    }
