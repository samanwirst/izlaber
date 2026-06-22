from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Count, Q

from apps.catalog.models import Marketplace, Product
from apps.crawling.models import CrawlRun

DEFAULT_CHECKPOINT_PATH = Path(".parser_state/uzum_market/checkpoint.json")


def audit_uzum_catalog(
    *,
    marketplace_code: str = "uzum",
    state_file: Path | None = None,
    require_checkpoint: bool = False,
) -> dict[str, Any]:
    state_file = state_file or Path(settings.ROOT_DIR) / DEFAULT_CHECKPOINT_PATH
    marketplace = Marketplace.objects.filter(code=marketplace_code).first()
    checkpoint = _read_checkpoint(state_file)
    report: dict[str, Any] = {
        "marketplace": marketplace_code,
        "database": _empty_database_metrics(),
        "latest_crawl_run": None,
        "checkpoint": checkpoint,
        "checks": [],
    }

    if marketplace is None:
        _add_check(
            report,
            name="marketplace_exists",
            severity="critical",
            passed=False,
            message=f"Marketplace {marketplace_code!r} does not exist.",
        )
        return _finalize_report(report)

    report["database"] = _database_metrics(marketplace)
    report["latest_crawl_run"] = _latest_crawl_run(marketplace)
    _add_database_checks(report)
    _add_crawl_run_checks(report)
    _add_checkpoint_checks(report, require_checkpoint=require_checkpoint)
    return _finalize_report(report)


def _empty_database_metrics() -> dict[str, Any]:
    return {
        "total_products": 0,
        "active_products": 0,
        "inactive_products": 0,
        "missing_canonical_url": 0,
        "missing_cover_image_url": 0,
        "missing_image_urls": 0,
        "cover_matches_first_image": 0,
        "cover_mismatch_first_image": 0,
        "cover_540_high": 0,
        "missing_title": 0,
        "missing_current_price": 0,
        "missing_category": 0,
        "duplicate_source_product_ids": 0,
    }


def _database_metrics(marketplace: Marketplace) -> dict[str, Any]:
    products = Product.objects.filter(marketplace=marketplace)
    metrics = _empty_database_metrics()
    metrics.update(
        {
            "total_products": products.count(),
            "active_products": products.filter(is_active=True).count(),
            "inactive_products": products.filter(is_active=False).count(),
            "missing_canonical_url": products.filter(
                Q(canonical_url__isnull=True) | Q(canonical_url="")
            ).count(),
            "missing_cover_image_url": products.filter(
                Q(cover_image_url__isnull=True) | Q(cover_image_url="")
            ).count(),
            "cover_540_high": products.filter(
                cover_image_url__contains="t_product_540_high"
            ).count(),
            "missing_title": products.filter(Q(title__isnull=True) | Q(title="")).count(),
            "missing_current_price": products.filter(current_price__isnull=True).count(),
            "missing_category": products.filter(category__isnull=True).count(),
            "duplicate_source_product_ids": products.values("source_product_id")
            .annotate(product_count=Count("id"))
            .filter(product_count__gt=1)
            .count(),
        }
    )
    metrics.update(_scan_image_metrics(products))
    return metrics


def _scan_image_metrics(products) -> dict[str, int]:
    metrics = {
        "missing_image_urls": 0,
        "cover_matches_first_image": 0,
        "cover_mismatch_first_image": 0,
    }
    iterable = products.only("cover_image_url", "image_urls").iterator(chunk_size=5000)
    for product in iterable:
        image_urls = product.image_urls or []
        first_image = image_urls[0] if image_urls else None
        if first_image is None:
            metrics["missing_image_urls"] += 1
            continue
        if product.cover_image_url == first_image:
            metrics["cover_matches_first_image"] += 1
        elif product.cover_image_url:
            metrics["cover_mismatch_first_image"] += 1
    return metrics


def _latest_crawl_run(marketplace: Marketplace) -> dict[str, Any] | None:
    run = CrawlRun.objects.filter(marketplace=marketplace).order_by("-started_at").first()
    if run is None:
        return None
    events_by_level = {
        row["level"]: row["count"]
        for row in run.events.values("level").annotate(count=Count("id")).order_by("level")
    }
    duration_seconds = None
    if run.finished_at:
        duration_seconds = round((run.finished_at - run.started_at).total_seconds(), 3)
    return {
        "id": run.id,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_seconds": duration_seconds,
        "discovered_count": run.discovered_count,
        "fetched_count": run.fetched_count,
        "created_count": run.created_count,
        "updated_count": run.updated_count,
        "unchanged_count": run.unchanged_count,
        "deactivated_count": run.deactivated_count,
        "failed_count": run.failed_count,
        "events_by_level": events_by_level,
        "metadata": run.metadata,
    }


def _read_checkpoint(state_file: Path) -> dict[str, Any]:
    checkpoint: dict[str, Any] = {
        "path": str(state_file),
        "exists": state_file.exists(),
        "valid_json": False,
        "crawl_run_id": None,
        "processed_category_urls": 0,
        "processed_category_page_urls": 0,
        "discovered_urls": 0,
        "processed_product_ids": 0,
        "failed_urls": 0,
        "blocked_urls": 0,
        "error": None,
    }
    if not state_file.exists():
        return checkpoint
    try:
        data = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError) as error:
        checkpoint["error"] = str(error)
        return checkpoint

    checkpoint["valid_json"] = True
    checkpoint["crawl_run_id"] = data.get("crawl_run_id")
    for key in (
        "processed_category_urls",
        "processed_category_page_urls",
        "discovered_urls",
        "processed_product_ids",
        "failed_urls",
        "blocked_urls",
    ):
        value = data.get(key) or []
        checkpoint[key] = len(value) if isinstance(value, list) else 0
    return checkpoint


