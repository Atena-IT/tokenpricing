from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from notifier.models import (
    DeliveryListItem,
    DeliveryRecord,
    DeliveryStatus,
    DetectedEvent,
    EventListItem,
    ModelStatus,
    NormalizedModel,
    SecretRotationResponse,
    SubscriptionCreate,
    SubscriptionFilters,
    SubscriptionRecord,
    SubscriptionStatus,
    SubscriptionUpdate,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_models (
    snapshot_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    display_name TEXT NOT NULL,
    model_family TEXT NOT NULL,
    model_type TEXT NOT NULL,
    category TEXT NOT NULL,
    supports_vision INTEGER NOT NULL,
    supports_function_calling INTEGER NOT NULL,
    input_per_million REAL NOT NULL,
    output_per_million REAL NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, model_id),
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    webhook_url TEXT NOT NULL,
    description TEXT,
    secret TEXT NOT NULL,
    status TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    verified_at TEXT,
    paused_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    snapshot_id INTEGER,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    model_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    webhook_url TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    max_attempts INTEGER NOT NULL,
    next_attempt_at TEXT NOT NULL,
    last_attempt_at TEXT,
    delivered_at TEXT,
    last_error TEXT,
    response_status INTEGER,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotifierStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _row_to_subscription(self, row: sqlite3.Row) -> SubscriptionRecord:
        return SubscriptionRecord(
            id=row["id"],
            webhook_url=row["webhook_url"],
            description=row["description"],
            status=SubscriptionStatus(row["status"]),
            secret=row["secret"],
            filters=SubscriptionFilters.model_validate(json.loads(row["filters_json"])),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            verified_at=(
                datetime.fromisoformat(row["verified_at"])
                if row["verified_at"]
                else None
            ),
            paused_at=(
                datetime.fromisoformat(row["paused_at"]) if row["paused_at"] else None
            ),
        )

    def create_subscription(self, request: SubscriptionCreate) -> SubscriptionRecord:
        subscription_id = secrets.token_hex(12)
        now = utcnow()
        secret = request.secret or secrets.token_urlsafe(32)
        filters_json = json.dumps(
            request.filters.model_dump(mode="json"), sort_keys=True
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subscriptions (
                    id, webhook_url, description, secret, status, filters_json,
                    created_at, updated_at, verified_at, paused_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subscription_id,
                    str(request.webhook_url),
                    request.description,
                    secret,
                    SubscriptionStatus.ACTIVE.value,
                    filters_json,
                    now.isoformat(),
                    now.isoformat(),
                    None,
                    None,
                ),
            )
        return self.get_subscription(subscription_id)

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subscriptions WHERE status != ? ORDER BY created_at DESC",
                (SubscriptionStatus.DELETED.value,),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def get_subscription(self, subscription_id: str) -> SubscriptionRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ? AND status != ?",
                (subscription_id, SubscriptionStatus.DELETED.value),
            ).fetchone()
        if row is None:
            raise KeyError(subscription_id)
        return self._row_to_subscription(row)

    def update_subscription(
        self,
        subscription_id: str,
        request: SubscriptionUpdate,
    ) -> SubscriptionRecord:
        current = self.get_subscription(subscription_id)
        now = utcnow()
        status = request.status or current.status
        paused_at = current.paused_at
        if status == SubscriptionStatus.PAUSED:
            paused_at = current.paused_at or now
        elif status == SubscriptionStatus.ACTIVE:
            paused_at = None
        filters = request.filters or current.filters
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE subscriptions
                SET webhook_url = ?, description = ?, status = ?, filters_json = ?,
                    updated_at = ?, paused_at = ?
                WHERE id = ?
                """,
                (
                    str(request.webhook_url or current.webhook_url),
                    request.description
                    if request.description is not None
                    else current.description,
                    status.value,
                    json.dumps(filters.model_dump(mode="json"), sort_keys=True),
                    now.isoformat(),
                    paused_at.isoformat() if paused_at else None,
                    subscription_id,
                ),
            )
        return self.get_subscription(subscription_id)

    def delete_subscription(self, subscription_id: str) -> None:
        now = utcnow()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE subscriptions
                SET status = ?, updated_at = ?, paused_at = ?
                WHERE id = ?
                """,
                (
                    SubscriptionStatus.DELETED.value,
                    now.isoformat(),
                    now.isoformat(),
                    subscription_id,
                ),
            )

    def mark_verified(self, subscription_id: str) -> SubscriptionRecord:
        now = utcnow()
        with self._connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET verified_at = ?, updated_at = ? WHERE id = ?",
                (now.isoformat(), now.isoformat(), subscription_id),
            )
        return self.get_subscription(subscription_id)

    def rotate_secret(self, subscription_id: str) -> SecretRotationResponse:
        now = utcnow()
        secret = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET secret = ?, updated_at = ? WHERE id = ?",
                (secret, now.isoformat(), subscription_id),
            )
        return SecretRotationResponse(
            subscription_id=subscription_id,
            secret=secret,
            rotated_at=now,
        )

    def get_latest_snapshot_models(self) -> tuple[int, list[NormalizedModel]] | None:
        with self._connect() as connection:
            snapshot = connection.execute(
                "SELECT id FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if snapshot is None:
                return None
            rows = connection.execute(
                "SELECT * FROM snapshot_models WHERE snapshot_id = ?",
                (snapshot["id"],),
            ).fetchall()
        return snapshot["id"], [self._row_to_model(row) for row in rows]

    def create_snapshot(
        self,
        generated_at: datetime,
        models: list[NormalizedModel],
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO snapshots (generated_at, created_at) VALUES (?, ?)",
                (generated_at.isoformat(), utcnow().isoformat()),
            )
            snapshot_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO snapshot_models (
                    snapshot_id, model_id, provider, display_name, model_family,
                    model_type, category, supports_vision, supports_function_calling,
                    input_per_million, output_per_million, currency, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id,
                        model.model_id,
                        model.provider,
                        model.display_name,
                        model.model_family,
                        model.model_type,
                        model.category,
                        int(model.supports_vision),
                        int(model.supports_function_calling),
                        model.input_per_million,
                        model.output_per_million,
                        model.currency,
                        model.status.value,
                    )
                    for model in models
                ],
            )
        return snapshot_id

    def _row_to_model(self, row: sqlite3.Row) -> NormalizedModel:
        return NormalizedModel(
            model_id=row["model_id"],
            provider=row["provider"],
            display_name=row["display_name"],
            model_family=row["model_family"],
            model_type=row["model_type"],
            category=row["category"],
            supports_vision=bool(row["supports_vision"]),
            supports_function_calling=bool(row["supports_function_calling"]),
            input_per_million=row["input_per_million"],
            output_per_million=row["output_per_million"],
            currency=row["currency"],
            status=ModelStatus(row["status"]),
        )

    def save_events(
        self, snapshot_id: int | None, events: list[DetectedEvent]
    ) -> list[DetectedEvent]:
        if not events:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO events (id, snapshot_id, event_type, occurred_at, model_json, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.id,
                        snapshot_id,
                        event.type.value,
                        event.occurred_at.isoformat(),
                        json.dumps(event.model.model_dump(mode="json"), sort_keys=True),
                        json.dumps(event.payload, sort_keys=True),
                    )
                    for event in events
                ],
            )
        return [
            event.model_copy(update={"snapshot_id": snapshot_id}) for event in events
        ]

    def enqueue_deliveries(
        self,
        deliveries: list[DeliveryRecord],
    ) -> list[DeliveryRecord]:
        if not deliveries:
            return []
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO deliveries (
                    id, event_id, subscription_id, webhook_url, status, attempts,
                    max_attempts, next_attempt_at, last_attempt_at, delivered_at,
                    last_error, response_status, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        delivery.id,
                        delivery.event_id,
                        delivery.subscription_id,
                        str(delivery.webhook_url),
                        delivery.status.value,
                        delivery.attempts,
                        delivery.max_attempts,
                        delivery.next_attempt_at.isoformat(),
                        delivery.last_attempt_at.isoformat()
                        if delivery.last_attempt_at
                        else None,
                        delivery.delivered_at.isoformat()
                        if delivery.delivered_at
                        else None,
                        delivery.last_error,
                        delivery.response_status,
                        delivery.created_at.isoformat(),
                        json.dumps(delivery.payload, sort_keys=True),
                    )
                    for delivery in deliveries
                ],
            )
        return deliveries

    def get_due_deliveries(self, now: datetime | None = None) -> list[DeliveryRecord]:
        current_time = (now or utcnow()).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM deliveries
                WHERE status IN (?, ?) AND next_attempt_at <= ?
                ORDER BY created_at ASC
                """,
                (
                    DeliveryStatus.PENDING.value,
                    DeliveryStatus.FAILED.value,
                    current_time,
                ),
            ).fetchall()
        return [self._row_to_delivery(row) for row in rows]

    def update_delivery(
        self,
        delivery_id: str,
        *,
        status: DeliveryStatus,
        attempts: int,
        next_attempt_at: datetime,
        last_attempt_at: datetime,
        delivered_at: datetime | None,
        last_error: str | None,
        response_status: int | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE deliveries
                SET status = ?, attempts = ?, next_attempt_at = ?, last_attempt_at = ?,
                    delivered_at = ?, last_error = ?, response_status = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    attempts,
                    next_attempt_at.isoformat(),
                    last_attempt_at.isoformat(),
                    delivered_at.isoformat() if delivered_at else None,
                    last_error,
                    response_status,
                    delivery_id,
                ),
            )

    def _row_to_delivery(self, row: sqlite3.Row) -> DeliveryRecord:
        return DeliveryRecord(
            id=row["id"],
            event_id=row["event_id"],
            subscription_id=row["subscription_id"],
            webhook_url=row["webhook_url"],
            status=DeliveryStatus(row["status"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            next_attempt_at=datetime.fromisoformat(row["next_attempt_at"]),
            last_attempt_at=(
                datetime.fromisoformat(row["last_attempt_at"])
                if row["last_attempt_at"]
                else None
            ),
            delivered_at=(
                datetime.fromisoformat(row["delivered_at"])
                if row["delivered_at"]
                else None
            ),
            last_error=row["last_error"],
            response_status=row["response_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            payload=json.loads(row["payload_json"]),
        )

    def list_events(self, limit: int = 100) -> list[EventListItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY occurred_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items: list[EventListItem] = []
        for row in rows:
            model_data = json.loads(row["model_json"])
            items.append(
                EventListItem(
                    id=row["id"],
                    snapshot_id=row["snapshot_id"],
                    type=row["event_type"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    model_id=model_data["model_id"],
                    provider=model_data["provider"],
                    model_family=model_data["model_family"],
                    model_type=model_data["model_type"],
                    category=model_data["category"],
                    payload=json.loads(row["payload_json"]),
                )
            )
        return items

    def list_deliveries(self, limit: int = 100) -> list[DeliveryListItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM deliveries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            DeliveryListItem(
                id=row["id"],
                event_id=row["event_id"],
                subscription_id=row["subscription_id"],
                status=row["status"],
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
                webhook_url=row["webhook_url"],
                next_attempt_at=datetime.fromisoformat(row["next_attempt_at"]),
                last_attempt_at=(
                    datetime.fromisoformat(row["last_attempt_at"])
                    if row["last_attempt_at"]
                    else None
                ),
                delivered_at=(
                    datetime.fromisoformat(row["delivered_at"])
                    if row["delivered_at"]
                    else None
                ),
                response_status=row["response_status"],
                last_error=row["last_error"],
            )
            for row in rows
        ]
