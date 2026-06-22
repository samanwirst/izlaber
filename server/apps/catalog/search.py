from __future__ import annotations

import re
from collections.abc import Iterable

from django.db.models import Count, Max, Sum

from apps.catalog.models import ProductSearchTerm

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
V_NECK_RE = re.compile(
    r"(?<![0-9a-zа-яё])v\s*[-–—]?\s*(?:образн\w*|вырез\w*)"
    r"|(?<![0-9a-zа-яё])v[-\s]?neck(?![0-9a-zа-яё])"
    r"|треугольн\w*\s+вырез\w*",
    re.IGNORECASE,
)
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
SWEATER_TOKENS = {
    "джемпер",
    "джемпера",
    "джемперы",
    "пуловер",
    "пуловеры",
    "свитер",
    "свитера",
    "свитеры",
}
NECKLINE_TOKENS = {
    "горловина",
    "горловиной",
    "вырез",
    "выреза",
    "вырезом",
    "вырезы",
    "вырезами",
}
V_NECK_HINT_TOKENS = {
    "v",
    "vneck",
    "образная",
    "образного",
    "образной",
    "образным",
    "образными",
    "образный",
    "треугольная",
    "треугольного",
    "треугольной",
    "треугольным",
    "треугольный",
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
    _merge_terms(terms, semantic_terms(title), TITLE_WEIGHT)
    _merge_terms(terms, semantic_terms(brand), BRAND_WEIGHT)
    _merge_terms(terms, semantic_terms(category_path_text), CATEGORY_WEIGHT)
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
    tokens = tokenize(query)
    semantic = query_semantic_terms(query, tokens)
    skip_tokens = _query_skip_tokens(semantic)

    expanded: list[str] = []
    seen: set[str] = set()
    for term in semantic:
        seen.add(term)
        expanded.append(term)
        if len(expanded) >= MAX_QUERY_TOKENS:
            return expanded

    for token in tokens:
        if token in skip_tokens:
            continue
        for synonym in QUERY_SYNONYMS.get(token, {token}):
            if synonym in seen:
                continue
            seen.add(synonym)
            expanded.append(synonym)
            if len(expanded) >= MAX_QUERY_TOKENS:
                return expanded
    return expanded


def semantic_terms(value: str | None) -> list[str]:
    if not value:
        return []

    terms: list[str] = []
    tokens = set(tokenize(value))
    if tokens & SWEATER_TOKENS:
        terms.append("sweater")
    if tokens & NECKLINE_TOKENS:
        terms.append("neckline")
    if V_NECK_RE.search(value):
        terms.append("vneck")
    return terms


def query_semantic_terms(query: str, tokens: list[str] | None = None) -> list[str]:
    tokens = tokens or tokenize(query)
    token_set = set(tokens)
    terms: list[str] = []
    if token_set & SWEATER_TOKENS:
        terms.append("sweater")
    if _query_has_v_neck(query, token_set):
        terms.append("vneck")
    elif token_set & NECKLINE_TOKENS:
        terms.append("neckline")
    return terms


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


def _query_has_v_neck(query: str, tokens: set[str]) -> bool:
    if V_NECK_RE.search(query):
        return True
    return bool(tokens & {"v", "vneck"} and tokens & NECKLINE_TOKENS)


def _query_skip_tokens(semantic: list[str]) -> set[str]:
    skip_tokens: set[str] = set()
    if "sweater" in semantic:
        skip_tokens.update(SWEATER_TOKENS)
    if "vneck" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
        skip_tokens.update(V_NECK_HINT_TOKENS)
    elif "neckline" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
    return skip_tokens


def _split_alpha_numeric(token: str) -> list[str]:
    parts = re.findall(r"[a-zа-яё]+|\d+", token, re.IGNORECASE)
    if len(parts) <= 1:
        return [token]
    return [token, *parts]
