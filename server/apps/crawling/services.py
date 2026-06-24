from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import models, transaction
from django.db.models import Subquery
from django.utils import timezone

from apps.catalog.models import (
    Category,
    Marketplace,
    Product,
    ProductSearchTerm,
    ProductSnapshot,
    Seller,
)
from apps.catalog.search import product_search_text, replace_product_search_terms
from apps.crawling.models import CrawlRun, CrawlRunSeenProduct, SearchBackfillRequest


@dataclass(frozen=True, slots=True)
class UpsertStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    reactivated: int = 0


def normalize_search_backfill_query(query: str) -> str:
    return " ".join(str(query or "").split())[:255]


@transaction.atomic
def create_search_backfill_request(
    *,
    marketplace_code: str,
    query: str,
    source: str = "bot_search",
    requested_by_telegram_user_id: int | None = None,
    limit: int = 30,
    priority: int = 100,
    metadata: dict[str, Any] | None = None,
) -> SearchBackfillRequest:
    normalized_query = normalize_search_backfill_query(query)
    marketplace = get_or_create_marketplace(marketplace_code)
    reusable = (
        SearchBackfillRequest.objects.select_for_update()
        .filter(
            marketplace=marketplace,
            normalized_query=normalized_query.casefold(),
            status__in=[
                SearchBackfillRequest.Status.PENDING,
                SearchBackfillRequest.Status.RUNNING,
            ],
        )
        .order_by("priority", "created_at")
        .first()
    )
    if reusable is not None:
        if priority < reusable.priority:
            reusable.priority = priority
            reusable.save(update_fields=["priority", "updated_at"])
        return reusable

    return SearchBackfillRequest.objects.create(
        marketplace=marketplace,
        query=normalized_query,
        normalized_query=normalized_query.casefold(),
        source=source[:64] or "bot_search",
        requested_by_telegram_user_id=requested_by_telegram_user_id,
        limit=max(1, min(int(limit), 100)),
        priority=max(1, min(int(priority), 1000)),
        metadata=metadata or {},
    )


@transaction.atomic
def claim_search_backfill_request(
    *,
    marketplace_code: str,
    worker_id: str,
    stale_after_seconds: int = 600,
) -> SearchBackfillRequest | None:
    marketplace = get_or_create_marketplace(marketplace_code)
    stale_before = timezone.now() - timedelta(seconds=stale_after_seconds)
    SearchBackfillRequest.objects.filter(
        marketplace=marketplace,
        status=SearchBackfillRequest.Status.RUNNING,
        claimed_at__lt=stale_before,
        attempts__lt=models.F("max_attempts"),
    ).update(
        status=SearchBackfillRequest.Status.PENDING,
        worker_id="",
        claimed_at=None,
        last_error="stale worker claim released",
    )
    request = (
        SearchBackfillRequest.objects.select_for_update()
        .filter(
            marketplace=marketplace,
            status=SearchBackfillRequest.Status.PENDING,
            attempts__lt=models.F("max_attempts"),
        )
        .order_by("priority", "created_at")
        .first()
    )
    if request is None:
        return None
    request.status = SearchBackfillRequest.Status.RUNNING
    request.worker_id = worker_id[:128]
    request.claimed_at = timezone.now()
    request.finished_at = None
    request.attempts += 1
    request.last_error = ""
    request.save(
        update_fields=[
            "status",
            "worker_id",
            "claimed_at",
            "finished_at",
            "attempts",
            "last_error",
            "updated_at",
        ]
    )
    return request


@transaction.atomic
def finish_search_backfill_request(
    *,
    request_id: int,
    status: str,
    stats: dict[str, Any] | None = None,
    error: str = "",
) -> SearchBackfillRequest:
    request = SearchBackfillRequest.objects.select_for_update().get(pk=request_id)
    stats = stats or {}
    status = (
        status
        if status in SearchBackfillRequest.Status.values
        else SearchBackfillRequest.Status.FAILED
    )
    request.status = status
    request.finished_at = timezone.now()
    request.discovered_count = int(stats.get("discovered") or 0)
    request.changed_count = int(stats.get("changed") or 0)
    request.created_count = int(stats.get("created") or 0)
    request.updated_count = int(stats.get("updated") or 0)
    request.last_error = error[:4000]
    request.metadata = {**request.metadata, "last_stats": stats}
    request.save()
    return request


def get_or_create_marketplace(code: str) -> Marketplace:
    marketplace_defaults = {
        "uzum": {
            "name": "Uzum Market",
            "base_url": "https://uzum.uz",
        },
        "wildberries": {
            "name": "Wildberries",
            "base_url": "https://www.wildberries.uz",
        },
    }
    marketplace_default = marketplace_defaults.get(code)
    defaults = {
        "name": marketplace_default["name"] if marketplace_default else code.title(),
        "base_url": marketplace_default["base_url"] if marketplace_default else "",
        "is_active": True,
    }
    marketplace, _ = Marketplace.objects.get_or_create(code=code, defaults=defaults)
    return marketplace


