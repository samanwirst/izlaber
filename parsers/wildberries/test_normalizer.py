import pytest

from parsers.wildberries.client import CatalogSegment, CategoryTask
from parsers.wildberries.config import ParserConfig
from parsers.wildberries.normalizer import normalize_product
from parsers.wildberries.pipeline import run_search_backfill


def test_normalize_wildberries_product():
    category = CategoryTask(
        source_category_id="8126",
        name="Блузки и рубашки",
        path="Женщинам > Блузки и рубашки",
        url="https://www.wildberries.uz/catalog/zhenshchinam/odezhda/bluzki-i-rubashki",
        shard="bl_shirts",
        query="cat=8126",
        params={"cat": "8126"},
    )
    segment = CatalogSegment(category=category, total=100)
    raw = {
        "id": 237194752,
        "name": "Рубашка оверсайз прозрачная летняя",
        "brand": "ENRIbase",
        "supplierId": 1399208,
        "supplier": "ENRIbase",
        "rating": 5,
        "feedbacks": 20773,
        "pics": 2,
        "sizes": [
            {
                "name": "42-50",
                "optionId": 373382862,
                "wh": 507,
                "price": {"basic": 80650000, "product": 21350000},
            }
        ],
    }

    product = normalize_product(
        raw,
        category=category,
        segment=segment,
        config=ParserConfig(server_api_base_url="http://server/api", parser_api_key="key"),
    )

    assert product is not None
    assert product["source_product_id"] == "237194752"
    assert product["canonical_url"] == (
        "https://www.wildberries.uz/catalog/237194752/detail.aspx"
        "?targetUrl=GP&size=373382862"
    )
    assert product["current_price"] == "213500"
    assert product["old_price"] == "806500"
    assert product["brand"] == "ENRIbase"
    assert product["seller"]["source_seller_id"] == "1399208"
    assert product["category"]["source_category_id"] == "8126"
    assert product["cover_image_url"].startswith(
        "https://basket-15.wbbasket.ru/vol2371/part237194/237194752/images/c516x688/"
    )
    assert product["content_hash"]


@pytest.mark.asyncio
async def test_wildberries_search_backfill_upserts_products(monkeypatch):
    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def fetch_search_page(self, query: str, *, page: int):
            assert query == "snickers"
            assert page == 1
            return {
                "metadata": {"name": "snickers"},
                "products": [
                    {
                        "id": 945622805,
                        "name": "Шоколадные конфеты Snickers",
                        "brand": "Snickers",
                        "supplierId": 83720,
                        "supplier": "iCover",
                        "reviewRating": 4.9,
                        "feedbacks": 29,
                        "pics": 1,
                        "sizes": [
                            {
                                "name": "",
                                "optionId": 1422006848,
                                "wh": 218671,
                                "price": {"basic": 299000, "product": 31800},
                            }
                        ],
                    }
                ],
            }

    class FakeStorage:
        upserted: list[dict] = []

        def __init__(self, config, dry_run=False):
            self.config = config
            self.dry_run = dry_run

        async def start_crawl_run(self, mode, metadata):
            assert mode == "incremental"
            assert metadata["kind"] == "search_backfill"
            assert metadata["queries"] == ["snickers"]
            return 123

        async def record_seen_product_ids(self, crawl_run_id, source_product_ids):
            assert crawl_run_id == 123
            assert source_product_ids == ["945622805"]
            return {"seen_count": 1}

        async def get_product_states(self, source_product_ids):
            return {}

        async def upsert_products(self, products, crawl_run_id):
            assert crawl_run_id == 123
            self.upserted.extend(products)
            return {
                "created_count": len(products),
                "updated_count": 0,
                "unchanged_count": 0,
                "reactivated_count": 0,
            }

        async def finish_crawl_run(self, crawl_run_id, *, status, deactivate_unseen, metadata):
            assert crawl_run_id == 123
            assert status == "success"
            assert deactivate_unseen is False
            assert metadata["processed"] == 1

    monkeypatch.setattr("parsers.wildberries.pipeline.WildberriesClient", FakeClient)
    monkeypatch.setattr("parsers.wildberries.pipeline.ServerStorage", FakeStorage)

    stats = await run_search_backfill(
        config=ParserConfig(server_api_base_url="http://server/api", parser_api_key="key"),
        queries=["snickers"],
        limit=1,
        dry_run=False,
    )

    assert stats["processed"] == 1
    assert stats["created"] == 1
    assert FakeStorage.upserted[0]["source_product_id"] == "945622805"
    assert FakeStorage.upserted[0]["canonical_url"] == (
        "https://www.wildberries.uz/catalog/945622805/detail.aspx"
        "?targetUrl=SG&size=1422006848"
    )
    assert FakeStorage.upserted[0]["category"]["source_category_id"] == "search:snickers"
    assert FakeStorage.upserted[0]["raw_data"]["search_backfill"]["query"] == "snickers"
