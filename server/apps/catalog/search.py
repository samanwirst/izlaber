from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

from django.db import connection
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
COMPRESSION_TOKENS = {
    "компрессионка",
    "компрессионки",
    "компрессионку",
}
COMPRESSION_WEAR_TOKENS = {
    "белье",
    "гольфы",
    "костюм",
    "костюмы",
    "леггинсы",
    "лонгслив",
    "майка",
    "носки",
    "одежда",
    "рашгард",
    "рукав",
    "спорт",
    "спортивная",
    "спортивный",
    "тайтсы",
    "топ",
    "футболка",
    "футболки",
    "шорты",
    "штаны",
}
PHONE_TOKENS = {
    "iphone",
    "айфон",
}
PHONE_ACCESSORY_TOKENS = {
    "адаптер",
    "блок",
    "держатель",
    "зарядка",
    "кабель",
    "пленка",
    "стекло",
    "чехол",
    "чехлы",
}
PRICE_STOP_TOKENS = {
    "до",
    "дешевле",
    "ниже",
    "менее",
    "от",
    "дороже",
    "выше",
    "более",
    "тыс",
    "тысяч",
    "тысячи",
    "тысяча",
    "к",
    "k",
    "млн",
    "миллион",
    "миллиона",
    "миллионов",
    "сум",
    "uzs",
}
MAX_POSTGRES_CANDIDATES = 1000


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


def product_search_text(
    *,
    title: str | None,
    brand: str | None,
    category_path_text: str | None,
    source_product_id: str | None,
) -> str:
    title_text = " ".join([title or ""] * 3)
    brand_text = " ".join([brand or ""] * 2)
    semantic_text = " ".join(
        [
            *semantic_terms(title),
            *semantic_terms(brand),
            *semantic_terms(category_path_text),
        ]
    )
    parts = [
        title_text,
        brand_text,
        category_path_text or "",
        str(source_product_id or ""),
        semantic_text,
    ]
    return " ".join(part for part in parts if part).strip()


