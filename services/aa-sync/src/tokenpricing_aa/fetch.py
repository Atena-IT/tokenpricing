"""HTTP acquisition for Artificial Analysis public pages.

Data source: Artificial Analysis (https://artificialanalysis.ai).

Everything this module needs is server-rendered into the initial HTML document:
there is no JSON API behind these pages and no browser is required. The spike
(`experiments/aa-scrape-spike`) recommended Playwright, but that was only needed
to reach the *expanded* column view of the aggregate leaderboard. The per-provider
pages and the Openness Index table are fully rendered on a plain GET, so this
workload is plain HTTP.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

BASE_URL = "https://artificialanalysis.ai"
PROVIDER_INDEX_URL = f"{BASE_URL}/leaderboards/providers"
OPENNESS_URL = f"{BASE_URL}/evaluations/artificial-analysis-openness-index"
PROVIDER_PAGE_URL = f"{BASE_URL}/providers/{{slug}}"

REQUEST_TIMEOUT = 60.0
USER_AGENT = "tokenpricing-aa-sync/0.1.0 (https://github.com/Atena-IT/tokenpricing)"

# Politeness: the whole capture is ~60 requests once a week, so there is nothing to
# rate limit against. A small delay keeps us well inside any reasonable budget.
REQUEST_DELAY_SECONDS = 1.0

_PROVIDER_HREF = re.compile(r"/providers/([a-z0-9._-]+)")


def _client(client: httpx.Client | None = None) -> httpx.Client:
    if client is not None:
        return client
    return httpx.Client(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


def discover_provider_slugs(html: str) -> list[str]:
    """Extract provider slugs from the aggregate leaderboard markup.

    The leaderboard is only used for *discovery* — its rows are filtered
    (``Status: Current``) and cover roughly half of what the per-provider pages
    expose, so the row data itself is taken from the provider pages instead.

    Some discovered slugs do not resolve to a live page; callers must tolerate
    404s rather than assuming every slug is fetchable.
    """
    slugs = {
        slug
        for slug in _PROVIDER_HREF.findall(html)
        # Next.js chunk filenames land under the same prefix in the asset graph.
        if not slug.endswith(".js")
    }
    return sorted(slugs)


def fetch_provider_pages(
    client: httpx.Client | None = None,
    sleep: Any = None,
) -> dict[str, Any]:
    """Fetch the provider index plus every discoverable provider page."""
    if sleep is None:
        import time

        sleep = time.sleep

    owns_client = client is None
    http = _client(client)
    try:
        index = http.get(PROVIDER_INDEX_URL)
        index.raise_for_status()
        slugs = discover_provider_slugs(index.text)
        if not slugs:
            raise ValueError("No provider slugs discovered on the provider leaderboard")

        pages: dict[str, str] = {}
        missing: list[dict[str, Any]] = []
        for slug in slugs:
            sleep(REQUEST_DELAY_SECONDS)
            response = http.get(PROVIDER_PAGE_URL.format(slug=slug))
            if response.status_code != 200:
                missing.append({"slug": slug, "status": response.status_code})
                continue
            pages[slug] = response.text
    finally:
        if owns_client:
            http.close()

    return {
        "source": "artificial_analysis_providers",
        "source_url": PROVIDER_INDEX_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "discovered_slugs": slugs,
        "unreachable_slugs": missing,
        "pages": pages,
    }


def fetch_openness_page(client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch the Openness Index leaderboard."""
    owns_client = client is None
    http = _client(client)
    try:
        response = http.get(OPENNESS_URL)
        response.raise_for_status()
        html = response.text
    finally:
        if owns_client:
            http.close()

    return {
        "source": "artificial_analysis_openness",
        "source_url": OPENNESS_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "page": html,
    }
