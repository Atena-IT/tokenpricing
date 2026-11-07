"""Each of the three failure modes must produce its own named alert.

These drive the real code paths against deliberately broken inputs -- a page with
no payload, an HTTP transport that refuses, a payload whose shape moved -- and
assert on what actually gets delivered. Delivery itself is injected, so no test
touches the network or opens an issue.
"""

from __future__ import annotations

import httpx
import pytest

from tests.factories import leaderboard_page, offering, openness_page
from tokenpricing_aa import cli
from tokenpricing_aa.alerting import (
    Alert,
    AlertKind,
    deliver_via_github_issue,
    payload_not_found_alert,
    request_blocked_alert,
    schema_drift_alert,
    send_alert,
)
from tokenpricing_aa.fetch import FetchBlockedError, get_page
from tokenpricing_aa.flight import PayloadNotFoundError
from tokenpricing_aa.normalize import ShapeError
from tokenpricing_aa.schema import DriftReport, FieldSpec, build_manifest, check_drift


class Recorder:
    """A delivery channel that records instead of sending."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def __call__(self, alert: Alert) -> str:
        self.alerts.append(alert)
        return "recorded"

    @property
    def kinds(self) -> list[str]:
        return [a.kind.value for a in self.alerts]


def _capture(page: str, url: str = "https://artificialanalysis.ai/leaderboards/providers"):
    return {"source_url": url, "fetched_at": "2026-08-14T00:00:00+00:00", "page": page}


# --------------------------------------------------------------------------- #
# Failure mode 1: the payload cannot be found
# --------------------------------------------------------------------------- #


def test_payload_not_found_alert_names_the_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CURRENT_DATABASE_DIR", tmp_path / "current")
    monkeypatch.setattr(cli, "HISTORY_DIR", tmp_path / "history")
    recorder = Recorder()

    broken = _capture("<html><body>no payload here at all</body></html>")
    with pytest.raises(PayloadNotFoundError):
        cli._build(broken, _capture(openness_page()), recorder)

    assert recorder.kinds == ["payload-not-found"]
    alert = recorder.alerts[0]
    assert alert.title.startswith("[aa-sync] payload-not-found:")
    assert "self.__next_f.push" in alert.body
    assert "flight payload could not be extracted" in alert.body


def test_payload_not_found_alert_does_not_publish_anything(tmp_path, monkeypatch):
    current = tmp_path / "current"
    monkeypatch.setattr(cli, "CURRENT_DATABASE_DIR", current)
    monkeypatch.setattr(cli, "HISTORY_DIR", tmp_path / "history")
    with pytest.raises(PayloadNotFoundError):
        cli._build(_capture("<html></html>"), _capture(openness_page()), Recorder())
    assert not list(tmp_path.glob("**/*.json"))


def test_payload_not_found_alert_body_explains_the_remedy():
    alert = payload_not_found_alert("https://x/y", RuntimeError("no chunks"))
    assert alert.kind is AlertKind.PAYLOAD_NOT_FOUND
    assert "acquisition strategy" in alert.body


# --------------------------------------------------------------------------- #
# Failure mode 2: the request is blocked
# --------------------------------------------------------------------------- #


def test_forbidden_is_not_retried_and_raises_blocked():
    attempts = []

    def handler(request):
        attempts.append(request.url)
        return httpx.Response(403, text="forbidden")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FetchBlockedError) as exc:
        get_page("https://artificialanalysis.ai/x", client=client, sleep=lambda _: None)

    assert exc.value.status == 403
    assert len(attempts) == 1, "a refusal must not be retried"


def test_transient_5xx_is_retried_then_succeeds():
    statuses = [503, 503, 200]

    def handler(request):
        code = statuses.pop(0)
        return httpx.Response(code, text="<html>ok</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert (
        get_page("https://artificialanalysis.ai/x", client=client, sleep=lambda _: None)
        == "<html>ok</html>"
    )
    assert statuses == []


def test_persistent_5xx_exhausts_retries_then_raises_blocked():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FetchBlockedError) as exc:
        get_page("https://artificialanalysis.ai/x", client=client, sleep=lambda _: None)

    assert exc.value.status == 503
    assert len(calls) > 1, "a transient status must be retried before alerting"
    assert "retryable status persisted" in str(exc.value)


def test_transport_failure_is_retried_then_raises_blocked():
    def handler(request):
        raise httpx.ConnectError("no route to host")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FetchBlockedError) as exc:
        get_page("https://artificialanalysis.ai/x", client=client, sleep=lambda _: None)
    assert exc.value.status is None


def test_blocked_alert_carries_the_status_and_attempt_history():
    error = FetchBlockedError(
        "https://artificialanalysis.ai/leaderboards/providers",
        403,
        1,
        ["attempt 1: HTTP 403"],
        "not a retryable status",
    )
    alert = request_blocked_alert(error.url, error)
    assert alert.kind is AlertKind.REQUEST_BLOCKED
    assert "**403**" in alert.body
    assert "attempt 1: HTTP 403" in alert.body
    assert "not a transient blip" in alert.body


def test_sync_alerts_on_blocked_fetch(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "CURRENT_DATABASE_DIR", tmp_path / "current")
    monkeypatch.setattr(cli, "HISTORY_DIR", tmp_path / "history")
    monkeypatch.setattr(cli, "RAW_CAPTURE_DIR", tmp_path / "capture")

    def blocked():
        raise FetchBlockedError("https://artificialanalysis.ai/x", 403, 1, ["attempt 1: HTTP 403"])

    monkeypatch.setattr(cli, "fetch_leaderboard", blocked)
    recorder = Recorder()
    with pytest.raises(FetchBlockedError):
        cli.sync(recorder)
    assert recorder.kinds == ["request-blocked"]


# --------------------------------------------------------------------------- #
# Failure mode 3: schema drift
# --------------------------------------------------------------------------- #


def _specs(objects):
    return {p: FieldSpec.from_json(s) for p, s in build_manifest(objects)["fields"].items()}


def test_schema_drift_alert_lists_the_offending_fields():
    baseline = [offering(id=f"id-{i}") for i in range(5)]
    broken = [
        offering(id=f"id-{i}", features={"contextWindowTokens": "262k"}) for i in range(5)
    ]
    report = check_drift(broken, _specs(baseline))
    alert = schema_drift_alert("artificial-analysis", report)

    assert alert.kind is AlertKind.SCHEMA_DRIFT
    assert alert.title == "[aa-sync] schema-drift: artificial-analysis"
    assert "features.contextWindowTokens" in alert.body
    assert "Type changed" in alert.body


def test_schema_drift_alert_explains_a_unit_change():
    baseline = [offering(id=f"id-{i}", model={"gpqa": 0.5}) for i in range(5)]
    live = [offering(id=f"id-{i}", model={"gpqa": 50.0}) for i in range(5)]
    report = check_drift(live, _specs(baseline))
    alert = schema_drift_alert("artificial-analysis", report)
    assert "Range shifted" in alert.body
    assert "units" in alert.body


def test_build_alerts_on_drift_and_publishes_nothing(tmp_path, monkeypatch):
    """A payload that parses fine but moved must not reach database/."""
    current = tmp_path / "current"
    monkeypatch.setattr(cli, "CURRENT_DATABASE_DIR", current)
    monkeypatch.setattr(cli, "HISTORY_DIR", tmp_path / "history")

    # Drift the live payload against the real checked-in manifest: prices per 1k.
    drifted = [
        offering(id=f"id-{i}", pricing={"price1mInputTokens": 950000.0})
        for i in range(5)
    ]
    recorder = Recorder()
    with pytest.raises(cli.DriftError):
        cli._build(_capture(leaderboard_page(drifted)), _capture(openness_page()), recorder)

    assert recorder.kinds == ["schema-drift"]
    assert not list(tmp_path.glob("**/*.json"))


def test_new_field_alone_does_not_alert_or_block(tmp_path, monkeypatch):
    """AA ships new benchmarks constantly; that must never page anyone."""
    monkeypatch.setattr(cli, "CURRENT_DATABASE_DIR", tmp_path / "current")
    monkeypatch.setattr(cli, "HISTORY_DIR", tmp_path / "history")
    # Isolate the additive case from the checked-in manifest, which a handful of
    # stub offerings cannot satisfy on sparsely-scored benchmarks.
    monkeypatch.setattr(
        cli,
        "check_drift",
        lambda _objects: DriftReport(record_count=3, new=["model.brandNewBench2027"]),
    )
    recorder = Recorder()

    additive = [offering(id=f"id-{i}", model={"brandNewBench2027": 0.4}) for i in range(3)]
    # The shape guard still rejects a 3-row capture -- but for its own reason, and
    # without an alert for the additive field.
    with pytest.raises(ShapeError, match="expected >="):
        cli._build(_capture(leaderboard_page(additive)), _capture(openness_page()), recorder)

    assert recorder.alerts == []


# --------------------------------------------------------------------------- #
# Delivery: dedupe behaviour, and the swappable seam
# --------------------------------------------------------------------------- #


def test_github_delivery_opens_an_issue_when_none_is_open():
    posted = {}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[])
        posted["url"] = str(request.url)
        return httpx.Response(201, json={"number": 91})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    alert = payload_not_found_alert("https://x/y", RuntimeError("boom"))
    outcome = deliver_via_github_issue(
        alert, repo="Atena-IT/tokenpricing", token="t", client=client
    )
    assert outcome == "opened #91"
    assert posted["url"].endswith("/repos/Atena-IT/tokenpricing/issues")


def test_github_delivery_comments_instead_of_duplicating():
    alert = payload_not_found_alert("https://x/y", RuntimeError("boom"))
    seen = {}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"number": 42, "title": alert.title}])
        seen["url"] = str(request.url)
        return httpx.Response(201, json={"id": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    outcome = deliver_via_github_issue(
        alert, repo="Atena-IT/tokenpricing", token="t", client=client
    )
    assert outcome == "commented on #42"
    assert seen["url"].endswith("/issues/42/comments")


def test_a_different_failure_mode_opens_its_own_issue():
    """Dedupe is per (kind, subject), so two distinct failures do not collapse."""
    drift = payload_not_found_alert("https://x/y", RuntimeError("boom"))
    other = request_blocked_alert("https://x/y", FetchBlockedError("https://x/y", 403, 1, []))
    assert drift.title != other.title

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"number": 42, "title": drift.title}])
        return httpx.Response(201, json={"number": 43})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert (
        deliver_via_github_issue(other, repo="a/b", token="t", client=client)
        == "opened #43"
    )


def test_titles_are_stable_across_runs():
    """Dedupe matches on the title, so it must not carry run-specific detail."""
    first = request_blocked_alert("https://x/y", FetchBlockedError("https://x/y", 403, 1, ["a"]))
    second = request_blocked_alert("https://x/y", FetchBlockedError("https://x/y", 403, 4, ["b"]))
    assert first.title == second.title


def test_delivery_without_credentials_reports_undelivered_rather_than_raising(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    alert = payload_not_found_alert("https://x/y", RuntimeError("boom"))
    assert "undelivered" in deliver_via_github_issue(alert)


def test_send_alert_never_raises_when_delivery_fails():
    """An alerting failure must not mask the failure being alerted on."""

    def broken(_alert):
        raise RuntimeError("channel down")

    alert = payload_not_found_alert("https://x/y", RuntimeError("boom"))
    assert "delivery failed" in send_alert(alert, broken)


def test_delivery_is_a_single_swappable_function():
    """Documents the seam: any (Alert) -> str callable is a channel."""
    sent: list[str] = []
    assert send_alert(
        payload_not_found_alert("https://x/y", RuntimeError("boom")),
        lambda alert: sent.append(alert.title) or "sent to teams",
    ) == "sent to teams"
    assert sent == ["[aa-sync] payload-not-found: https://x/y"]
