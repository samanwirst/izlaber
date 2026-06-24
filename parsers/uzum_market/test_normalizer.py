import pytest

from parsers.uzum_market.browser import UzumBrowserClient
from parsers.uzum_market.config import ParserConfig
from parsers.uzum_market.discovery import UzumDiscovery
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


def test_normalizer_handles_json_ld_graph_product():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Product",
          "name": "Батончик Snickers, 50 г",
          "description": "SNICKERS шоколадный батончик",
          "image": ["https://images.uzum.uz/snickers/t_product_540_low.jpg"],
          "offers": {
            "price": 5000,
            "priceCurrency": "UZS",
            "availability": "https://schema.org/OutOfStock",
            "seller": {"@type": "Organization", "name": "Adler Group"}
          },
          "aggregateRating": {"ratingValue": 4.9, "reviewCount": 230}
        }
      ]
    }
    </script>
    """

    products = products_from_html(html, "https://uzum.uz/ru/product/batonchik-snickers-50-g-42828")

    assert products[0]["source_product_id"] == "42828"
    assert products[0]["title"] == "Батончик Snickers, 50 г"
    assert products[0]["current_price"] == "5000"
    assert products[0]["availability"] == "unavailable"
    assert products[0]["seller"]["name"] == "Adler Group"


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


def test_graphql_search_phase_errors_are_retryable():
    errors = [
        {
            "message": (
                "search_phase_execution_exception: all shards failed"
            )
        }
    ]

    assert UzumBrowserClient._is_retryable_graphql_error(errors) is True


def test_browser_rejects_missing_product_placeholder():
    assert UzumBrowserClient._is_missing_product({"title": "Не нашли такой товар"}) is True
    assert UzumBrowserClient._is_missing_product({"title": "Батончик Snickers, 50 г"}) is False


def test_browser_profile_can_start_without_seed_profile(tmp_path):
    client = UzumBrowserClient.__new__(UzumBrowserClient)
    client.config = ParserConfig(
        server_api_base_url="http://127.0.0.1:1/api",
        parser_api_key="parser-key",
        browser_profile_source=tmp_path / "missing-source",
        browser_runtime_profile_dir=tmp_path / "runtime-profile",
        browser_profile_name="Default",
    )

    profile_dir = client._prepare_profile_dir()

    assert profile_dir == tmp_path / "runtime-profile"
    assert (profile_dir / "Default").is_dir()


@pytest.mark.asyncio
async def test_direct_auth_mode_does_not_launch_chrome(monkeypatch):
    def fail_launch(*_args, **_kwargs):
        raise AssertionError("Chrome should not be launched in direct auth mode")

    monkeypatch.setattr(UzumBrowserClient, "_launch_chrome", fail_launch)
    config = ParserConfig(
        server_api_base_url="http://127.0.0.1:1/api",
        parser_api_key="parser-key",
        uzum_auth_token="token",
        uzum_x_iid="iid",
    )

    async with UzumBrowserClient(config) as client:
        assert client._page is None
        assert client._graphql_search_query
        assert client._graphql_headers["authorization"] == "Bearer token"
        assert client._graphql_headers["x-iid"] == "iid"


@pytest.mark.asyncio
async def test_discovery_uses_explicit_start_urls_without_root_lookup():
    class DummyClient:
        async def collect_root_category_urls(self):
            raise AssertionError("root categories should not be requested")

    config = ParserConfig(
        server_api_base_url="http://127.0.0.1:1/api",
        parser_api_key="parser-key",
        discovery_start_urls=("https://uzum.uz/ru/category/batonchiki-369",),
    )

    urls = [url async for url in UzumDiscovery(DummyClient(), config).discover()]

    assert urls == ["https://uzum.uz/ru/category/batonchiki-369"]


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


@pytest.mark.asyncio
async def test_url_backfill_dry_run_collects_direct_and_listing_urls(monkeypatch, tmp_path):
    from parsers.uzum_market.pipeline import run_url_backfill

    class DummyBrowserClient:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def collect_listing_links(self, url):
            return [], [
                "https://uzum.uz/ru/product/batonchik-snickers-50-g-42828?skuId=1",
                "https://uzum.uz/ru/product/batonchik-snickers-50-g-42828?skuId=2",
            ]

        async def collect_product_detail(self, url):
            return normalize_product(
                {"title": "Батончик Snickers, 50 г", "current_price": "5000"},
                url,
            )

    monkeypatch.setattr("parsers.uzum_market.pipeline.UzumBrowserClient", DummyBrowserClient)
    config = ParserConfig(
        server_api_base_url="http://127.0.0.1:1/api",
        parser_api_key="parser-key",
        crawl_delay_seconds=0,
        state_dir=tmp_path,
    )

    stats = await run_url_backfill(
        config=config,
        urls=[
            "https://uzum.uz/ru/category/tovary-snickers",
            "https://uzum.uz/ru/product/batonchik-snickers-50-g-42828",
        ],
        url_file=None,
        limit=None,
        dry_run=True,
    )

    assert stats["source_urls"] == 2
    assert stats["listing_urls"] == 1
    assert stats["product_urls"] == 2
    assert stats["discovered"] == 1
    assert stats["server_unchanged"] == 1


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
