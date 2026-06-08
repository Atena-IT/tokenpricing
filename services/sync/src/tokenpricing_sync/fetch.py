from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
LITELLM_RAW_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
OPENROUTER_FALLBACK_URL = "https://raw.githubusercontent.com/DiTo97/LLMTracker/main/data/current/openrouter.json"
LITELLM_FALLBACK_URL = (
    "https://raw.githubusercontent.com/DiTo97/LLMTracker/main/data/current/litellm.json"
)
REQUEST_TIMEOUT = 60.0
USER_AGENT = "tokenpricing-sync/0.1.0 (https://github.com/Atena-IT/tokenpricing)"


def _wrap_source_payload(source: str, source_url: str, data: Any) -> dict[str, Any]:
    payload = {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    if source == "openrouter" and isinstance(data, dict):
        payload["api_url"] = source_url
        payload["model_count"] = len(data.get("data", []))
        payload["data"] = data.get("data", [])
        return payload

    payload["source_url"] = source_url
    payload["model_count"] = len(data)
    payload["data"] = data
    return payload


def _fetch_json(url: str) -> Any:
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.json()


def fetch_openrouter() -> dict[str, Any]:
    try:
        payload = _fetch_json(OPENROUTER_API_URL)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("OpenRouter payload is not in the expected format")
        return _wrap_source_payload("openrouter", OPENROUTER_API_URL, payload)
    except (httpx.HTTPError, ValueError):
        fallback = _fetch_json(OPENROUTER_FALLBACK_URL)
        if not isinstance(fallback, dict) or "data" not in fallback:
            raise ValueError(
                "OpenRouter fallback payload is not in the expected format"
            )
        return fallback


def fetch_litellm() -> dict[str, Any]:
    try:
        payload = _fetch_json(LITELLM_RAW_URL)
        if not isinstance(payload, dict):
            raise ValueError("LiteLLM payload is not in the expected format")
        return _wrap_source_payload("litellm", LITELLM_RAW_URL, payload)
    except (httpx.HTTPError, ValueError):
        fallback = _fetch_json(LITELLM_FALLBACK_URL)
        if not isinstance(fallback, dict) or "data" not in fallback:
            raise ValueError("LiteLLM fallback payload is not in the expected format")
        return fallback
