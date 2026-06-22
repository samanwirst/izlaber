from apps.catalog import search as catalog_search
from apps.catalog.models import Product, ProductSearchTerm, ProductSnapshot
from apps.catalog.search import (
    product_search_terms,
    query_price_filters,
    query_terms,
    search_product_ids,
)
from apps.catalog.visual import hamming_distance_hex, visual_search_product_ids
from apps.catalog.visual_index import VisualIndexStats
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
    assert product.search_text

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


def test_search_normalizes_v_neck_sweater_query():
    assert query_terms("свитер v вырез") == ["sweater", "vneck"]
    assert query_terms("кофта v вырез") == ["vneck", "кофта"]
    assert query_terms("кардиган v вырез") == ["vneck", "кардиган"]

    terms = product_search_terms(
        title="Женский серый свитер с V образным вырезом, базовый теплый трикотаж",
        brand=None,
        category_path_text="Джемперы, свитеры и кардиганы",
        source_product_id="p1",
    )

    assert terms["sweater"] == 10
    assert terms["neckline"] == 10
    assert terms["vneck"] == 10

    t_shirt_terms = product_search_terms(
        title="Женская кофта с V образным вырезом",
        brand=None,
        category_path_text="Футболки и поло",
        source_product_id="p2",
    )
    assert "sweater" not in t_shirt_terms
    assert t_shirt_terms["vneck"] == 10


def test_search_query_skips_price_noise_and_extracts_price_filter():
    assert query_terms("кроссовки белые до 300 тысяч") == ["кроссовки", "белые"]
    assert query_price_filters("кроссовки белые до 300 тысяч") == (None, 300000)
    assert query_terms("компрессионка") == ["compressionwear"]


def test_search_relaxes_extra_visual_details_without_losing_product_type(db):
    mug = product_payload(source_product_id="mug-1", content_hash="hash-mug")
    mug["title"] = "Кружка белая с рисунком для чая"
    landscape = product_payload(source_product_id="decor-1", content_hash="hash-decor")
    landscape["title"] = "Картина настенная с горным пейзажем"
    upsert_products(marketplace_code="uzum", products=[mug, landscape])

    product_ids = search_product_ids(
        "Белая кружка с пейзажем.",
        marketplace_code="uzum",
        active_only=True,
        limit=5,
    )

    assert product_ids[0] == Product.objects.get(source_product_id="mug-1").id


def test_postgres_relaxed_search_drops_later_descriptive_terms_first(monkeypatch):
    calls = []

    def fake_postgres_search(**kwargs):
        calls.append(kwargs["terms"])
        if kwargs["terms"] == ["белая", "кружка"]:
            return [123]
        return []

    monkeypatch.setattr(
        catalog_search,
        "_search_product_ids_postgres",
        fake_postgres_search,
    )

    product_ids = catalog_search._search_product_ids_postgres_relaxed(
        terms=["белая", "кружка", "пейзажем"],
        marketplace_code="uzum",
        active_only=True,
        limit=5,
        min_price=None,
        max_price=None,
    )

    assert product_ids == [123]
    assert calls[0] == ["белая", "кружка"]


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


def test_product_list_uses_lightweight_payload(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])

    client = APIClient()
    response = client.get(
        "/api/v1/products/",
        {"q": "test", "marketplace": "uzum", "limit": 5},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["title"] == "Test product"
    assert row["cover_image_url"] == "https://images.uzum.uz/test/t_product_540_high.jpg"
    assert "raw_data" not in row
    assert "specs" not in row
    assert "image_urls" not in row


def test_visual_search_product_ids_matches_cover_fingerprint(db):
    upsert_products(
        marketplace_code="uzum",
        products=[
            product_payload(source_product_id="p1", content_hash="hash-1"),
            product_payload(source_product_id="p2", content_hash="hash-2"),
        ],
    )
    p1 = Product.objects.get(source_product_id="p1")
    p2 = Product.objects.get(source_product_id="p2")
    Product.objects.filter(id=p1.id).update(
        cover_image_ahash="ffffffffffffffff",
        cover_image_dhash="0000000000000000",
        cover_image_fingerprint_url=p1.cover_image_url,
    )
    Product.objects.filter(id=p2.id).update(
        cover_image_ahash="0000000000000000",
        cover_image_dhash="ffffffffffffffff",
        cover_image_fingerprint_url=p2.cover_image_url,
    )

    assert hamming_distance_hex("ffffffffffffffff", "fffffffffffffffe") == 1
    assert visual_search_product_ids(
        ahash="fffffffffffffffe",
        dhash="0000000000000001",
        marketplace_code="uzum",
        active_only=True,
        limit=5,
        max_distance=2,
    ) == [p1.id]


def test_visual_search_api_returns_product_cards(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    Product.objects.filter(id=product.id).update(
        cover_image_ahash="ffffffffffffffff",
        cover_image_dhash="0000000000000000",
        cover_image_fingerprint_url=product.cover_image_url,
    )

    client = APIClient()
    response = client.post(
        "/api/v1/products/visual-search/",
        {
            "ahash": "ffffffffffffffff",
            "dhash": "0000000000000000",
            "marketplace": "uzum",
            "max_distance": 0,
            "limit": 5,
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    assert response.data[0]["id"] == product.id
    assert response.data[0]["cover_image_url"] == product.cover_image_url


def test_visual_index_api_indexes_requested_product(settings, db, monkeypatch):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(
        marketplace_code="uzum",
        products=[product_payload(source_product_id="2797446")],
    )
    product = Product.objects.get()
    indexed_rows = []

    def fake_index_product_cover_rows(*, rows, concurrency, timeout):
        indexed_rows.extend(rows)
        return VisualIndexStats(processed=len(rows), updated=len(rows), failed=0)

    monkeypatch.setattr(
        "apps.catalog.views.index_product_cover_rows",
        fake_index_product_cover_rows,
    )

    client = APIClient()
    response = client.post(
        "/api/v1/products/visual-index/",
        {"source_product_ids": ["2797446"]},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    assert response.data == {"processed": 1, "updated": 1, "failed": 0}
    assert indexed_rows == [(product.id, product.cover_image_url)]
