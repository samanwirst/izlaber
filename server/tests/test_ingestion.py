import re
import warnings

import pytest
from apps.catalog import search as catalog_search
from apps.catalog.models import Product, ProductSearchTerm, ProductSnapshot
from apps.catalog.search import (
    product_search_terms,
    product_search_text,
    protected_query_term_groups,
    query_price_filters,
    query_terms,
    search_product_ids,
)
from apps.catalog.serializers import ProductCardSerializer
from apps.catalog.visual import (
    ImageFingerprintError,
    hamming_distance_hex,
    image_fingerprint,
    visual_search_product_ids,
)
from apps.catalog.visual_index import VisualIndexStats
from apps.crawling.models import CrawlRun, SearchBackfillRequest
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


def test_get_or_create_marketplace_knows_wildberries(db):
    marketplace = get_or_create_marketplace("wildberries")

    assert marketplace.name == "Wildberries"
    assert marketplace.base_url == "https://www.wildberries.uz"


def test_product_card_serializer_includes_marketplace_source(db):
    upsert_products(marketplace_code="wildberries", products=[product_payload()])
    product = Product.objects.select_related("marketplace").get()

    data = ProductCardSerializer(product).data

    assert data["marketplace"]["code"] == "wildberries"
    assert data["marketplace"]["name"] == "Wildberries"
    assert data["marketplace"]["base_url"] == "https://www.wildberries.uz"


def test_product_upsert_reuses_category_within_batch(db, monkeypatch):
    calls = 0

    def wrapped_upsert_category(marketplace, payload):
        nonlocal calls
        calls += 1
        return original_upsert_category(marketplace, payload)

    from apps.crawling import services

    original_upsert_category = services._upsert_category
    monkeypatch.setattr(services, "_upsert_category", wrapped_upsert_category)
    products = [
        {
            **product_payload(source_product_id=f"p{index}", content_hash=f"hash-{index}"),
            "category": {
                "source_category_id": "369",
                "name": "Батончики",
                "path_text": "Батончики",
                "url": "https://uzum.uz/ru/category/batonchiki-369",
            },
        }
        for index in range(3)
    ]

    stats = upsert_products(marketplace_code="uzum", products=products)

    assert stats.created == 3
    assert calls == 1


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


def test_search_query_normalizes_generic_phone_case_intent():
    assert query_terms("чехол на телефон") == ["чехол"]
    assert query_terms("чехол для смартфона") == ["чехол"]
    assert query_terms("стикеры на чехол телефона") == ["стикеры", "чехол", "телефона"]

    phone_case_order = catalog_search._postgres_intent_order_sql("чехол на телефон")
    assert "стикер" in phone_case_order
    assert "наклей" in phone_case_order
    assert "аксессуары для смартфонов" in phone_case_order
    assert "THEN 5" in phone_case_order

    sticker_order = catalog_search._postgres_intent_order_sql("стикеры на чехол телефона")
    assert sticker_order == ""


def test_search_intent_order_demotes_watch_strap_charms():
    order_sql = catalog_search._postgres_intent_order_sql("ремешок для часов")

    assert "шарм" in order_sql
    assert "подвеск" in order_sql


@pytest.mark.parametrize(
    ("query", "terms"),
    [
        ("стекло на телефон", ["стекло"]),
        ("пленка для смартфона", ["пленка"]),
        ("зарядка для телефона", ["зарядка"]),
        ("кабель для телефона", ["кабель"]),
        ("держатель для телефона", ["держатель"]),
    ],
)
def test_search_query_normalizes_generic_phone_accessory_intents(query, terms):
    assert query_terms(query) == terms

    order_sql = catalog_search._postgres_intent_order_sql(query)

    assert "аксессуары для смартфонов" in order_sql
    assert "смартфоны" in order_sql
    assert "THEN 0" in order_sql
    assert "THEN 5" in order_sql


@pytest.mark.parametrize(
    ("query", "preferred_fragment", "demoted_fragment"),
    [
        ("чехол для ноутбука", "ноутбук", "THEN 5"),
        ("ремешок для часов", "ремеш", "THEN 5"),
        ("фильтр для пылесоса", "пылесос", "THEN 5"),
        ("наклейки на клавиатуру", "клавиатур", "THEN 5"),
        ("обложка на паспорт", "паспорт", "THEN 5"),
    ],
)
def test_search_intent_order_handles_accessory_target_queries(
    query,
    preferred_fragment,
    demoted_fragment,
):
    order_sql = catalog_search._postgres_intent_order_sql(query)

    assert preferred_fragment in order_sql
    assert demoted_fragment in order_sql
    assert "THEN 0" in order_sql


