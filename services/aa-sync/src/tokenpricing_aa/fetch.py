"""HTTP acquisition for Artificial Analysis public pages.

Data source: Artificial Analysis (https://artificialanalysis.ai).

Two GETs per run. Everything this service needs is server-rendered into the initial
HTML document of the provider leaderboard, whose flight payload carries every
offering of every provider with every field -- including the superseded offerings
its rendered table hides. There is no JSON API behind these pages, no browser is
required, and the per-provider ``/providers/<slug>`` pages add nothing: see
``flight.py`` for the measurements behind that.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

BASE_URL = "https://artificialanalysis.ai"
LEADERBOARD_URL = f"{BASE_URL}/leaderboards/providers"
OPENNESS_URL = f"{BASE_URL}/evaluations/artificial-analysis-openness-index"

REQUEST_TIMEOUT = 90.0
USER_AGENT = "tokenpricing-aa-sync/0.1.0 (https://github.com/Atena-IT/tokenpricing)"

# Two requests a week. Retries exist to ride out a transient blip, not to grind
# against a block: a 403 is returned as-is on the first attempt.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (2.0, 8.0, 30.0)

# Statuses worth a retry. Anything else is a decision by the far end, and
# repeating the request will not change it.
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

logger = logging.getLogger(__name__)


class FetchBlockedError(RuntimeError):
    """A page could not be retrieved after exhausting retries.

    Carries the evidence needed to tell a block from an outage without digging
    through logs: the final status (``None`` for a transport failure), how many
    attempts were made, and every status seen along the way.
    """

    def __init__(
        self,
        url: str,
        status: int | None,
        attempts: int,
        history: list[str],
        detail: str = "",
    ) -> None:
        self.url = url
        self.status = status
        self.attempts = attempts
        self.history = history
        self.detail = detail
        described = f"HTTP {status}" if status is not None else "transport failure"
        super().__init__(
            f"{url} unreachable after {attempts} attempt(s): {described}"
            + (f" ({detail})" if detail else "")
            + f"; attempts: {', '.join(history)}"
        )


def _client(client: httpx.Client | None = None) -> httpx.Client:
    if client is not None:
        return client
    return httpx.Client(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


def get_page(
    url: str,
    client: httpx.Client | None = None,
    sleep: Any = None,
) -> str:
    """GET ``url``, retrying only transient failures.

    Raises ``FetchBlockedError`` when the failure is persistent or is a refusal
    (403, 404, 451, ...) that retrying cannot fix.
    """
    if sleep is None:
        import time

        sleep = time.sleep

    owns_client = client is None
    http = _client(client)
    history: list[str] = []
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = http.get(url)
            except httpx.HTTPError as exc:
                history.append(f"attempt {attempt}: {type(exc).__name__}")
                if attempt == MAX_ATTEMPTS:
                    raise FetchBlockedError(
                        url, None, attempt, history, str(exc)
                    ) from exc
                sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])
                continue

            history.append(f"attempt {attempt}: HTTP {response.status_code}")
            if response.status_code == 200:
                return response.text

            if response.status_code not in RETRY_STATUSES:
                raise FetchBlockedError(
                    url,
                    response.status_code,
                    attempt,
                    history,
                    "not a retryable status",
                )

            if attempt == MAX_ATTEMPTS:
                raise FetchBlockedError(
                    url,
                    response.status_code,
                    attempt,
                    history,
                    "retryable status persisted",
                )
            logger.warning(
                "%s returned %s, retrying (attempt %s/%s)",
                url,
                response.status_code,
                attempt,
                MAX_ATTEMPTS,
            )
            sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])
    finally:
        if owns_client:
            http.close()

    raise AssertionError("unreachable")  # pragma: no cover


def fetch_leaderboard(
    client: httpx.Client | None = None, sleep: Any = None
) -> dict[str, Any]:
    """Fetch the provider leaderboard page."""
    return {
        "source": "artificial_analysis_leaderboard",
        "source_url": LEADERBOARD_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "page": get_page(LEADERBOARD_URL, client=client, sleep=sleep),
    }


def fetch_openness_page(
    client: httpx.Client | None = None, sleep: Any = None
) -> dict[str, Any]:
    """Fetch the Openness Index page."""
    return {
        "source": "artificial_analysis_openness",
        "source_url": OPENNESS_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "page": get_page(OPENNESS_URL, client=client, sleep=sleep),
    }
