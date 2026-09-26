"""Failure and drift alerting for the Artificial Analysis sync.

Three failure modes are worth waking someone for, and they are kept distinct
because each has a different remedy. An alert that says "sync failed" tells you
nothing; these name the failure:

``payload-not-found``
    AA no longer ships page data as a flight payload in the initial HTML. The
    acquisition strategy itself needs revisiting.
``request-blocked``
    The page could not be retrieved after retries -- a 403, a persistent 5xx, or a
    transport failure. Nothing to fix in this repo; check whether we are blocked.
``schema-drift``
    The payload parsed, but a field vanished, changed type, or changed units. The
    projection in ``parse.py`` needs updating before the data can be trusted.

Delivery is deliberately one function. ``deliver_via_github_issue`` is the default
because it reaches no external service and needs no account decisions: it opens (or
comments on) an issue in this repository. To route alerts somewhere else -- Teams,
email, PagerDuty -- write a function with the same ``(Alert) -> str`` shape and pass
it as ``delivery`` to ``send_alert``, or change the default below. No other module
knows how alerts are delivered.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ISSUE_LABEL = "aa-sync-failure"
GITHUB_API = "https://api.github.com"


class AlertKind(str, Enum):
    PAYLOAD_NOT_FOUND = "payload-not-found"
    REQUEST_BLOCKED = "request-blocked"
    SCHEMA_DRIFT = "schema-drift"


@dataclass
class Alert:
    kind: AlertKind
    subject: str
    """What the failure was about (a URL, a dataset name) -- part of the identity."""
    detail: str
    body: str

    @property
    def title(self) -> str:
        """Stable, human-readable, and unique per (kind, subject).

        Deduplication matches on this exact string, so it must not embed anything
        that changes run to run -- no timestamps, no counts.
        """
        return f"[aa-sync] {self.kind.value}: {self.subject}"


def _run_context() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if repo and run_id:
        return f"\n\nRun: {server}/{repo}/actions/runs/{run_id}"
    return ""


def payload_not_found_alert(url: str, error: Exception) -> Alert:
    detail = str(error)
    body = (
        f"The flight payload could not be extracted from `{url}`.\n\n"
        f"```\n{detail}\n```\n\n"
        "This service reads AA's data from the `self.__next_f.push([1,...])` chunks "
        "in the initial HTML document. This error means those chunks are gone, "
        "renamed, or no longer decodable -- most likely AA changed how the page "
        "ships its data (client-side fetch, different bundler, different "
        "serialisation).\n\n"
        "**What to check:** fetch the page manually and look for the chunk calls. If "
        "they are gone, the acquisition strategy in `flight.py` needs rethinking; "
        "the raw capture is attached to the failing workflow run."
        + _run_context()
    )
    return Alert(AlertKind.PAYLOAD_NOT_FOUND, url, detail, body)


def request_blocked_alert(url: str, error: Exception) -> Alert:
    detail = str(error)
    status = getattr(error, "status", None)
    attempts = getattr(error, "attempts", None)
    history = getattr(error, "history", None) or []
    body = (
        f"`{url}` could not be retrieved.\n\n"
        f"- Final status: **{status if status is not None else 'transport failure'}**\n"
        f"- Attempts: {attempts}\n"
        + ("- History:\n" + "".join(f"  - {h}\n" for h in history) if history else "")
        + "\nRetries with backoff already ran, so this is not a transient blip. A 403 "
        "or 451 means we are being refused and no code change here will help; a "
        "persistent 5xx means AA is down.\n\n"
        f"```\n{detail}\n```" + _run_context()
    )
    return Alert(AlertKind.REQUEST_BLOCKED, url, detail, body)


def schema_drift_alert(subject: str, report: Any) -> Alert:
    lines = []
    for label, items in (
        ("Missing / entirely null", report.missing),
        ("Type changed", report.type_changed),
        ("Range shifted (possible unit change)", report.range_shifted),
    ):
        if items:
            lines.append(f"**{label}**\n" + "".join(f"- `{i}`\n" for i in sorted(items)))
    if report.new:
        lines.append(
            "**New fields (informational, not a failure)**\n"
            + "".join(f"- `{i}`\n" for i in sorted(report.new))
        )
    body = (
        f"The `{subject}` payload parsed successfully but no longer matches "
        f"`schema/offering-manifest.json` over {report.record_count} records.\n\n"
        + "\n".join(lines)
        + "\nA field disappearing or changing type breaks the columns built from it. "
        "A shifted numeric range usually means the *units* changed -- fractions "
        "rescaled to percentages, per-1M prices restated per-1k -- which parses "
        "cleanly and silently corrupts everything downstream.\n\n"
        "**What to check:** compare against the manifest, update the projection in "
        "`parse.py` if the change is real, then regenerate the manifest with "
        "`uv run tokenpricing-aa-sync build-manifest`." + _run_context()
    )
    return Alert(AlertKind.SCHEMA_DRIFT, subject, report.summary(), body)


# --------------------------------------------------------------------------- #
# Delivery. Swap this one function to change the channel.
# --------------------------------------------------------------------------- #


def deliver_via_github_issue(
    alert: Alert,
    *,
    repo: str | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Open an issue for ``alert``, or comment on the open one that matches it.

    Deduplication is by exact issue title among open issues carrying
    ``aa-sync-failure``, so a failure that persists for weeks accumulates comments
    on one issue instead of opening a new issue every run.
    """
    repo = repo or os.environ.get("GITHUB_REPOSITORY") or ""
    token = token or os.environ.get("GITHUB_TOKEN") or ""
    if not repo or not token:
        logger.error(
            "no GITHUB_REPOSITORY/GITHUB_TOKEN; alert not delivered:\n%s\n\n%s",
            alert.title,
            alert.body,
        )
        return "undelivered: missing GITHUB_REPOSITORY or GITHUB_TOKEN"

    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        existing = http.get(
            f"{GITHUB_API}/repos/{repo}/issues",
            params={"state": "open", "labels": ISSUE_LABEL, "per_page": 100},
            headers=headers,
        )
        existing.raise_for_status()
        match = next(
            (
                issue
                for issue in existing.json()
                if issue.get("title") == alert.title
            ),
            None,
        )

        if match is not None:
            number = match["number"]
            response = http.post(
                f"{GITHUB_API}/repos/{repo}/issues/{number}/comments",
                json={"body": f"Still failing.\n\n{alert.body}"},
                headers=headers,
            )
            response.raise_for_status()
            return f"commented on #{number}"

        response = http.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            json={
                "title": alert.title,
                "body": alert.body,
                "labels": [ISSUE_LABEL],
            },
            headers=headers,
        )
        response.raise_for_status()
        return f"opened #{response.json().get('number')}"
    finally:
        if owns_client:
            http.close()


Delivery = Callable[[Alert], str]

DEFAULT_DELIVERY: Delivery = deliver_via_github_issue


def send_alert(alert: Alert, delivery: Delivery | None = None) -> str:
    """Deliver ``alert``, logging it regardless of whether delivery succeeds.

    Never raises: an alerting failure must not mask the failure being alerted on.
    """
    logger.error("ALERT %s -- %s", alert.title, alert.detail)
    try:
        outcome = (delivery or DEFAULT_DELIVERY)(alert)
    except Exception as exc:
        logger.exception("alert delivery failed")
        return f"delivery failed: {exc}"
    logger.info("alert delivered: %s", outcome)
    return outcome