def get_product_content_hashes(
    *,
    marketplace_code: str,
    source_product_ids: list[str],
) -> dict[str, str]:
    return {
        source_product_id: state["content_hash"]
        for source_product_id, state in get_product_delta_states(
            marketplace_code=marketplace_code,
            source_product_ids=source_product_ids,
        ).items()
    }


def get_product_delta_states(
    *,
    marketplace_code: str,
    source_product_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not source_product_ids:
        return {}
    marketplace = Marketplace.objects.filter(code=marketplace_code).first()
    if marketplace is None:
        return {}
    rows = Product.objects.filter(
        marketplace=marketplace,
        source_product_id__in=[str(product_id) for product_id in source_product_ids],
    ).values_list("source_product_id", "content_hash", "is_active")
    return {
        source_product_id: {"content_hash": content_hash, "is_active": is_active}
        for source_product_id, content_hash, is_active in rows
    }


@transaction.atomic
def record_seen_product_ids(
    *,
    crawl_run: CrawlRun,
    source_product_ids: list[str],
) -> int:
    unique_ids = sorted({str(product_id) for product_id in source_product_ids if product_id})
    if not unique_ids:
        return 0
    CrawlRunSeenProduct.objects.bulk_create(
        [
            CrawlRunSeenProduct(crawl_run=crawl_run, source_product_id=source_product_id)
            for source_product_id in unique_ids
        ],
        ignore_conflicts=True,
        batch_size=5000,
    )
    return len(unique_ids)


@transaction.atomic
def upsert_products(
    *,
    marketplace_code: str,
    products: list[dict[str, Any]],
    crawl_run: CrawlRun | None = None,
    create_snapshot: bool = False,
) -> UpsertStats:
    marketplace = get_or_create_marketplace(marketplace_code)
    stats = {"created": 0, "updated": 0, "unchanged": 0, "reactivated": 0}
    now = timezone.now()
    seller_cache: dict[tuple[str, str], Seller | None] = {}
    category_cache: dict[tuple[str, str], Category | None] = {}

    for payload in products:
        source_product_id = str(payload["source_product_id"])
        seller_payload = payload.get("seller") or {}
        category_payload = payload.get("category") or {}
        seller_key = _seller_cache_key(seller_payload)
        category_key = _category_cache_key(category_payload)
        if seller_key not in seller_cache:
            seller_cache[seller_key] = _upsert_seller(marketplace, seller_payload)
        if category_key not in category_cache:
            category_cache[category_key] = _upsert_category(marketplace, category_payload)
        seller = seller_cache[seller_key]
        category = category_cache[category_key]
        defaults = _product_defaults(payload, seller=seller, category=category, now=now)
        product, created = Product.objects.get_or_create(
            marketplace=marketplace,
            source_product_id=source_product_id,
            defaults=defaults,
        )
        if created:
            replace_product_search_terms(product)
            stats["created"] += 1
            if create_snapshot:
                _create_snapshot(product, crawl_run)
            continue

        was_inactive = not product.is_active
        if product.content_hash == defaults["content_hash"]:
            product.last_seen_at = now
            product.is_active = True
            product.unavailable_since = None
            update_fields = [
                "last_seen_at",
                "is_active",
                "unavailable_since",
                "updated_at",
            ]
            if product.search_text != defaults["search_text"]:
                product.search_text = defaults["search_text"]
                update_fields.append("search_text")
            product.save(
                update_fields=update_fields
            )
            stats["unchanged"] += 1
            if was_inactive:
                replace_product_search_terms(product)
                stats["reactivated"] += 1
            continue

        cover_changed = product.cover_image_url != defaults["cover_image_url"]
        for field, value in defaults.items():
            if field != "first_seen_at":
                setattr(product, field, value)
        if cover_changed:
            _reset_product_visual_fingerprint(product)
        product.last_seen_at = now
        product.is_active = True
        product.unavailable_since = None
        product.save()
        replace_product_search_terms(product)
        _create_snapshot(product, crawl_run)
        stats["updated"] += 1
        if was_inactive:
            stats["reactivated"] += 1

    if crawl_run is not None:
        crawl_run.created_count += stats["created"]
        crawl_run.updated_count += stats["updated"]
        crawl_run.unchanged_count += stats["unchanged"]
        crawl_run.fetched_count += len(products)
        crawl_run.save(
            update_fields=[
                "created_count",
                "updated_count",
                "unchanged_count",
                "fetched_count",
            ]
        )

    return UpsertStats(**stats)


@transaction.atomic
def finish_crawl_run(
    *,
    crawl_run: CrawlRun,
    status: str,
    log_summary: str = "",
    metadata: dict[str, Any] | None = None,
    deactivate_unseen: bool = False,
) -> CrawlRun:
    crawl_run.status = status
    crawl_run.finished_at = timezone.now()
    crawl_run.log_summary = log_summary
    if metadata:
        crawl_run.metadata = {**crawl_run.metadata, **metadata}

    if deactivate_unseen and crawl_run.run_type == CrawlRun.RunType.FULL:
        crawl_run.deactivated_count = _deactivate_unseen_products(crawl_run)

    crawl_run.save()
    return crawl_run


def _deactivate_unseen_products(crawl_run: CrawlRun) -> int:
    seen_products = CrawlRunSeenProduct.objects.filter(crawl_run=crawl_run)
    active_products = Product.objects.filter(
        marketplace=crawl_run.marketplace,
        is_active=True,
    )
    if seen_products.exists():
        unseen = active_products.exclude(
            source_product_id__in=Subquery(seen_products.values("source_product_id"))
        )
    else:
        # Backward-compatible fallback for old parser runs that updated last_seen_at.
        unseen = active_products.filter(last_seen_at__lt=crawl_run.started_at)

    unseen_ids = unseen.values("id")
    ProductSearchTerm.objects.filter(product_id__in=Subquery(unseen_ids)).update(
        product_is_active=False
    )
    return unseen.update(
        is_active=False,
        availability=Product.Availability.UNAVAILABLE,
        unavailable_since=timezone.now(),
    )


def _upsert_seller(marketplace: Marketplace, payload: dict[str, Any]) -> Seller | None:
    name = payload.get("name")
    if not name:
        return None
    source_seller_id = payload.get("source_seller_id")
    lookup = (
        {"marketplace": marketplace, "source_seller_id": str(source_seller_id)}
        if source_seller_id
        else None
    )
    defaults = {
        "name": name,
        "url": payload.get("url"),
        "rating": _decimal_or_none(payload.get("rating")),
        "raw_data": payload.get("raw_data") or payload,
    }
    if lookup:
        seller, _ = Seller.objects.update_or_create(defaults=defaults, **lookup)
        return seller
    seller, _ = Seller.objects.get_or_create(marketplace=marketplace, name=name, defaults=defaults)
    return seller


def _seller_cache_key(payload: dict[str, Any]) -> tuple[str, str]:
    source_seller_id = payload.get("source_seller_id")
    if source_seller_id:
        return ("source", str(source_seller_id))
    return ("name", str(payload.get("name") or ""))


def _upsert_category(marketplace: Marketplace, payload: dict[str, Any]) -> Category | None:
    name = payload.get("name") or payload.get("path_text")
    if not name:
        return None
    source_category_id = payload.get("source_category_id")
    defaults = {
        "name": name,
        "slug": payload.get("slug"),
        "path_text": payload.get("path_text") or name,
        "url": payload.get("url"),
        "raw_data": payload.get("raw_data") or payload,
    }
    if source_category_id:
        category, _ = Category.objects.update_or_create(
            marketplace=marketplace,
            source_category_id=str(source_category_id),
            defaults=defaults,
        )
        return category
    category, _ = Category.objects.get_or_create(
        marketplace=marketplace,
        path_text=defaults["path_text"],
        defaults=defaults,
    )
    return category


def _category_cache_key(payload: dict[str, Any]) -> tuple[str, str]:
    source_category_id = payload.get("source_category_id")
    if source_category_id:
        return ("source", str(source_category_id))
    return ("path", str(payload.get("path_text") or payload.get("name") or ""))


def _product_defaults(
    payload: dict[str, Any],
    *,
    seller: Seller | None,
    category: Category | None,
    now,
) -> dict[str, Any]:
    return {
        "canonical_url": payload["canonical_url"],
        "title": payload["title"],
        "description": payload.get("description"),
        "brand": payload.get("brand"),
        "seller": seller,
        "category": category,
        "category_path_text": payload.get("category_path_text"),
        "rating": _decimal_or_none(payload.get("rating")),
        "reviews_count": payload.get("reviews_count"),
        "current_price": _decimal_or_none(payload.get("current_price")),
        "old_price": _decimal_or_none(payload.get("old_price")),
        "currency": payload.get("currency") or "UZS",
        "availability": payload.get("availability") or Product.Availability.UNKNOWN,
        "cover_image_url": payload.get("cover_image_url") or _first_image_url(payload),
        "image_urls": payload.get("image_urls") or [],
        "specs": payload.get("specs") or {},
        "raw_data": payload.get("raw_data") or {},
        "search_text": product_search_text(
            title=payload["title"],
            description=payload.get("description"),
            brand=payload.get("brand"),
            category_path_text=payload.get("category_path_text"),
            source_product_id=payload["source_product_id"],
        ),
        "content_hash": payload["content_hash"],
        "first_seen_at": now,
        "last_seen_at": now,
        "is_active": True,
        "unavailable_since": None,
    }


def _create_snapshot(product: Product, crawl_run: CrawlRun | None) -> ProductSnapshot:
    return ProductSnapshot.objects.create(
        product=product,
        crawl_run=crawl_run,
        price=product.current_price,
        old_price=product.old_price,
        availability=product.availability,
        rating=product.rating,
        reviews_count=product.reviews_count,
        content_hash=product.content_hash,
        raw_data=product.raw_data,
    )


def _reset_product_visual_fingerprint(product: Product) -> None:
    product.cover_image_ahash = None
    product.cover_image_dhash = None
    product.cover_image_fingerprint_url = None
    product.cover_image_fingerprint_at = None


def _decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _first_image_url(payload: dict[str, Any]) -> str | None:
    image_urls = payload.get("image_urls") or []
    return image_urls[0] if image_urls else None
