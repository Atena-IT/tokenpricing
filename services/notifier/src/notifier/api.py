from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response

from notifier.models import (
    DeliveryFlushResult,
    HealthResponse,
    SecretRotationResponse,
    SubscriptionCreate,
    SubscriptionRecord,
    SubscriptionUpdate,
    SyncResult,
)
from notifier.service import NotifierService

DEFAULT_DB_PATH = Path("./database/notifier.db")


def create_app(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    service: NotifierService | None = None,
) -> FastAPI:
    app = FastAPI(title="tokenpricing notifier", version="0.1.0")
    app.state.service = service or NotifierService(db_path)

    def get_service() -> NotifierService:
        return app.state.service

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/subscriptions", response_model=list[SubscriptionRecord])
    async def list_subscriptions() -> list[SubscriptionRecord]:
        return get_service().list_subscriptions()

    @app.post("/subscriptions", response_model=SubscriptionRecord, status_code=201)
    async def create_subscription(request: SubscriptionCreate) -> SubscriptionRecord:
        return get_service().create_subscription(request)

    @app.get("/subscriptions/{subscription_id}", response_model=SubscriptionRecord)
    async def get_subscription(subscription_id: str) -> SubscriptionRecord:
        try:
            return get_service().get_subscription(subscription_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc

    @app.patch("/subscriptions/{subscription_id}", response_model=SubscriptionRecord)
    async def update_subscription(
        subscription_id: str,
        request: SubscriptionUpdate,
    ) -> SubscriptionRecord:
        try:
            return get_service().update_subscription(subscription_id, request)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc

    @app.delete("/subscriptions/{subscription_id}", status_code=204)
    async def delete_subscription(subscription_id: str) -> Response:
        try:
            get_service().delete_subscription(subscription_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc
        return Response(status_code=204)

    @app.post(
        "/subscriptions/{subscription_id}/verify",
        response_model=DeliveryFlushResult,
    )
    async def verify_subscription(subscription_id: str) -> DeliveryFlushResult:
        try:
            return await get_service().verify_subscription(subscription_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc

    @app.post(
        "/subscriptions/{subscription_id}/test",
        response_model=DeliveryFlushResult,
    )
    async def test_subscription(subscription_id: str) -> DeliveryFlushResult:
        try:
            return await get_service().send_test_notification(subscription_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc

    @app.post(
        "/subscriptions/{subscription_id}/rotate-secret",
        response_model=SecretRotationResponse,
    )
    async def rotate_secret(subscription_id: str) -> SecretRotationResponse:
        try:
            return get_service().rotate_secret(subscription_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="subscription not found"
            ) from exc

    @app.post("/sync", response_model=SyncResult)
    async def sync(force_refresh: bool = False) -> SyncResult:
        return await get_service().sync_once(force_refresh=force_refresh)

    @app.post("/deliveries/flush", response_model=DeliveryFlushResult)
    async def flush_deliveries() -> DeliveryFlushResult:
        return await get_service().flush_deliveries()

    @app.get("/events")
    async def list_events(limit: int = 100):
        return get_service().store.list_events(limit=limit)

    @app.get("/deliveries")
    async def list_deliveries(limit: int = 100):
        return get_service().store.list_deliveries(limit=limit)

    return app
