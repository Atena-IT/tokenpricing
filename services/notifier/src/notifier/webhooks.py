from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import httpx

from notifier.models import DeliveryAttemptResult, DeliveryRecord

MAX_ERROR_LENGTH = 2048
RETRY_DELAYS = [0, 60, 300, 1800, 7200]


def sign_payload(secret: str, timestamp: str, body: bytes) -> str:
    message = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def dispatch_webhook(
    delivery: DeliveryRecord,
    secret: str,
    timeout_seconds: float = 10.0,
) -> DeliveryAttemptResult:
    timestamp = datetime.now(timezone.utc).isoformat()
    body = json.dumps(delivery.payload, sort_keys=True).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Tokenpricing-Delivery": delivery.id,
        "X-Tokenpricing-Event": str(
            delivery.payload.get("event", {}).get("type", "unknown")
        ),
        "X-Tokenpricing-Timestamp": timestamp,
        "X-Tokenpricing-Signature": sign_payload(secret, timestamp, body),
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.post(
                str(delivery.webhook_url), content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            return DeliveryAttemptResult(success=False, error=str(exc))
    if 200 <= response.status_code < 300:
        return DeliveryAttemptResult(success=True, status_code=response.status_code)
    return DeliveryAttemptResult(
        success=False,
        status_code=response.status_code,
        error=_truncate_error(response.text or response.reason_phrase),
    )


def next_retry_time(now: datetime, attempt_number: int) -> datetime:
    delay = RETRY_DELAYS[min(attempt_number, len(RETRY_DELAYS) - 1)]
    return now + timedelta(seconds=delay)


def _truncate_error(message: str | None) -> str | None:
    if message is None or len(message) <= MAX_ERROR_LENGTH:
        return message
    return f"{message[:MAX_ERROR_LENGTH]}..."
