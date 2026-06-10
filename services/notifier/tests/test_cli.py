from __future__ import annotations

import argparse
import asyncio
import builtins
from pathlib import Path

import pytest

from notifier import cli
from notifier.api import DEFAULT_DB_PATH


class DummyResult:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def model_dump_json(self, indent: int = 2) -> str:
        return self.payload


def test_build_parser_uses_home_directory_default_db_path() -> None:
    args = cli.build_parser().parse_args(["serve"])

    assert args.db_path == str(DEFAULT_DB_PATH)
    assert DEFAULT_DB_PATH == Path.home() / ".tokenpricing" / "notifier.db"


@pytest.mark.asyncio
async def test_run_worker_command_recovers_after_cycle_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeService:
        def __init__(self) -> None:
            self.sync_calls = 0
            self.flush_calls = 0

        async def sync_once(self, *, force_refresh: bool = False) -> DummyResult:
            self.sync_calls += 1
            if self.sync_calls == 1:
                raise RuntimeError("temporary failure")
            return DummyResult('{"snapshot_id": 1}')

        async def flush_deliveries(self) -> DummyResult:
            self.flush_calls += 1
            return DummyResult('{"attempted": 0}')

    service = FakeService()
    sleep_calls = 0

    def fake_service_factory(path):
        return service

    async def fake_sleep(interval: int) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(cli, "NotifierService", fake_service_factory)
    monkeypatch.setattr(cli.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(builtins, "print", lambda *_args, **_kwargs: None)

    args = argparse.Namespace(
        db_path=str(tmp_path / "notifier.db"),
        poll_interval=1,
        force_refresh=False,
    )

    with pytest.raises(asyncio.CancelledError):
        await cli.run_worker_command(args)

    assert service.sync_calls == 2
    assert service.flush_calls == 1