def test_search_index_includes_description_terms():
    terms = product_search_terms(
        title="Батончик Snickers, 50 г",
        description="SNICKERS шоколадный батончик",
        brand=None,
        category_path_text=None,
        source_product_id="42828",
    )
    search_text = product_search_text(
        title="Батончик Snickers, 50 г",
        description="SNICKERS шоколадный батончик",
        brand=None,
        category_path_text=None,
        source_product_id="42828",
    )

    assert terms["шоколадный"] == catalog_search.DESCRIPTION_WEIGHT
    assert "шоколадный батончик" in search_text


def test_search_protects_latin_brand_in_mixed_query():
    assert protected_query_term_groups("Snickers") == [{"snickers", "сникерс"}]
    assert protected_query_term_groups("Snickers шоколадный батончик") == [
        {"snickers", "сникерс"}
    ]
    assert protected_query_term_groups("сникерс батончик") == [{"snickers", "сникерс"}]
    assert protected_query_term_groups("white sneakers") == []
    assert catalog_search._token_regex("сникерс")
    assert catalog_search._tsquery(["snickers", "сникерс"], operator=" & ") == (
        "(snickers:* | сникерс:*)"
    )


def test_search_does_not_relax_away_latin_brand(db):
    a4 = product_payload(source_product_id="a4", content_hash="hash-a4")
    a4["title"] = "А4 Шоколадный батончик, 40 г"
    upsert_products(marketplace_code="uzum", products=[a4])

    assert (
        search_product_ids(
            "Snickers шоколадный батончик",
            marketplace_code="uzum",
            active_only=True,
            limit=5,
        )
        == []
    )

    snickers = product_payload(source_product_id="snickers", content_hash="hash-snickers")
    snickers["title"] = "Шоколадный батончик Snickers, 50 г"
    upsert_products(marketplace_code="uzum", products=[snickers])

    product_ids = search_product_ids(
        "Snickers шоколадный батончик",
        marketplace_code="uzum",
        active_only=True,
        limit=5,
    )

    assert product_ids == [Product.objects.get(source_product_id="snickers").id]


def test_snickers_brand_does_not_match_sneaker_word():
    pattern = catalog_search._token_regex("сникерс")

    assert re.search(pattern, "батончик сникерс, 50 г")
    assert not re.search(pattern, "кроссовки сникерсы")


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


def test_search_backfill_request_lifecycle(settings, db):
    settings.BOT_API_KEY = "bot-key"
    settings.PARSER_API_KEY = "parser-key"
    client = APIClient()

    response = client.post(
        "/api/internal/search-backfill-requests/",
        {"marketplace": "uzum", "query": "Snickers батончик", "source": "bot_photo_search_miss"},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 202
    request_id = response.data["id"]
    assert response.data["status"] == SearchBackfillRequest.Status.PENDING
    assert response.data["normalized_query"] == "snickers батончик"

    duplicate = client.post(
        "/api/internal/search-backfill-requests/",
        {"marketplace": "uzum", "query": " snickers   батончик "},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert duplicate.status_code == 202
    assert duplicate.data["id"] == request_id

    claim = client.post(
        "/api/internal/search-backfill-requests/claim/",
        {"marketplace": "uzum", "worker_id": "test-worker"},
        format="json",
        HTTP_X_INTERNAL_API_KEY="parser-key",
    )

    assert claim.status_code == 200
    assert claim.data["id"] == request_id
    assert claim.data["status"] == SearchBackfillRequest.Status.RUNNING

    finish = client.post(
        f"/api/internal/search-backfill-requests/{request_id}/finish/",
        {
            "status": "success",
            "stats": {"discovered": 30, "changed": 2, "created": 1, "updated": 1},
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="parser-key",
    )

    assert finish.status_code == 200
    assert finish.data["status"] == SearchBackfillRequest.Status.SUCCESS
    assert finish.data["created_count"] == 1
    assert finish.data["updated_count"] == 1


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
    assert row["marketplace"]["code"] == "uzum"
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


def test_image_fingerprint_rejects_decompression_bomb_warning(monkeypatch):
    from PIL import Image

    class FakeImage:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def convert(self, mode):
            warnings.warn(
                "image is too large",
                Image.DecompressionBombWarning,
                stacklevel=2,
            )
            return self

    monkeypatch.setattr(Image, "open", lambda image_bytes: FakeImage())

    with pytest.raises(ImageFingerprintError):
        image_fingerprint(b"not-used")


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
    assert response.data[0]["marketplace"]["code"] == "uzum"
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
