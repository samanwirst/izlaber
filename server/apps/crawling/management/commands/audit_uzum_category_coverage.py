import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.catalog.models import Category, Marketplace, Product


class Command(BaseCommand):
    help = "Compare Uzum live category totals collected by the parser with stored products."

    def add_arguments(self, parser):
        parser.add_argument("coverage_file", type=Path)
        parser.add_argument("--marketplace", default="uzum")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--min-gap", type=int, default=1)
        parser.add_argument("--fail-on-gaps", action="store_true")
        parser.add_argument(
            "--write-parser-shards",
            type=Path,
            help="Write shard .env files with UZUM_DISCOVERY_START_URLS for gap backfills.",
        )
        parser.add_argument("--shards", type=int, default=4)
        parser.add_argument(
            "--shard-state-prefix",
            default=".parser_state/uzum_market/shards/shard",
            help="Prefix for generated UZUM_STATE_DIR values, e.g. PREFIX01-state.",
        )
        parser.add_argument(
            "--exclude-processed-state",
            action="append",
            type=Path,
            default=[],
            help="Checkpoint file or directory whose processed_category_urls should be skipped.",
        )

    def handle(self, *args, **options):
        report = _coverage_report(
            coverage_file=options["coverage_file"],
            marketplace_code=options["marketplace"],
            min_gap=max(0, options["min_gap"]),
        )
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            self._write_human_report(report, limit=max(1, options["limit"]))

        if options["write_parser_shards"]:
            shard_report = _write_parser_shards(
                report["gaps"],
                output_dir=options["write_parser_shards"],
                shard_count=max(1, options["shards"]),
                state_prefix=options["shard_state_prefix"],
                exclude_paths=options["exclude_processed_state"],
            )
            self.stdout.write(
                "  parser shards: "
                f"{shard_report['shards']} files, "
                f"{shard_report['categories']} categories, "
                f"{shard_report['gap_total']} gap"
            )

        if options["fail_on_gaps"] and report["gap_categories"]:
            raise CommandError(f"{report['gap_categories']} categories have coverage gaps.")

    def _write_human_report(self, report: dict, *, limit: int) -> None:
        self.stdout.write("Uzum category coverage")
        self.stdout.write(
            "  categories: "
            f"{report['categories']} checked, "
            f"{report['matched_categories']} matched in DB, "
            f"{report['missing_categories']} missing in DB"
        )
        self.stdout.write(
            "  products: "
            f"{report['live_total']} live total, "
            f"{report['stored_active']} stored active, "
            f"{report['gap_total']} gap"
        )
        self.stdout.write(
            "  note: category totals are not unique product counts; "
            "Uzum can return the same product through multiple categories/segments."
        )
        self.stdout.write(f"  gap categories: {report['gap_categories']}")
        for row in report["gaps"][:limit]:
            self.stdout.write(
                "  "
                f"gap={row['gap']} live={row['live_total']} stored={row['stored_active']} "
                f"id={row['category_id']} title={row['title'] or row['stored_name']} "
                f"url={row['url']}"
            )


def _coverage_report(
    *,
    coverage_file: Path,
    marketplace_code: str,
    min_gap: int,
) -> dict:
    if not coverage_file.exists():
        raise CommandError(f"Coverage file does not exist: {coverage_file}")
    payload = json.loads(coverage_file.read_text())
    categories = payload.get("categories")
    if not isinstance(categories, list):
        raise CommandError("Coverage file must contain a categories list.")

    marketplace = Marketplace.objects.filter(code=marketplace_code).first()
    if marketplace is None:
        raise CommandError(f"Marketplace {marketplace_code!r} does not exist.")

    by_source_id = {
        str(category.source_category_id): category
        for category in Category.objects.filter(
            marketplace=marketplace,
            source_category_id__isnull=False,
        )
    }
    active_counts = {
        category_id: count
        for category_id, count in Product.objects.filter(
            marketplace=marketplace,
            is_active=True,
            category_id__isnull=False,
        )
        .values_list("category_id")
        .annotate(count=Count("id"))
    }
    rows = []
    missing_categories = 0
    matched_categories = 0
    live_total = 0
    stored_active = 0

    for category_row in categories:
        if not isinstance(category_row, dict):
            continue
        category_id = str(category_row.get("category_id") or "")
        live_count = int(category_row.get("total") or 0)
        live_total += live_count
        category = by_source_id.get(category_id)
        if category is None:
            missing_categories += 1
            active_count = 0
            stored_name = ""
        else:
            matched_categories += 1
            stored_name = category.path_text or category.name
            active_count = active_counts.get(category.id, 0)
        stored_active += active_count
        gap = max(0, live_count - active_count)
        rows.append(
            {
                "category_id": category_id,
                "title": category_row.get("title") or "",
                "stored_name": stored_name,
                "url": category_row.get("url") or "",
                "live_total": live_count,
                "stored_active": active_count,
                "gap": gap,
                "error": category_row.get("error"),
            }
        )

    gaps = [
        row
        for row in sorted(rows, key=lambda value: value["gap"], reverse=True)
        if row["gap"] >= min_gap
    ]
    return {
        "coverage_file": str(coverage_file),
        "generated_at": payload.get("generated_at"),
        "categories": len(rows),
        "matched_categories": matched_categories,
        "missing_categories": missing_categories,
        "live_total": live_total,
        "stored_active": stored_active,
        "gap_total": sum(row["gap"] for row in rows),
        "gap_categories": len(gaps),
        "coverage_note": (
            "Category totals are not unique product counts; products can be returned "
            "through multiple categories or search segments while the database stores "
            "one category per product."
        ),
        "gaps": gaps,
    }


def _write_parser_shards(
    gaps: list[dict],
    *,
    output_dir: Path,
    shard_count: int,
    state_prefix: str,
    exclude_paths: list[Path],
) -> dict:
    processed_urls = _load_processed_category_urls(exclude_paths)
    shardable_gaps = [
        row
        for row in gaps
        if row.get("url") and row.get("url") not in processed_urls and row.get("gap", 0) > 0
    ]
    shards = [{"gap": 0, "items": []} for _ in range(shard_count)]
    for row in shardable_gaps:
        shard = min(shards, key=lambda value: value["gap"])
        shard["items"].append(row)
        shard["gap"] += int(row["gap"])

    output_dir.mkdir(parents=True, exist_ok=True)
    for index, shard in enumerate(shards, start=1):
        urls = ",".join(str(row["url"]) for row in shard["items"])
        env_path = output_dir / f"shard{index:02d}.env"
        env_path.write_text(
            f"UZUM_STATE_DIR={state_prefix}{index:02d}-state\n"
            f"UZUM_DISCOVERY_START_URLS={urls}\n"
        )

    return {
        "shards": shard_count,
        "categories": len(shardable_gaps),
        "gap_total": sum(int(row["gap"]) for row in shardable_gaps),
        "excluded_processed_categories": len(processed_urls),
    }


def _load_processed_category_urls(paths: list[Path]) -> set[str]:
    processed_urls: set[str] = set()
    for path in paths:
        checkpoint_paths = _checkpoint_paths(path)
        for checkpoint_path in checkpoint_paths:
            try:
                payload = json.loads(checkpoint_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            urls = payload.get("processed_category_urls")
            if isinstance(urls, list):
                processed_urls.update(str(url) for url in urls if url)
    return processed_urls


def _checkpoint_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("**/checkpoint.json"))
    return []
