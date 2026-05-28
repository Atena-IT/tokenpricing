from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import uvicorn

from notifier.api import DEFAULT_DB_PATH, create_app
from notifier.service import NotifierService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tokenpricing notifier service")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="serve the management API")
    serve.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    sync = subparsers.add_parser("sync", help="run one polling cycle")
    sync.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    sync.add_argument("--force-refresh", action="store_true")
    sync.add_argument("--deliver", action="store_true")

    worker = subparsers.add_parser("worker", help="run the poller loop")
    worker.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    worker.add_argument("--poll-interval", type=int, default=6 * 60 * 60)
    worker.add_argument("--force-refresh", action="store_true")

    return parser


async def run_sync_command(args: argparse.Namespace) -> None:
    service = NotifierService(Path(args.db_path))
    result = await service.sync_once(force_refresh=args.force_refresh)
    print(result.model_dump_json(indent=2))
    if args.deliver:
        flush = await service.flush_deliveries()
        print(flush.model_dump_json(indent=2))


async def run_worker_command(args: argparse.Namespace) -> None:
    service = NotifierService(Path(args.db_path))
    while True:
        result = await service.sync_once(force_refresh=args.force_refresh)
        print(result.model_dump_json(indent=2))
        flush = await service.flush_deliveries()
        print(flush.model_dump_json(indent=2))
        await asyncio.sleep(args.poll_interval)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        app = create_app(db_path=Path(args.db_path))
        uvicorn.run(app, host=args.host, port=args.port)
        return
    if args.command == "sync":
        asyncio.run(run_sync_command(args))
        return
    if args.command == "worker":
        asyncio.run(run_worker_command(args))
        return
    parser.error("unknown command")
