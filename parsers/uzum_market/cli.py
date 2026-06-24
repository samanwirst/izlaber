import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

from parsers.uzum_market.config import load_config
from parsers.uzum_market.logging import configure_logging
from parsers.uzum_market.pipeline import (
    run_category_coverage,
    run_crawl,
    run_search_backfill,
    run_search_backfill_worker,
    run_url_backfill,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uzum-market-parser")
    subparsers = parser.add_subparsers(dest="command", required=True)
    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--mode", choices=["full", "incremental", "resume", "test"], default="test")
    crawl.add_argument("--limit", type=int, default=None)
    crawl.add_argument("--resume", action="store_true")
    crawl.add_argument("--dry-run", action="store_true")
    crawl.add_argument("--headful", action="store_true")
    crawl.add_argument("--log-level", default="INFO")
    backfill_search = subparsers.add_parser("backfill-search")
    backfill_search.add_argument("queries", nargs="+")
    backfill_search.add_argument("--limit", type=int, default=100)
    backfill_search.add_argument("--dry-run", action="store_true")
    backfill_search.add_argument("--headful", action="store_true")
    backfill_search.add_argument("--log-level", default="INFO")
    backfill_worker = subparsers.add_parser("backfill-worker")
    backfill_worker.add_argument("--poll-interval", type=float, default=3.0)
    backfill_worker.add_argument("--limit", type=int, default=30)
    backfill_worker.add_argument("--once", action="store_true")
    backfill_worker.add_argument("--worker-id", default=None)
    backfill_worker.add_argument("--headful", action="store_true")
    backfill_worker.add_argument("--log-level", default="INFO")
    backfill_urls = subparsers.add_parser("backfill-urls")
    backfill_urls.add_argument("urls", nargs="*")
    backfill_urls.add_argument("--url-file", type=Path, default=None)
    backfill_urls.add_argument("--limit", type=int, default=None)
    backfill_urls.add_argument("--dry-run", action="store_true")
    backfill_urls.add_argument("--headful", action="store_true")
    backfill_urls.add_argument("--log-level", default="INFO")
    coverage = subparsers.add_parser("coverage")
    coverage.add_argument("--limit", type=int, default=None)
    coverage.add_argument(
        "--output",
        type=Path,
        default=Path(".parser_state/uzum_market/category-coverage.json"),
    )
    coverage.add_argument("--headful", action="store_true")
    coverage.add_argument("--log-level", default="INFO")
    return parser


async def async_main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.log_level)
    config = load_config()
    if args.headful:
        config = replace(config, browser_headless=False)
    if args.command == "crawl":
        limit = args.limit
        if args.mode == "test" and limit is None:
            limit = 100
        stats = await run_crawl(
            config=config,
            mode=args.mode,
            limit=limit,
            resume=args.resume or args.mode == "resume",
            dry_run=args.dry_run,
        )
        print(stats)
    elif args.command == "backfill-search":
        stats = await run_search_backfill(
            config=config,
            queries=args.queries,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        print(stats)
    elif args.command == "backfill-worker":
        stats = await run_search_backfill_worker(
            config=config,
            poll_interval_seconds=args.poll_interval,
            once=args.once,
            limit=args.limit,
            worker_id=args.worker_id,
        )
        print(stats)
    elif args.command == "backfill-urls":
        stats = await run_url_backfill(
            config=config,
            urls=args.urls,
            url_file=args.url_file,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        print(stats)
    elif args.command == "coverage":
        stats = await run_category_coverage(
            config=config,
            limit=args.limit,
            output_path=args.output,
        )
        print(stats)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
