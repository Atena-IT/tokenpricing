from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
LITELLM_RAW_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
REQUEST_TIMEOUT = 60.0
USER_AGENT = "tokenpricing-sync/0.1.0 (https://github.com/Atena-IT/tokenpricing)"


def _wrap_source_payload(source: str, source_url: str, data: Any) -> dict[str, Any]:
    model_count = len(data.get("data", [])) if source == "openrouter" and isinstance(data, dict) else len(data)
    return {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "model_count": model_count,
        "data": data,
    }


def fetch_openrouter() -> dict[str, Any]:
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.get(OPENROUTER_API_URL, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("OpenRouter payload is not in the expected format")
    return _wrap_source_payload("openrouter", OPENROUTER_API_URL, payload)


def fetch_litellm() -> dict[str, Any]:
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.get(LITELLM_RAW_URL, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("LiteLLM payload is not in the expected format")
    return _wrap_source_payload("litellm", LITELLM_RAW_URL, payload)