def replace_product_search_terms(product) -> None:
    if connection.vendor == "postgresql":
        return

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
    min_price: Decimal | int | str | None = None,
    max_price: Decimal | int | str | None = None,
) -> list[int]:
    terms = query_terms(query)
    if not terms or limit <= 0:
        return []

    query_min_price, query_max_price = query_price_filters(query)
    min_price = _clean_price(min_price) or query_min_price
    max_price = _clean_price(max_price) or query_max_price

    if connection.vendor == "postgresql":
        rows = _search_product_ids_postgres(
            terms=terms,
            query=query,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
        )
        if rows:
            return rows

        # Trigram catches morphology and typos that exact token FTS misses.
        return _search_product_ids_postgres_trigram(
            query=query,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
        )

    queryset = ProductSearchTerm.objects.filter(term__in=terms)
    if marketplace_code:
        queryset = queryset.filter(marketplace_code=marketplace_code)
    if active_only:
        queryset = queryset.filter(product_is_active=True)
    if min_price is not None:
        queryset = queryset.filter(product__current_price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(product__current_price__lte=max_price)

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
    skip_tokens.update(_price_skip_tokens(tokens))

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


def query_price_filters(query: str) -> tuple[Decimal | None, Decimal | None]:
    normalized = query.lower().replace(",", ".")
    price_pattern = re.compile(
        r"\b(?P<direction>до|дешевле|ниже|менее|от|дороже|выше|более)\s+"
        r"(?P<amount>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>тыс(?:яч[аи]?)?|к|k|млн|миллион(?:а|ов)?)?\b",
        re.IGNORECASE,
    )

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    for match in price_pattern.finditer(normalized):
        value = _price_amount(match.group("amount"), match.group("unit"))
        if value is None:
            continue
        direction = match.group("direction")
        if direction in {"до", "дешевле", "ниже", "менее"}:
            max_price = value if max_price is None else min(max_price, value)
        else:
            min_price = value if min_price is None else max(min_price, value)
    return min_price, max_price


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
    if _has_compression_wear_term(tokens):
        terms.append("compressionwear")
    return terms


def query_semantic_terms(query: str, tokens: list[str] | None = None) -> list[str]:
    tokens = tokens or tokenize(query)
    token_set = set(tokens)
    terms: list[str] = []
    if token_set & SWEATER_TOKENS:
        terms.append("sweater")
    if _has_compression_term(token_set):
        terms.append("compressionwear")
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
    if "compressionwear" in semantic:
        skip_tokens.update(COMPRESSION_TOKENS)
    if "vneck" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
        skip_tokens.update(V_NECK_HINT_TOKENS)
    elif "neckline" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
    return skip_tokens


def _has_compression_wear_term(tokens: set[str]) -> bool:
    return _has_compression_term(tokens) and bool(tokens & COMPRESSION_WEAR_TOKENS)


def _has_compression_term(tokens: set[str]) -> bool:
    return any(token in COMPRESSION_TOKENS or token.startswith("компрессион") for token in tokens)


def _price_skip_tokens(tokens: list[str]) -> set[str]:
    skip_tokens: set[str] = set()
    for index, token in enumerate(tokens):
        if token in PRICE_STOP_TOKENS:
            skip_tokens.add(token)
            if index + 1 < len(tokens) and tokens[index + 1].isdigit():
                skip_tokens.add(tokens[index + 1])
            if index > 0 and tokens[index - 1].isdigit():
                skip_tokens.add(tokens[index - 1])
        elif token.isdigit():
            previous_token = tokens[index - 1] if index > 0 else ""
            next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
            if previous_token in PRICE_STOP_TOKENS or next_token in PRICE_STOP_TOKENS:
                skip_tokens.add(token)
    return skip_tokens


def _split_alpha_numeric(token: str) -> list[str]:
    parts = re.findall(r"[a-zа-яё]+|\d+", token, re.IGNORECASE)
    if len(parts) <= 1:
        return [token]
    return [token, *parts]


def _search_product_ids_postgres(
    *,
    terms: list[str],
    query: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    min_price: Decimal | None,
    max_price: Decimal | None,
) -> list[int]:
    tsquery = _tsquery(terms, operator=" & ")
    return _fetch_postgres_product_ids(
        where_sql="to_tsvector('simple'::regconfig, p.search_text) @@ to_tsquery('simple', %s)",
        where_params=[tsquery],
        rank_sql=(
            "ts_rank_cd(to_tsvector('simple'::regconfig, p.search_text), "
            "to_tsquery('simple', %s))"
        ),
        rank_params=[tsquery],
        query=query,
        marketplace_code=marketplace_code,
        active_only=active_only,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
    )


def _search_product_ids_postgres_trigram(
    *,
    query: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    min_price: Decimal | None,
    max_price: Decimal | None,
) -> list[int]:
    return _fetch_postgres_product_ids(
        where_sql="p.search_text %% %s",
        where_params=[query],
        rank_sql="similarity(p.search_text, %s)",
        rank_params=[query],
        query=query,
        marketplace_code=marketplace_code,
        active_only=active_only,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
    )


def _fetch_postgres_product_ids(
    *,
    where_sql: str,
    where_params: list,
    rank_sql: str,
    rank_params: list,
    query: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    min_price: Decimal | None,
    max_price: Decimal | None,
) -> list[int]:
    where_clauses = [where_sql]
    params: list = []
    params.extend(where_params)

    if marketplace_code:
        where_clauses.append("m.code = %s")
        params.append(marketplace_code)
    if active_only:
        where_clauses.append("p.is_active = TRUE")
    if min_price is not None:
        where_clauses.append("p.current_price >= %s")
        params.append(min_price)
    if max_price is not None:
        where_clauses.append("p.current_price <= %s")
        params.append(max_price)

    bounded_limit = min(max(limit, 1), MAX_POSTGRES_CANDIDATES)
    intent_order_sql = _postgres_intent_order_sql(query)
    sql = f"""
        SELECT p.id
        FROM catalog_product p
        JOIN catalog_marketplace m ON m.id = p.marketplace_id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY
            {intent_order_sql}
            {rank_sql} DESC,
            p.rating DESC NULLS LAST,
            p.reviews_count DESC NULLS LAST,
            p.last_seen_at DESC
        LIMIT %s
    """
    params.extend(rank_params)
    params.append(bounded_limit)

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [row[0] for row in cursor.fetchall()]


def _tsquery(terms: list[str], *, operator: str) -> str:
    return operator.join(f"{term}:*" for term in terms if term)


def _postgres_intent_order_sql(query: str) -> str:
    tokens = set(tokenize(query))
    if tokens & PHONE_TOKENS and not tokens & PHONE_ACCESSORY_TOKENS:
        return """
            CASE
                WHEN p.category_path_text ILIKE '%%смартфоны%%'
                 AND p.category_path_text NOT ILIKE '%%аксессуар%%'
                THEN 0
                WHEN p.title ILIKE '%%чехол%%'
                  OR p.title ILIKE '%%кабель%%'
                  OR p.title ILIKE '%%стекло%%'
                  OR p.title ILIKE '%%адаптер%%'
                  OR p.title ILIKE '%%заряд%%'
                  OR p.category_path_text ILIKE '%%аксессуар%%'
                THEN 2
                ELSE 1
            END ASC,
        """
    return ""


def _price_amount(amount: str, unit: str | None) -> Decimal | None:
    try:
        value = Decimal(amount)
    except Exception:
        return None

    normalized_unit = (unit or "").lower()
    if normalized_unit in {"тыс", "тысяч", "тысячи", "тысяча", "к", "k"}:
        value *= Decimal("1000")
    elif normalized_unit in {"млн", "миллион", "миллиона", "миллионов"}:
        value *= Decimal("1000000")
    return value


def _clean_price(value: Decimal | int | str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    return parsed if parsed >= 0 else None
