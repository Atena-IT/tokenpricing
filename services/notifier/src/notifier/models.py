from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EventType(str, Enum):
    PRICING_CHANGED = "pricing_changed"
    PRICING_INCREASED = "pricing_increased"
    PRICING_DECREASED = "pricing_decreased"
    MODEL_DEPRECATED = "model_deprecated"
    MODEL_REMOVED = "model_removed"
    MODEL_ADDED = "model_added"
    TEST = "test"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ModelStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


DEFAULT_EVENT_TYPES = [
    EventType.PRICING_CHANGED,
    EventType.MODEL_DEPRECATED,
    EventType.MODEL_REMOVED,
]


class SubscriptionFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str | None = None
    provider: str | None = None
    model_family: str | None = None
    model_type: str | None = None
    category: str | None = None
    supports_vision: bool | None = None
    supports_function_calling: bool | None = None
    event_types: list[EventType] = Field(
        default_factory=lambda: DEFAULT_EVENT_TYPES.copy()
    )


class SubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_url: HttpUrl
    description: str | None = None
    secret: str | None = None
    filters: SubscriptionFilters = Field(default_factory=SubscriptionFilters)


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_url: HttpUrl | None = None
    description: str | None = None
    status: SubscriptionStatus | None = None
    filters: SubscriptionFilters | None = None


class SecretRotationResponse(BaseModel):
    subscription_id: str
    secret: str
    rotated_at: datetime


class SubscriptionRecord(BaseModel):
    id: str
    webhook_url: HttpUrl
    description: str | None = None
    status: SubscriptionStatus
    secret: str
    filters: SubscriptionFilters
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None = None
    paused_at: datetime | None = None


class NormalizedModel(BaseModel):
    model_id: str
    provider: str
    display_name: str
    model_family: str
    model_type: str
    category: str
    supports_vision: bool
    supports_function_calling: bool
    input_per_million: float
    output_per_million: float
    currency: str
    status: ModelStatus


class DetectedEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: int | None = None
    type: EventType
    occurred_at: datetime
    model: NormalizedModel
    payload: dict[str, Any] = Field(default_factory=dict)


class DeliveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    subscription_id: str
    webhook_url: HttpUrl
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    max_attempts: int = 5
    next_attempt_at: datetime
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None
    response_status: int | None = None
    created_at: datetime
    payload: dict[str, Any]


class DeliveryAttemptResult(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None


class SyncResult(BaseModel):
    snapshot_id: int
    models_processed: int
    events_detected: int
    deliveries_enqueued: int


class DeliveryFlushResult(BaseModel):
    attempted: int
    sent: int
    failed: int


class EventListItem(BaseModel):
    id: str
    snapshot_id: int | None
    type: EventType
    occurred_at: datetime
    model_id: str
    provider: str
    model_family: str
    model_type: str
    category: str
    payload: dict[str, Any]


class DeliveryListItem(BaseModel):
    id: str
    event_id: str
    subscription_id: str
    status: DeliveryStatus
    attempts: int
    max_attempts: int
    webhook_url: HttpUrl
    next_attempt_at: datetime
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    response_status: int | None = None
    last_error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
