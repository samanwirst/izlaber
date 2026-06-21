from apps.catalog.models import Product, ProductSearchTerm, ProductSnapshot
from apps.catalog.search import search_product_ids
from apps.crawling.models import CrawlRun
from apps.crawling.services import (
    finish_crawl_run,
    get_or_create_marketplace,
    get_product_content_hashes,
    get_product_delta_states,
    record_seen_product_ids,
    upsert_products,
)
from django.utils import timezone
from rest_framework.test import APIClient


def product_payload(source_product_id="p1", content_hash="hash-1", price="1000.00"):
    return {
        "source_product_id": source_product_id,
        "canonical_url": f"https://uzum.uz/ru/product/test-{source_product_id}",
        "title": "Test product",
        "current_price": price,
        "old_price": None,
        "currency": "UZS",
        "availability": "available",
        "image_urls": ["https://images.uzum.uz/test/t_product_540_high.jpg"],
        "specs": {"color": "black"},
        "raw_data": {"id": source_product_id},
        "content_hash": content_hash,
    }


def test_product_upsert_idempotency(db):
    stats = upsert_products(marketplace_code="uzum", products=[product_payload()])
    assert stats.created == 1
    assert Product.objects.count() == 1
    product = Product.objects.get()
    assert product.canonical_url == "https://uzum.uz/ru/product/test-p1"
    assert product.cover_image_url == "https://images.uzum.uz/test/t_product_540_high.jpg"

    stats = upsert_products(marketplace_code="uzum", products=[product_payload()])
    assert stats.unchanged == 1
    assert Product.objects.count() == 1
    assert ProductSnapshot.objects.count() == 0


def test_product_upsert_updates_search_index(db):
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()

    assert search_product_ids(
        "test",
        marketplace_code="uzum",
        active_only=True,
        limit=5,
    ) == [product.id]


def test_product_upsert_uses_explicit_cover_image_url(db):
    payload = product_payload()
    payload["cover_image_url"] = "https://images.uzum.uz/test/custom-cover.jpg"

    upsert_products(marketplace_code="uzum", products=[payload])

    product = Product.objects.get()
    assert product.cover_image_url == "https://images.uzum.uz/test/custom-cover.jpg"


def test_product_hash_lookup_for_delta_crawl(db):
    upsert_products(marketplace_code="uzum", products=[product_payload()])

    hashes = get_product_content_hashes(
        marketplace_code="uzum",
        source_product_ids=["p1", "missing"],
    )

    assert hashes == {"p1": "hash-1"}
    assert get_product_delta_states(
        marketplace_code="uzum",
        source_product_ids=["p1", "missing"],
    ) == {"p1": {"content_hash": "hash-1", "is_active": True}}


def test_product_changed_update_creates_snapshot(db):
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    stats = upsert_products(
        marketplace_code="uzum",
        products=[product_payload(content_hash="hash-2", price="1200.00")],
    )
    product = Product.objects.get()
    assert stats.updated == 1
    assert product.current_price == 1200
    assert ProductSnapshot.objects.count() == 1


def test_full_crawl_finish_deactivates_unseen_products(db):
    marketplace = get_or_create_marketplace("uzum")
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    crawl_run = CrawlRun.objects.create(
        marketplace=marketplace,
        run_type=CrawlRun.RunType.FULL,
        status=CrawlRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    finish_crawl_run(
        crawl_run=crawl_run,
        status=CrawlRun.Status.SUCCESS,
        deactivate_unseen=True,
    )
    product = Product.objects.get()
    assert product.is_active is False
    assert product.unavailable_since is not None


def test_full_crawl_finish_uses_seen_products_for_delta_deactivation(db):
    marketplace = get_or_create_marketplace("uzum")
    upsert_products(
        marketplace_code="uzum",
        products=[
            product_payload(source_product_id="p1"),
            product_payload(source_product_id="p2"),
        ],
    )
    crawl_run = CrawlRun.objects.create(
        marketplace=marketplace,
        run_type=CrawlRun.RunType.FULL,
        status=CrawlRun.Status.RUNNING,
        started_at=timezone.now(),
    )

    record_seen_product_ids(crawl_run=crawl_run, source_product_ids=["p1"])
    finish_crawl_run(
        crawl_run=crawl_run,
        status=CrawlRun.Status.SUCCESS,
        deactivate_unseen=True,
    )

    assert Product.objects.get(source_product_id="p1").is_active is True
    assert Product.objects.get(source_product_id="p2").is_active is False
    p2_term = ProductSearchTerm.objects.filter(product__source_product_id="p2").first()
    assert p2_term is not None
    assert p2_term.product_is_active is False


def test_inactive_product_reactivates_when_seen_again(db):
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    product.is_active = False
    product.unavailable_since = timezone.now()
    product.save()

    stats = upsert_products(marketplace_code="uzum", products=[product_payload()])
    product.refresh_from_db()
    assert stats.unchanged == 1
    assert stats.reactivated == 1
    assert product.is_active is True
    assert product.unavailable_since is None


def test_api_key_auth_rejects_missing_or_wrong_key(settings, db):
    settings.BOT_API_KEY = "bot-key"
    client = APIClient()

    response = client.get("/api/v1/products/")
    assert response.status_code == 403

    response = client.get("/api/v1/products/", HTTP_X_INTERNAL_API_KEY="wrong")
    assert response.status_code == 403

    response = client.get("/api/v1/products/", HTTP_X_INTERNAL_API_KEY="bot-key")
    assert response.status_code == 200
