import pytest

from parsers.uzum_market.browser import UzumBrowserClient
from parsers.uzum_market.config import ParserConfig
from parsers.uzum_market.normalizer import (
    dedupe_product_urls,
    extract_product_id,
    normalize_product,
    products_from_html,
)
from parsers.uzum_market.pipeline import _needs_upsert, run_crawl
from parsers.uzum_market.storage import CheckpointStore


def test_normalizer_handles_json_ld_product():
    html = """
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": " Phone ",
      "description": "Great phone",
      "image": ["//images.uzum.uz/a.jpg"],
      "offers": {"price": "1200000", "priceCurrency": "UZS", "availability": "https://schema.org/InStock"},
      "aggregateRating": {"ratingValue": "4.8", "reviewCount": "12"}
    }
    </script>
    """
    products = products_from_html(html, "https://uzum.uz/ru/product/phone-123")
    assert products[0]["source_product_id"] == "123"
    assert products[0]["title"] == "Phone"
    assert products[0]["availability"] == "available"
    assert products[0]["content_hash"]


def test_deduplicates_product_urls():
    urls = dedupe_product_urls(
        [
            "https://uzum.uz/ru/product/phone-123",
            "/ru/product/phone-123?skuId=1",
            "/ru/product/case-456",
        ]
    )
    assert len(urls) == 2
    assert urls[0].endswith("/ru/product/phone-123")


def test_extract_product_id_uses_trailing_numeric_segment():
    product_id = extract_product_id(
        "https://uzum.uz/ru/product/ochki-virtualnoj-realnosti-vr-box-belyj---5-1086485?skuId=1"
    )
    assert product_id == "1086485"


def test_delta_upsert_required_for_new_changed_or_inactive_products():
    product = {"source_product_id": "1", "content_hash": "new-hash"}

    assert _needs_upsert(product, None) is True
    assert _needs_upsert(product, {"content_hash": "old-hash", "is_active": True}) is True
    assert _needs_upsert(product, {"content_hash": "new-hash", "is_active": False}) is True
    assert _needs_upsert(product, {"content_hash": "new-hash", "is_active": True}) is False


def test_normalize_product_tolerates_missing_fields():
    product = normalize_product({"title": "A"}, "https://uzum.uz/ru/product/a-1")
    assert product["source_product_id"] == "1"
    assert product["currency"] == "UZS"


def test_normalize_product_sets_cover_from_first_image():
    product = normalize_product(
        {
            "title": "A",
            "image_urls": [
                "https://images.uzum.uz/a/t_product_540_high.jpg",
                "https://images.uzum.uz/b/t_product_540_high.jpg",
            ],
        },
        "https://uzum.uz/ru/product/a-1",
    )

    assert product["cover_image_url"] == "https://images.uzum.uz/a/t_product_540_high.jpg"


def test_category_tree_builds_stable_urls():
    client = UzumBrowserClient.__new__(UzumBrowserClient)
    urls = client._category_urls_from_tree(
        [
            {
                "id": 2894,
                "title": "Мебель",
                "children": [
                    {
                        "id": 17616,
                        "seoHeader": "Кровати и матрасы",
                        "children": [],
                    }
                ],
            }
        ]
    )

    assert urls == [
        "https://uzum.uz/ru/category/krovati-i-matrasy-17616",
    ]


def test_graphql_filters_roundtrip_in_category_page_url():
    filters = [
        {
            "filterType": "RANGE",
            "id": "0",
            "range": {"min": 3000, "max": 22525},
            "list": None,
        }
    ]
    url = UzumBrowserClient._category_page_url(
        "https://uzum.uz/ru/category/aksessuary-i-zapchasti-10398",
        2,
        filters,
    )

    assert url.endswith("currentPage=2&filters=filter%3DRV-0%3A3000~22525")
    assert UzumBrowserClient._filters_from_url(url) == filters


@pytest.mark.asyncio
async def test_parser_dry_run_does_not_write_to_server(monkeypatch, tmp_path):
    async def fake_discover(self, limit=None):
        yield "https://uzum.uz/ru/category/test-1"

    async def fake_collect_listing_products(self, url):
        return [normalize_product({"title": "A"}, "https://uzum.uz/ru/product/a-1")]

    class DummyBrowserClient:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def collect_category_page_urls(self, url):
            return [url]

        async def collect_listing_products(self, url):
            return await fake_collect_listing_products(self, url)

    monkeypatch.setattr("parsers.uzum_market.discovery.UzumDiscovery.discover", fake_discover)
    monkeypatch.setattr("parsers.uzum_market.pipeline.UzumBrowserClient", DummyBrowserClient)

    config = ParserConfig(
        server_api_base_url="http://127.0.0.1:1/api",
        parser_api_key="parser-key",
        crawl_delay_seconds=0,
        state_dir=tmp_path,
        discovery_start_urls=("https://uzum.uz/ru/category/test-1",),
    )
    stats = await run_crawl(config=config, mode="test", limit=1, resume=False, dry_run=True)
    assert stats["processed"] == 1


def test_checkpoint_store_fills_missing_keys(tmp_path):
    store = CheckpointStore(tmp_path)
    store.save({"discovered_urls": ["https://uzum.uz/ru/product/a-1"]})

    state = store.load()

    assert state["discovered_urls"] == ["https://uzum.uz/ru/product/a-1"]
    assert state["processed_product_ids"] == []
    assert state["failed_urls"] == []


def test_checkpoint_store_writes_atomically(tmp_path):
    store = CheckpointStore(tmp_path)
    store.save({"processed_product_ids": ["1"]})

    assert store.load()["processed_product_ids"] == ["1"]
    assert not (tmp_path / "checkpoint.tmp").exists()
