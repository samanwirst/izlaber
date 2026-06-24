import json
import re
from decimal import Decimal
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from parsers.uzum_market.fingerprints import content_hash

BASE_URL = "https://uzum.uz"
PRODUCT_RE = re.compile(r"/(?:ru|uz)?/?product/[^\"'<>\s]*-(?P<id>\d+)(?:[/?#][^\"'<>\s]*)?$")


def normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_price(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = re.sub(r"[^\d.,]", "", value).replace(",", ".")
    try:
        return str(Decimal(str(value)))
    except Exception:
        return None


def canonical_product_url(url: str) -> str:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def extract_product_id(url: str) -> str | None:
    match = PRODUCT_RE.search(url)
    return match.group("id") if match else None


def dedupe_product_urls(urls: list[str]) -> list[str]:
    seen_ids: set[str] = set()
    result: list[str] = []
    for url in urls:
        product_id = extract_product_id(url)
        if not product_id or product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        result.append(canonical_product_url(url))
    return result


def normalize_product(raw: dict[str, Any], canonical_url: str) -> dict[str, Any]:
    source_product_id = str(raw.get("source_product_id") or extract_product_id(canonical_url) or "")
    title = normalize_whitespace(raw.get("title")) or "Untitled product"
    image_urls = [_normalize_url(url) for url in raw.get("image_urls", []) if url]
    cover_image_url = raw.get("cover_image_url")
    if cover_image_url:
        cover_image_url = _normalize_url(cover_image_url)
    elif image_urls:
        cover_image_url = image_urls[0]
    seller = raw.get("seller") or {}
    category = raw.get("category") or {}
    normalized = {
        "source_product_id": source_product_id,
        "canonical_url": canonical_product_url(canonical_url),
        "title": title,
        "description": normalize_whitespace(raw.get("description")),
        "brand": normalize_whitespace(raw.get("brand")),
        "seller": {
            "source_seller_id": seller.get("source_seller_id"),
            "name": normalize_whitespace(seller.get("name")),
            "url": _normalize_url(seller.get("url")) if seller.get("url") else None,
            "rating": normalize_price(seller.get("rating")),
            "raw_data": seller.get("raw_data") or seller,
        }
        if seller.get("name")
        else None,
        "category": {
            "source_category_id": category.get("source_category_id"),
            "name": normalize_whitespace(category.get("name") or category.get("path_text")),
            "slug": category.get("slug"),
            "path_text": normalize_whitespace(category.get("path_text") or category.get("name")),
            "url": _normalize_url(category.get("url")) if category.get("url") else None,
            "raw_data": category.get("raw_data") or category,
        }
        if category
        else None,
        "category_path_text": normalize_whitespace(raw.get("category_path_text")),
        "rating": normalize_price(raw.get("rating")),
        "reviews_count": _int_or_none(raw.get("reviews_count")),
        "current_price": normalize_price(raw.get("current_price")),
        "old_price": normalize_price(raw.get("old_price")),
        "currency": raw.get("currency") or "UZS",
        "availability": raw.get("availability") or "unknown",
        "cover_image_url": cover_image_url,
        "image_urls": image_urls,
        "specs": raw.get("specs") or {},
        "raw_data": raw.get("raw_data") or raw,
    }
    normalized["content_hash"] = content_hash(normalized)
    return normalized


def product_from_json_ld(data: dict[str, Any], canonical_url: str) -> dict[str, Any]:
    offers = data.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    aggregate_rating = data.get("aggregateRating") or {}
    images = data.get("image") or []
    if isinstance(images, str):
        images = [images]
    raw = {
        "title": data.get("name"),
        "description": data.get("description"),
        "brand": (
            (data.get("brand") or {}).get("name")
            if isinstance(data.get("brand"), dict)
            else data.get("brand")
        ),
        "current_price": offers.get("price"),
        "currency": offers.get("priceCurrency") or "UZS",
        "availability": _availability_from_schema(offers.get("availability")),
        "rating": aggregate_rating.get("ratingValue"),
        "reviews_count": aggregate_rating.get("reviewCount"),
        "image_urls": images,
        "seller": _seller_from_schema(offers.get("seller")),
        "raw_data": data,
    }
    return normalize_product(raw, canonical_url)


def products_from_html(html: str, url: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    pattern = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    for raw_json in re.findall(pattern, html, re.S):
        try:
            data = json.loads(unescape(raw_json.strip()))
        except json.JSONDecodeError:
            continue
        entries = _json_ld_entries(data)
        for entry in entries:
            if isinstance(entry, dict) and entry.get("@type") == "Product":
                products.append(product_from_json_ld(entry, url))
    return products


def product_urls_from_html(html: str) -> list[str]:
    return dedupe_product_urls([match.group(0) for match in PRODUCT_RE.finditer(html)])


def _normalize_url(value: str) -> str:
    return urljoin(BASE_URL, value)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _availability_from_schema(value: str | None) -> str:
    if not value:
        return "unknown"
    lowered = value.lower()
    if "instock" in lowered:
        return "available"
    if "outofstock" in lowered:
        return "unavailable"
    return "unknown"


def _json_ld_entries(data: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    stack = data if isinstance(data, list) else [data]
    for entry in stack:
        if not isinstance(entry, dict):
            continue
        entries.append(entry)
        graph = entry.get("@graph")
        if isinstance(graph, list):
            entries.extend(graph_item for graph_item in graph if isinstance(graph_item, dict))
    return entries


def _seller_from_schema(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str):
        name = normalize_whitespace(value)
        return {"name": name, "raw_data": value} if name else None
    if not isinstance(value, dict):
        return None
    name = normalize_whitespace(value.get("name"))
    if not name:
        return None
    return {
        "source_seller_id": value.get("@id") or value.get("identifier"),
        "name": name,
        "url": value.get("url"),
        "raw_data": value,
    }
