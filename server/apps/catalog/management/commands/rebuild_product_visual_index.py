from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.visual_index import index_product_cover_rows, visual_index_queryset


class Command(BaseCommand):
    help = "Build visual fingerprints for product cover images."

    def add_arguments(self, parser):
        parser.add_argument("--marketplace", default="uzum")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--concurrency", type=int, default=16)
        parser.add_argument("--timeout", type=float, default=12.0)
        parser.add_argument("--force", action="store_true")
        parser.add_argument(
            "--product-id",
            action="append",
            type=int,
            default=[],
            help="Index a specific internal product id. Can be passed multiple times.",
        )
        parser.add_argument(
            "--source-product-id",
            action="append",
            default=[],
            help="Index a specific marketplace product id. Can be passed multiple times.",
        )

    def handle(self, *args, **options):
        marketplace = options["marketplace"]
        limit = max(0, options["limit"])
        batch_size = max(1, options["batch_size"])
        concurrency = max(1, options["concurrency"])
        timeout = max(1.0, options["timeout"])
        force = options["force"]
        product_ids = options["product_id"]
        source_product_ids = options["source_product_id"]

        queryset = visual_index_queryset(
            marketplace_code=marketplace,
            force=force,
            product_ids=product_ids,
            source_product_ids=source_product_ids,
        ).values_list("id", "cover_image_url")

        processed = 0
        updated = 0
        failed = 0
        last_id = 0
        while True:
            remaining = limit - processed if limit else batch_size
            if remaining <= 0:
                break
            batch = list(queryset.filter(id__gt=last_id)[: min(batch_size, remaining)])
            if not batch:
                break
            last_id = batch[-1][0]
            stats = index_product_cover_rows(
                rows=batch,
                concurrency=concurrency,
                timeout=timeout,
            )
            updated += stats.updated
            failed += stats.failed
            processed += stats.processed
            self.stdout.write(
                f"Processed={processed} updated={updated} failed={failed}",
                ending="\r",
            )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Visual index complete: processed={processed}, updated={updated}, failed={failed}"
            )
        )
