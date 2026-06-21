from __future__ import annotations

import re
from collections.abc import Iterable

from django.db.models import Count, Max, Sum

from apps.catalog.models import ProductSearchTerm

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
MAX_QUERY_TOKENS = 6
MAX_TOKEN_LENGTH = 64
TITLE_WEIGHT = 10
BRAND_WEIGHT = 8
CATEGORY_WEIGHT = 3
SOURCE_ID_WEIGHT = 1
QUERY_SYNONYMS = {
    "айфон": {"айфон", "iphone"},
    "iphone": {"iphone", "айфон"},
}


def product_search_terms(
    *,
    title: str | None,
    brand: str | None,
    category_path_text: str | None,
    source_product_id: str | None,
) -> dict[str, int]:
    terms: dict[str, int] = {}
    _merge_terms(terms, tokenize(title), TITLE_WEIGHT)
    _merge_terms(terms, tokenize(brand), BRAND_WEIGHT)
    _merge_terms(terms, tokenize(category_path_text), CATEGORY_WEIGHT)
    _merge_terms(terms, tokenize(source_product_id), SOURCE_ID_WEIGHT)
    return terms


def replace_product_search_terms(product) -> None:
    terms = product_search_terms(
        title=product.title,
        brand=product.brand,
        category_path_text=product.category_path_text,
        source_product_id=product.source_product_id,
    )
    ProductSearchTerm.objects.filter(product=product).delete()
    ProductSearchTerm.objects.bulk_create(
        [
            ProductSearchTerm(
                product=product,
                marketplace_code=product.marketplace.code,
                term=term,
                weight=weight,
                product_is_active=product.is_active,
                product_rating=product.rating,
                product_reviews_count=product.reviews_count,
                product_last_seen_at=product.last_seen_at,
            )
            for term, weight in terms.items()
        ],
        batch_size=500,
        ignore_conflicts=True,
    )


def search_product_ids(
    query: str,
    *,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
) -> list[int]:
    terms = query_terms(query)
    if not terms or limit <= 0:
        return []

    queryset = ProductSearchTerm.objects.filter(term__in=terms)
    if marketplace_code:
        queryset = queryset.filter(marketplace_code=marketplace_code)
    if active_only:
        queryset = queryset.filter(product_is_active=True)

    required_terms = len(terms)
    rows = list(
        queryset.values("product_id")
        .annotate(
            matched_terms=Count("term", distinct=True),
            score=Sum("weight"),
            max_weight=Max("weight"),
            max_rating=Max("product_rating"),
            max_reviews_count=Max("product_reviews_count"),
            max_last_seen_at=Max("product_last_seen_at"),
        )
        .filter(matched_terms__gte=required_terms)
        .order_by(
            "-matched_terms",
            "-score",
            "-max_weight",
            "-max_rating",
            "-max_reviews_count",
            "-max_last_seen_at",
        )
        .values_list("product_id", flat=True)[:limit]
    )
    if rows or required_terms == 1:
        return rows

    relaxed_required_terms = max(1, required_terms - 1)
    return list(
        queryset.values("product_id")
        .annotate(
            matched_terms=Count("term", distinct=True),
            score=Sum("weight"),
            max_weight=Max("weight"),
            max_rating=Max("product_rating"),
            max_reviews_count=Max("product_reviews_count"),
            max_last_seen_at=Max("product_last_seen_at"),
        )
        .filter(matched_terms__gte=relaxed_required_terms)
        .order_by(
            "-matched_terms",
            "-score",
            "-max_weight",
            "-max_rating",
            "-max_reviews_count",
            "-max_last_seen_at",
        )
        .values_list("product_id", flat=True)[:limit]
    )


def query_terms(query: str) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokenize(query):
        for synonym in QUERY_SYNONYMS.get(token, {token}):
            if synonym in seen:
                continue
            seen.add(synonym)
            expanded.append(synonym)
            if len(expanded) >= MAX_QUERY_TOKENS:
                return expanded
    return expanded


def tokenize(value: str | None) -> list[str]:
    if not value:
        return []
    tokens: list[str] = []
    for raw_token in TOKEN_RE.findall(value.lower()):
        for token in _split_alpha_numeric(raw_token):
            if len(token) < 2:
                continue
            tokens.append(token[:MAX_TOKEN_LENGTH])
    return tokens


def _merge_terms(target: dict[str, int], terms: Iterable[str], weight: int) -> None:
    for term in terms:
        target[term] = max(weight, target.get(term, 0))


def _split_alpha_numeric(token: str) -> list[str]:
    parts = re.findall(r"[a-zа-яё]+|\d+", token, re.IGNORECASE)
    if len(parts) <= 1:
        return [token]
    return [token, *parts]
