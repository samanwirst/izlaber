import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.crawling.audit import audit_uzum_catalog


class Command(BaseCommand):
    help = "Audit Uzum catalog crawl completeness and product data quality."

    def add_arguments(self, parser):
        parser.add_argument("--marketplace", default="uzum")
        parser.add_argument("--state-file", type=Path, default=None)
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--require-checkpoint", action="store_true")

    def handle(self, *args, **options):
        report = audit_uzum_catalog(
            marketplace_code=options["marketplace"],
            state_file=options["state_file"],
            require_checkpoint=options["require_checkpoint"],
        )
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            self._write_human_report(report)

        if not report["ok"]:
            raise CommandError(
                f"Uzum catalog audit failed: {report['critical_count']} critical checks failed."
            )

    def _write_human_report(self, report: dict) -> None:
        db = report["database"]
        checkpoint = report["checkpoint"]
        latest_run = report["latest_crawl_run"] or {}
        self.stdout.write("Uzum catalog audit")
        self.stdout.write(f"  ok: {report['ok']}")
        self.stdout.write(
            "  checks: "
            f"{report['critical_count']} critical failures, "
            f"{report['warning_count']} warnings"
        )
        self.stdout.write(
            "  products: "
            f"{db['total_products']} total, "
            f"{db['active_products']} active, "
            f"{db['inactive_products']} inactive"
        )
        self.stdout.write(
            "  required fields: "
            f"{db['missing_canonical_url']} missing urls, "
            f"{db['missing_cover_image_url']} missing covers, "
            f"{db['missing_image_urls']} missing image lists"
        )
        self.stdout.write(
            "  cover quality: "
            f"{db['cover_540_high']} t_product_540_high, "
            f"{db['cover_mismatch_first_image']} mismatched first-image covers"
        )
        self.stdout.write(
            "  latest run: "
            f"id={latest_run.get('id')} "
            f"status={latest_run.get('status')} "
            f"changed={latest_run.get('metadata', {}).get('changed')}"
        )
        self.stdout.write(
            "  checkpoint: "
            f"exists={checkpoint['exists']} "
            f"processed_ids={checkpoint['processed_product_ids']} "
            f"failed={checkpoint['failed_urls']} "
            f"blocked={checkpoint['blocked_urls']}"
        )

        failed_checks = [check for check in report["checks"] if not check["passed"]]
        if failed_checks:
            self.stdout.write("  failed checks:")
            for check in failed_checks:
                self.stdout.write(
                    f"    [{check['severity']}] {check['name']}: {check['message']}"
                )