def _add_database_checks(report: dict[str, Any]) -> None:
    db = report["database"]
    _add_check(
        report,
        name="products_present",
        severity="critical",
        passed=db["total_products"] > 0,
        message=f"{db['total_products']} products stored.",
    )
    _add_check(
        report,
        name="canonical_urls_complete",
        severity="critical",
        passed=db["missing_canonical_url"] == 0,
        message=f"{db['missing_canonical_url']} products without canonical_url.",
    )
    _add_check(
        report,
        name="cover_urls_complete",
        severity="critical",
        passed=db["missing_cover_image_url"] == 0,
        message=f"{db['missing_cover_image_url']} products without cover_image_url.",
    )
    _add_check(
        report,
        name="image_urls_complete",
        severity="critical",
        passed=db["missing_image_urls"] == 0,
        message=f"{db['missing_image_urls']} products without image_urls.",
    )
    _add_check(
        report,
        name="source_ids_unique",
        severity="critical",
        passed=db["duplicate_source_product_ids"] == 0,
        message=f"{db['duplicate_source_product_ids']} duplicated source_product_id values.",
    )
    _add_check(
        report,
        name="cover_quality_540_high",
        severity="warning",
        passed=db["cover_540_high"] == db["total_products"],
        message=f"{db['cover_540_high']} covers use t_product_540_high.",
    )
    _add_check(
        report,
        name="categories_present",
        severity="warning",
        passed=db["missing_category"] == 0,
        message=f"{db['missing_category']} products without category.",
    )
    _add_check(
        report,
        name="prices_present",
        severity="warning",
        passed=db["missing_current_price"] == 0,
        message=f"{db['missing_current_price']} products without current_price.",
    )


def _add_crawl_run_checks(report: dict[str, Any]) -> None:
    run = report["latest_crawl_run"]
    _add_check(
        report,
        name="latest_crawl_run_exists",
        severity="critical",
        passed=run is not None,
        message="Latest crawl run exists." if run else "No crawl run exists.",
    )
    if run is None:
        return
    _add_check(
        report,
        name="latest_crawl_success",
        severity="critical",
        passed=run["status"] == CrawlRun.Status.SUCCESS,
        message=f"Latest crawl run status is {run['status']}.",
    )
    _add_check(
        report,
        name="latest_crawl_no_failures",
        severity="critical",
        passed=run["failed_count"] == 0,
        message=f"Latest crawl run has {run['failed_count']} failed items.",
    )
    _add_check(
        report,
        name="latest_crawl_no_error_events",
        severity="critical",
        passed=run["events_by_level"].get("error", 0) == 0,
        message=f"Latest crawl run has {run['events_by_level'].get('error', 0)} error events.",
    )


def _add_checkpoint_checks(report: dict[str, Any], *, require_checkpoint: bool) -> None:
    checkpoint = report["checkpoint"]
    checkpoint_severity = "critical" if require_checkpoint else "warning"
    _add_check(
        report,
        name="checkpoint_exists",
        severity=checkpoint_severity,
        passed=checkpoint["exists"],
        message=f"Checkpoint path: {checkpoint['path']}.",
    )
    if not checkpoint["exists"]:
        return
    _add_check(
        report,
        name="checkpoint_valid_json",
        severity="critical",
        passed=checkpoint["valid_json"],
        message=checkpoint["error"] or "Checkpoint JSON is valid.",
    )
    if not checkpoint["valid_json"]:
        return
    _add_check(
        report,
        name="checkpoint_no_failed_urls",
        severity="critical",
        passed=checkpoint["failed_urls"] == 0,
        message=f"{checkpoint['failed_urls']} failed URLs in checkpoint.",
    )
    _add_check(
        report,
        name="checkpoint_no_blocked_urls",
        severity="critical",
        passed=checkpoint["blocked_urls"] == 0,
        message=f"{checkpoint['blocked_urls']} blocked URLs in checkpoint.",
    )
    db_total = report["database"]["total_products"]
    active_total = report["database"]["active_products"]
    checkpoint_processed = checkpoint["processed_product_ids"]
    _add_check(
        report,
        name="checkpoint_processed_close_to_database",
        severity="warning",
        passed=checkpoint_processed >= db_total * 0.99,
        message=(
            f"{checkpoint_processed} checkpoint product ids vs {db_total} products in database."
        ),
    )
    _add_check(
        report,
        name="active_products_close_to_checkpoint",
        severity="critical",
        passed=active_total >= checkpoint_processed * 0.99,
        message=(
            f"{active_total} active products vs "
            f"{checkpoint_processed} checkpoint product ids."
        ),
    )


def _add_check(
    report: dict[str, Any],
    *,
    name: str,
    severity: str,
    passed: bool,
    message: str,
) -> None:
    report["checks"].append(
        {
            "name": name,
            "severity": severity,
            "passed": passed,
            "message": message,
        }
    )


def _finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    report["critical_count"] = sum(
        1 for check in report["checks"] if check["severity"] == "critical" and not check["passed"]
    )
    report["warning_count"] = sum(
        1 for check in report["checks"] if check["severity"] == "warning" and not check["passed"]
    )
    report["ok"] = report["critical_count"] == 0
    return report
