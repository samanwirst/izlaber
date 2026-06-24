import re
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any

from parsers.common import content_hash
from parsers.wildberries.client import CatalogSegment, CategoryTask
from parsers.wildberries.config import ParserConfig

BASE_URL = "https://www.wildberries.uz"


def normalize_product(
    raw: dict[str, Any],
    *,
    category: CategoryTask,
    segment: CatalogSegment,
    config: ParserConfig,
) -> dict[str, Any] | None:
    source_product_id = str(raw.get("id") or "").strip()
    if not source_product_id:
        return None

    title = normalize_whitespace(raw.get("name")) or f"Wildberries product {source_product_id}"
    image_urls = _product_image_urls(source_product_id, raw.get("pics") or 1)
    current_price, old_price = _product_prices(raw)
    seller_name = normalize_whitespace(raw.get("supplier"))
    brand = normalize_whitespace(raw.get("brand"))
    canonical_url = canonical_product_url(source_product_id)
    normalized = {
        "source_product_id": source_product_id,
        "canonical_url": canonical_url,
        "title": title,
        "description": normalize_whitespace(raw.get("description")),
        "brand": brand,
        "seller": {
            "source_seller_id": str(raw.get("supplierId") or ""),
            "name": seller_name,
            "url": _seller_url(raw.get("supplierId")),
            "rating": normalize_price(raw.get("supplierRating")),
            "raw_data": {
                "supplierId": raw.get("supplierId"),
                "supplier": raw.get("supplier"),
                "supplierRating": raw.get("supplierRating"),
            },
        }
        if seller_name
        else None,
        "category": {
            "source_category_id": category.source_category_id,
            "name": category.name,
            "slug": _slug_from_url(category.url),
            "path_text": category.path,
            "url": category.url,
            "raw_data": {
                "shard": category.shard,
                "query": category.query,
                "params": category.params,
            },
        },
        "category_path_text": category.path,
        "rating": normalize_price(raw.get("reviewRating") or raw.get("rating")),
        "reviews_count": _int_or_none(raw.get("feedbacks")),
        "current_price": current_price,
        "old_price": old_price,
        "currency": config.currency_code,
        "availability": "available" if _has_available_size(raw) else "unknown",
        "cover_image_url": image_urls[0] if image_urls else None,
        "image_urls": image_urls,
        "specs": _specs(raw),
        "raw_data": {
            "wildberries": raw,
            "category": {
                "source_category_id": category.source_category_id,
                "name": category.name,
                "path": category.path,
                "url": category.url,
                "shard": category.shard,
                "query": category.query,
            },
            "segment": {
                "price_min_u": segment.price_min_u,
                "price_max_u": segment.price_max_u,
                "total": segment.total,
                "capped": segment.capped,
            },
            "delivery": {
                "dest": config.destination_ids,
                "currency": config.currency_param,
            },
        },
    }
    normalized["content_hash"] = content_hash(normalized)
    return normalized


def normalize_whitespace(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def normalize_price(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def canonical_product_url(source_product_id: str) -> str:
    return f"{BASE_URL}/catalog/{source_product_id}/detail.aspx"


def _product_prices(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    prices: list[int] = []
    old_prices: list[int] = []
    for size in raw.get("sizes") or []:
        if not isinstance(size, dict):
            continue
        price = size.get("price") or {}
        if not isinstance(price, dict):
            continue
        product_price = _int_or_none(price.get("product"))
        basic_price = _int_or_none(price.get("basic"))
        if product_price:
            prices.append(product_price)
        if basic_price:
            old_prices.append(basic_price)

    current = min(prices) if prices else _int_or_none(raw.get("salePriceU"))
    old = max(old_prices) if old_prices else _int_or_none(raw.get("priceU"))
    current_price = _price_u_to_decimal(current)
    old_price = _price_u_to_decimal(old) if old and old != current else None
    return current_price, old_price


def _price_u_to_decimal(value: int | None) -> str | None:
    if value in (None, 0):
        return None
    return str(Decimal(value) / Decimal(100))


def _product_image_urls(source_product_id: str, pics: Any) -> list[str]:
    try:
        nm_id = int(source_product_id)
    except ValueError:
        return []
    try:
        count = max(1, min(int(pics), 10))
    except (TypeError, ValueError):
        count = 1
    vol = nm_id // 100000
    part = nm_id // 1000
    host = _basket_host(vol)
    return [
        f"https://{host}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/c516x688/{index}.webp"
        for index in range(1, count + 1)
    ]


def _basket_host(vol: int) -> str:
    ranges = [
        (143, 1),
        (287, 2),
        (431, 3),
        (719, 4),
        (1007, 5),
        (1061, 6),
        (1115, 7),
        (1169, 8),
        (1313, 9),
        (1601, 10),
        (1655, 11),
        (1919, 12),
        (2045, 13),
        (2189, 14),
        (2405, 15),
        (2621, 16),
        (2837, 17),
        (3053, 18),
        (3269, 19),
        (3485, 20),
        (3701, 21),
        (3917, 22),
        (4133, 23),
        (4349, 24),
        (4565, 25),
        (4781, 26),
        (4997, 27),
        (5213, 28),
        (5429, 29),
        (5645, 30),
        (5861, 31),
        (6077, 32),
        (6293, 33),
        (6509, 34),
        (6725, 35),
        (6941, 36),
        (7157, 37),
        (7373, 38),
        (7589, 39),
        (7805, 40),
        (8021, 41),
        (8237, 42),
        (8453, 43),
        (8669, 44),
        (8885, 45),
        (9101, 46),
    ]
    for max_vol, basket in ranges:
        if vol <= max_vol:
            return f"basket-{basket:02d}"
    return "basket-46"


def _has_available_size(raw: dict[str, Any]) -> bool:
    sizes = raw.get("sizes") or []
    return any(isinstance(size, dict) for size in sizes)


def _specs(raw: dict[str, Any]) -> dict[str, Any]:
    specs: dict[str, Any] = {}
    if colors := raw.get("colors"):
        specs["colors"] = colors
    if sizes := raw.get("sizes"):
        specs["sizes"] = [
            {
                "name": size.get("name"),
                "origName": size.get("origName"),
                "optionId": size.get("optionId"),
                "wh": size.get("wh"),
                "time1": size.get("time1"),
                "time2": size.get("time2"),
            }
            for size in sizes
            if isinstance(size, dict)
        ]
    return specs


def _seller_url(supplier_id: Any) -> str | None:
    seller_id = _int_or_none(supplier_id)
    if seller_id is None:
        return None
    return f"{BASE_URL}/seller/{seller_id}"


def _slug_from_url(url: str) -> str | None:
    slug = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return slug or None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
