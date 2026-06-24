import argparse
import asyncio

from parsers.wildberries.config import load_config
from parsers.wildberries.logging import configure_logging
from parsers.wildberries.pipeline import run_crawl, run_search_backfill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wildberries-parser")
    subparsers = parser.add_subparsers(dest="command", required=True)
    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--mode", choices=["full", "incremental", "resume", "test"], default="test")
    crawl.add_argument("--limit", type=int, default=None)
    crawl.add_argument("--category-limit", type=int, default=None)
    crawl.add_argument("--resume", action="store_true")
    crawl.add_argument("--dry-run", action="store_true")
    crawl.add_argument("--log-level", default="INFO")
    backfill_search = subparsers.add_parser("backfill-search")
    backfill_search.add_argument("queries", nargs="+")
    backfill_search.add_argument("--limit", type=int, default=100)
    backfill_search.add_argument("--dry-run", action="store_true")
    backfill_search.add_argument("--log-level", default="INFO")
    return parser


async def async_main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.log_level)
    config = load_config()
    if args.command == "crawl":
        limit = args.limit
        category_limit = args.category_limit
        if args.mode == "test":
            limit = 100 if limit is None else limit
            category_limit = 50 if category_limit is None else category_limit
        stats = await run_crawl(
            config=config,
            mode=args.mode,
            limit=limit,
            resume=args.resume or args.mode == "resume",
            dry_run=args.dry_run,
            category_limit=category_limit,
        )
    elif args.command == "backfill-search":
        stats = await run_search_backfill(
            config=config,
            queries=args.queries,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    print(stats)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
