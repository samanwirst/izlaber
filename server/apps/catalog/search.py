from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from decimal import Decimal

from django.db import connection
from django.db.models import Count, Max, Sum

from apps.catalog.models import ProductSearchTerm

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
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
DESCRIPTION_WEIGHT = 4
CATEGORY_WEIGHT = 3
SOURCE_ID_WEIGHT = 1
QUERY_SYNONYMS = {
    "айфона": {"айфон", "айфона", "iphone"},
    "айфоне": {"айфон", "айфоне", "iphone"},
    "айфонов": {"айфон", "айфонов", "iphone"},
    "айфону": {"айфон", "айфону", "iphone"},
    "айфон": {"айфон", "iphone"},
    "iphone": {"iphone", "айфон"},
    "snickers": {"snickers", "сникерс"},
    "сникерс": {"сникерс", "snickers"},
}
PROTECTED_QUERY_SYNONYMS = {
    "snickers": {"snickers", "сникерс"},
    "сникерс": {"сникерс", "snickers"},
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
    "айфона",
    "айфоне",
    "айфонов",
    "айфону",
    "редми",
    "самсунг",
    "сяоми",
    "redmi",
    "samsung",
    "xiaomi",
}
GENERIC_PHONE_TOKENS = {
    "мобильный",
    "смартфон",
    "смартфона",
    "смартфоне",
    "смартфонов",
    "смартфоны",
    "телефон",
    "телефона",
    "телефоне",
    "телефонов",
    "телефоны",
}
PHONE_CASE_TOKENS = {
    "case",
    "cover",
    "чехол",
    "чехла",
    "чехле",
    "чехлом",
    "чехлы",
}
PHONE_GLASS_TOKENS = {
    "glass",
    "стекла",
    "стекле",
    "стекло",
    "стеклом",
}
PHONE_FILM_TOKENS = {
    "film",
    "пленка",
    "пленки",
    "пленкой",
    "пленку",
    "плёнка",
    "плёнки",
    "плёнкой",
    "плёнку",
}
PHONE_CHARGER_TOKENS = {
    "adapter",
    "charger",
    "адаптер",
    "адаптера",
    "блок",
    "зарядка",
    "зарядки",
    "зарядку",
    "зарядная",
    "зарядное",
    "зарядной",
    "зарядный",
}
PHONE_CABLE_TOKENS = {
    "cable",
    "lightning",
    "type",
    "usb",
    "кабелем",
    "кабель",
    "кабеля",
    "провод",
    "провода",
    "шнур",
    "шнура",
}
PHONE_HOLDER_TOKENS = {
    "holder",
    "stand",
    "держателе",
    "держатель",
    "держателя",
    "крепление",
    "крепления",
    "подставка",
    "подставки",
}
PHONE_ACCESSORY_QUERY_TOKENS = (
    PHONE_CASE_TOKENS
    | PHONE_GLASS_TOKENS
    | PHONE_FILM_TOKENS
    | PHONE_CHARGER_TOKENS
    | PHONE_CABLE_TOKENS
    | PHONE_HOLDER_TOKENS
)
STICKER_INTENT_TOKENS = {
    "label",
    "sticker",
    "stickers",
    "этикетка",
    "этикетки",
    "наклейка",
    "наклейки",
    "стикер",
    "стикерами",
    "стикеры",
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
LAPTOP_TARGET_TOKENS = {
    "laptop",
    "noutbuk",
    "ноутбук",
    "ноутбука",
    "ноутбуке",
    "ноутбуков",
    "ноутбуки",
}
LAPTOP_ACCESSORY_TOKENS = PHONE_CASE_TOKENS | {
    "bag",
    "sleeve",
    "сумка",
    "сумки",
}
WATCH_TARGET_TOKENS = {
    "applewatch",
    "watch",
    "часам",
    "часах",
    "часов",
    "часы",
}
WATCH_STRAP_TOKENS = {
    "band",
    "strap",
    "браслет",
    "браслета",
    "ремешка",
    "ремешки",
    "ремешок",
    "ремешком",
}
VACUUM_TARGET_TOKENS = {
    "vacuum",
    "пылесос",
    "пылесоса",
    "пылесосов",
    "пылесосы",
}
VACUUM_CONSUMABLE_TOKENS = {
    "filter",
    "nozzle",
    "brush",
    "мешки",
    "мешок",
    "насадка",
    "насадки",
    "фильтр",
    "фильтра",
    "фильтры",
    "щетка",
    "щетки",
    "щётка",
    "щётки",
}
KEYBOARD_TARGET_TOKENS = {
    "keyboard",
    "клавиатура",
    "клавиатуре",
    "клавиатуру",
    "клавиатуры",
}
PASSPORT_TARGET_TOKENS = {
    "passport",
    "паспорт",
    "паспорта",
    "паспорте",
}
PASSPORT_COVER_TOKENS = PHONE_CASE_TOKENS | {
    "обложка",
    "обложки",
    "обложкой",
    "обложку",
}
ACCESSORY_TARGET_INTENT_RULES = (
    (
        LAPTOP_ACCESSORY_TOKENS,
        LAPTOP_TARGET_TOKENS,
        ("чехол", "чехлы", "сумк", "case", "cover", "sleeve"),
        ("аксессуары для ноутбуков", "сумки для ноутбуков", "чехл", "сумк"),
        ("ноутбук", "laptop", "noutbuk"),
        ("ноутбук", "laptop", "noutbuk"),
    ),
    (
        WATCH_STRAP_TOKENS,
        WATCH_TARGET_TOKENS,
        ("ремеш", "браслет", "strap", "band"),
        ("ремеш", "браслет", "аксессуары для часов"),
        ("часы", "смарт-часы", "smart watch"),
        ("час", "watch"),
    ),
    (
        VACUUM_CONSUMABLE_TOKENS,
        VACUUM_TARGET_TOKENS,
        ("фильтр", "мешок", "насад", "щетк", "щётк", "filter", "nozzle", "brush"),
        ("аксессуары для пылесосов", "фильтр", "мешки", "насад"),
        ("пылесос", "vacuum"),
        ("пылесос", "vacuum"),
    ),
    (
        STICKER_INTENT_TOKENS,
        KEYBOARD_TARGET_TOKENS,
        ("стикер", "наклей", "этикет", "sticker", "label"),
        ("стикер", "наклей", "этикет"),
        ("клавиатур", "keyboard"),
        ("клавиатур", "keyboard"),
    ),
    (
        PASSPORT_COVER_TOKENS,
        PASSPORT_TARGET_TOKENS,
        ("облож", "чехол", "case", "cover"),
        ("облож", "чехл", "документ"),
        ("паспорт", "passport"),
        ("паспорт", "passport"),
    ),
)
QUERY_STOP_TOKENS = {
    "ва",
    "ваш",
    "для",
    "или",
    "на",
    "под",
    "при",
}
COMMON_LATIN_DESCRIPTOR_TOKENS = {
    "bar",
    "black",
    "blue",
    "case",
    "charger",
    "chocolate",
    "coffee",
    "cover",
    "cream",
    "drink",
    "green",
    "mini",
    "pink",
    "plus",
    "pro",
    "red",
    "shoes",
    "sneakers",
    "tea",
    "water",
    "white",
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
BALANCED_MARKETPLACE_CODES = ("uzum", "wildberries")
DEFAULT_MARKETPLACE_BALANCE_PAGE_SIZE = 10


def product_search_terms(
    *,
    title: str | None,
    description: str | None = None,
    brand: str | None,
    category_path_text: str | None,
    source_product_id: str | None,
) -> dict[str, int]:
    terms: dict[str, int] = {}
    _merge_terms(terms, tokenize(title), TITLE_WEIGHT)
    _merge_terms(terms, tokenize(brand), BRAND_WEIGHT)
    _merge_terms(terms, tokenize(description), DESCRIPTION_WEIGHT)
    _merge_terms(terms, tokenize(category_path_text), CATEGORY_WEIGHT)
    _merge_terms(terms, tokenize(source_product_id), SOURCE_ID_WEIGHT)
    _merge_terms(terms, semantic_terms(title), TITLE_WEIGHT)
    _merge_terms(terms, semantic_terms(brand), BRAND_WEIGHT)
    _merge_terms(terms, semantic_terms(description), DESCRIPTION_WEIGHT)
    _merge_terms(terms, semantic_terms(category_path_text), CATEGORY_WEIGHT)
    return terms


def product_search_text(
    *,
    title: str | None,
    description: str | None = None,
    brand: str | None,
    category_path_text: str | None,
    source_product_id: str | None,
) -> str:
    title_text = " ".join([title or ""] * 3)
    brand_text = " ".join([brand or ""] * 2)
    description_text = description or ""
    semantic_text = " ".join(
        [
            *semantic_terms(title),
            *semantic_terms(brand),
            *semantic_terms(description),
            *semantic_terms(category_path_text),
        ]
    )
    parts = [
        title_text,
        brand_text,
        description_text,
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
        description=product.description,
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
    allow_fallback: bool = True,
) -> list[int]:
    terms = query_terms(query)
    if not terms or limit <= 0:
        return []
    required_term_groups = protected_query_term_groups(query)

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
            required_term_groups=required_term_groups,
        )
        if rows or not allow_fallback:
            return rows

        # Trigram catches morphology and typos that exact token FTS misses.
        rows = _search_product_ids_postgres_trigram(
            query=query,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            required_term_groups=required_term_groups,
        )
        if rows:
            return rows

        # Human queries often mix product type with optional visual details. If the
        # full phrase has no exact hit, relax the weakest combinations before AI
        # expansion so "белая кружка с пейзажем" can still find white mugs.
        return _search_product_ids_postgres_relaxed(
            terms=terms,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            required_term_groups=required_term_groups,
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
    queryset = _filter_queryset_by_required_groups(queryset, required_term_groups)

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
    if rows or required_terms == 1 or not allow_fallback:
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


def balanced_marketplace_search_product_ids(
    query: str,
    *,
    active_only: bool,
    limit: int,
    page_size: int = DEFAULT_MARKETPLACE_BALANCE_PAGE_SIZE,
    min_price: Decimal | int | str | None = None,
    max_price: Decimal | int | str | None = None,
    marketplace_codes: tuple[str, ...] = BALANCED_MARKETPLACE_CODES,
) -> list[int]:
    """Return a marketplace-balanced ranked prefix for bot pagination.

    Each marketplace still contributes its own top-ranked search results. The
    blend only changes cross-marketplace interleaving so a larger catalog does
    not crowd out a smaller one when both have matching products.
    """
    if limit <= 0:
        return []

    bounded_limit = min(max(limit, 1), MAX_POSTGRES_CANDIDATES)
    ranked_by_marketplace = {
        marketplace_code: search_product_ids(
            query,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=bounded_limit,
            min_price=min_price,
            max_price=max_price,
            allow_fallback=False,
        )
        for marketplace_code in marketplace_codes
    }
    balanced_ids = balance_ranked_product_ids_by_marketplace(
        ranked_by_marketplace,
        limit=bounded_limit,
        page_size=page_size,
        marketplace_codes=marketplace_codes,
    )
    if balanced_ids:
        return balanced_ids

    fallback_by_marketplace = {
        marketplace_code: search_product_ids(
            query,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=bounded_limit,
            min_price=min_price,
            max_price=max_price,
        )
        for marketplace_code in marketplace_codes
    }
    balanced_fallback_ids = balance_ranked_product_ids_by_marketplace(
        fallback_by_marketplace,
        limit=bounded_limit,
        page_size=page_size,
        marketplace_codes=marketplace_codes,
    )
    if balanced_fallback_ids:
        return balanced_fallback_ids

    return search_product_ids(
        query,
        marketplace_code=None,
        active_only=active_only,
        limit=bounded_limit,
        min_price=min_price,
        max_price=max_price,
    )


def balance_ranked_product_ids_by_marketplace(
    ranked_by_marketplace: Mapping[str, list[int]],
    *,
    limit: int,
    page_size: int = DEFAULT_MARKETPLACE_BALANCE_PAGE_SIZE,
    marketplace_codes: Iterable[str] | None = None,
) -> list[int]:
    if limit <= 0:
        return []

    codes = _balance_marketplace_codes(ranked_by_marketplace, marketplace_codes)
    if not codes:
        return []

    seen_ids: set[int] = set()
    queues: dict[str, list[int]] = {}
    for code in codes:
        queue: list[int] = []
        for product_id in ranked_by_marketplace.get(code, []):
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            queue.append(product_id)
        queues[code] = queue

    page_size = max(1, min(page_size, limit))
    cursors = {code: 0 for code in codes}
    balanced_ids: list[int] = []

    while len(balanced_ids) < limit:
        page_limit = min(page_size, limit - len(balanced_ids))
        page_codes = [code for code in codes if cursors[code] < len(queues[code])]
        if not page_codes:
            break

        targets = _page_marketplace_targets(
            page_codes,
            page_limit=page_limit,
            queues=queues,
            cursors=cursors,
        )
        if not any(targets.values()):
            break

        while len(balanced_ids) < limit and any(targets.values()):
            progressed = False
            for code in page_codes:
                if targets[code] <= 0:
                    continue
                balanced_ids.append(queues[code][cursors[code]])
                cursors[code] += 1
                targets[code] -= 1
                progressed = True
                if len(balanced_ids) >= limit:
                    break
            if not progressed:
                break

    return balanced_ids


def _balance_marketplace_codes(
    ranked_by_marketplace: Mapping[str, list[int]],
    marketplace_codes: Iterable[str] | None,
) -> list[str]:
    codes: list[str] = []
    seen_codes: set[str] = set()
    for code in marketplace_codes or ():
        if code in seen_codes:
            continue
        codes.append(code)
        seen_codes.add(code)
    for code in ranked_by_marketplace:
        if code in seen_codes:
            continue
        codes.append(code)
        seen_codes.add(code)
    return [code for code in codes if ranked_by_marketplace.get(code)]


def _page_marketplace_targets(
    codes: list[str],
    *,
    page_limit: int,
    queues: dict[str, list[int]],
    cursors: dict[str, int],
) -> dict[str, int]:
    base_target, extra = divmod(page_limit, len(codes))
    targets = {
        code: base_target + (1 if index < extra else 0)
        for index, code in enumerate(codes)
    }

    deficit = 0
    for code in codes:
        available = len(queues[code]) - cursors[code]
        if targets[code] > available:
            deficit += targets[code] - available
            targets[code] = available

    while deficit > 0:
        progressed = False
        for code in codes:
            spare = len(queues[code]) - cursors[code] - targets[code]
            if spare <= 0:
                continue
            targets[code] += 1
            deficit -= 1
            progressed = True
            if deficit <= 0:
                break
        if not progressed:
            break

    return targets


def _filter_queryset_by_required_groups(queryset, required_term_groups: list[set[str]]):
    for group in required_term_groups:
        if group:
            queryset = queryset.filter(product__search_terms__term__in=group)
    return queryset


def query_terms(query: str) -> list[str]:
    tokens = tokenize(query)
    semantic = query_semantic_terms(query, tokens)
    skip_tokens = _query_skip_tokens(semantic, tokens)
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


def protected_query_term_groups(query: str) -> list[set[str]]:
    tokens = tokenize(query)
    token_set = set(tokens)
    has_latin = any(LATIN_RE.search(token) for token in token_set)
    has_cyrillic = any(re.search(r"[а-яё]", token, re.IGNORECASE) for token in token_set)

    groups: list[set[str]] = []
    seen_groups: set[tuple[str, ...]] = set()
    for token in tokens:
        if token in PROTECTED_QUERY_SYNONYMS:
            group = {value for value in PROTECTED_QUERY_SYNONYMS[token] if len(value) >= 3}
        elif has_latin and has_cyrillic:
            if not LATIN_RE.search(token) or token in COMMON_LATIN_DESCRIPTOR_TOKENS:
                continue
            group = {value for value in QUERY_SYNONYMS.get(token, {token}) if len(value) >= 3}
        else:
            continue
        if not group:
            continue
        key = tuple(sorted(group))
        if key in seen_groups:
            continue
        groups.append(group)
        seen_groups.add(key)
    return groups[:2]


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


def _query_skip_tokens(semantic: list[str], tokens: list[str] | None = None) -> set[str]:
    skip_tokens: set[str] = set(QUERY_STOP_TOKENS)
    token_set = set(tokens or [])
    if "sweater" in semantic:
        skip_tokens.update(SWEATER_TOKENS)
    if "compressionwear" in semantic:
        skip_tokens.update(COMPRESSION_TOKENS)
    if "vneck" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
        skip_tokens.update(V_NECK_HINT_TOKENS)
    elif "neckline" in semantic:
        skip_tokens.update(NECKLINE_TOKENS)
    if _has_generic_phone_accessory_query_intent(token_set):
        skip_tokens.update(GENERIC_PHONE_TOKENS)
    return skip_tokens


def _has_phone_case_query_intent(tokens: set[str]) -> bool:
    return bool(
        tokens & PHONE_CASE_TOKENS
        and tokens & GENERIC_PHONE_TOKENS
        and not tokens & STICKER_INTENT_TOKENS
    )


def _has_generic_phone_accessory_query_intent(tokens: set[str]) -> bool:
    return bool(
        tokens & PHONE_ACCESSORY_QUERY_TOKENS
        and tokens & GENERIC_PHONE_TOKENS
        and not tokens & STICKER_INTENT_TOKENS
    )


def _has_phone_accessory_query_intent(tokens: set[str]) -> bool:
    return bool(
        tokens & PHONE_ACCESSORY_QUERY_TOKENS
        and tokens & (GENERIC_PHONE_TOKENS | PHONE_TOKENS)
        and not tokens & STICKER_INTENT_TOKENS
    )


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
    required_term_groups: list[set[str]] | None = None,
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
        required_term_groups=required_term_groups,
    )


def _search_product_ids_postgres_trigram(
    *,
    query: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    min_price: Decimal | None,
    max_price: Decimal | None,
    required_term_groups: list[set[str]] | None = None,
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
        required_term_groups=required_term_groups,
    )


def _search_product_ids_postgres_relaxed(
    *,
    terms: list[str],
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    min_price: Decimal | None,
    max_price: Decimal | None,
    required_term_groups: list[set[str]] | None = None,
) -> list[int]:
    if len(terms) <= 1:
        return []

    min_term_count = 1 if len(terms) <= 3 else 2
    seen_queries: set[tuple[str, ...]] = set()
    for term_count in range(len(terms) - 1, min_term_count - 1, -1):
        for relaxed_terms in _relaxed_term_combinations(terms, term_count):
            key = tuple(relaxed_terms)
            if key in seen_queries:
                continue
            seen_queries.add(key)
            rows = _search_product_ids_postgres(
                terms=relaxed_terms,
                query=" ".join(relaxed_terms),
                marketplace_code=marketplace_code,
                active_only=active_only,
                limit=limit,
                min_price=min_price,
                max_price=max_price,
                required_term_groups=required_term_groups,
            )
            if rows:
                return rows
    return []


def _relaxed_term_combinations(terms: list[str], term_count: int) -> Iterable[list[str]]:
    if term_count >= len(terms):
        yield terms
        return
    if term_count <= 0:
        return

    # Drop later descriptive words first. In real user phrases the first words
    # usually contain the product type, while later words often describe color,
    # pattern, or noisy details that may not exist in the card title.
    if term_count == len(terms) - 1:
        for drop_index in range(len(terms) - 1, -1, -1):
            yield terms[:drop_index] + terms[drop_index + 1 :]
        return

    for start_index in range(0, len(terms) - term_count + 1):
        yield terms[start_index : start_index + term_count]


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
    required_term_groups: list[set[str]] | None = None,
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
    for group in required_term_groups or []:
        group_clauses = []
        for term in sorted(group):
            group_clauses.append("LOWER(p.search_text) ~ %s")
            params.append(_token_regex(term))
        if group_clauses:
            where_clauses.append(f"({' OR '.join(group_clauses)})")

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
    expressions: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if not term or term in seen:
            continue
        synonyms = sorted(QUERY_SYNONYMS.get(term, {term}))
        if len(synonyms) > 1:
            seen.update(synonyms)
            expressions.append("(" + " | ".join(f"{synonym}:*" for synonym in synonyms) + ")")
            continue
        seen.add(term)
        expressions.append(f"{term}:*")
    return operator.join(expressions)


def _token_regex(term: str) -> str:
    escaped = re.escape(term.lower())
    return rf"(^|[^0-9a-zа-яё]){escaped}([^0-9a-zа-яё]|$)"


def _postgres_intent_order_sql(query: str) -> str:
    tokens = set(tokenize(query))
    if _has_phone_case_query_intent(tokens):
        return """
            CASE
                WHEN p.title ILIKE '%%стикер%%'
                  OR p.title ILIKE '%%наклей%%'
                  OR p.title ILIKE '%%этикет%%'
                  OR p.category_path_text ILIKE '%%стикер%%'
                  OR p.category_path_text ILIKE '%%наклей%%'
                  OR p.category_path_text ILIKE '%%этикет%%'
                  OR p.category_path_text ILIKE '%%пленка%%'
                  OR p.category_path_text ILIKE '%%плёнка%%'
                THEN 5
                WHEN p.category_path_text ILIKE '%%аксессуары для смартфонов%%'
                THEN 0
                WHEN p.title ILIKE '%%телефон%%'
                  OR p.title ILIKE '%%смартфон%%'
                  OR p.title ILIKE '%%iphone%%'
                  OR p.title ILIKE '%%айфон%%'
                  OR p.title ILIKE '%%samsung%%'
                  OR p.title ILIKE '%%xiaomi%%'
                  OR p.title ILIKE '%%redmi%%'
                  OR p.title ILIKE '%%редми%%'
                THEN 1
                WHEN p.category_path_text ILIKE '%%планшет%%'
                  OR p.category_path_text ILIKE '%%кабел%%'
                  OR p.title ILIKE '%%ipad%%'
                THEN 4
                WHEN p.category_path_text ILIKE '%%чехл%%'
                  OR p.title ILIKE '%%чехол%%'
                  OR p.title ILIKE '%%чехлы%%'
                THEN 2
                ELSE 3
            END ASC,
        """
    if _has_phone_accessory_query_intent(tokens):
        return _postgres_phone_accessory_intent_order_sql(tokens)
    accessory_rule_sql = _postgres_accessory_target_intent_order_sql(tokens)
    if accessory_rule_sql:
        return accessory_rule_sql
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


def _postgres_phone_accessory_intent_order_sql(tokens: set[str]) -> str:
    accessory_condition = _sql_ilike_any("p.title", _phone_accessory_title_patterns(tokens))
    target_condition = _sql_ilike_any(
        "p.title",
        (
            "телефон",
            "смартфон",
            "iphone",
            "айфон",
            "samsung",
            "самсунг",
            "xiaomi",
            "сяоми",
            "redmi",
            "редми",
        ),
    )
    demote_condition = _sql_or(
        _phone_accessory_false_positive_condition(tokens),
        f"""
        (
            p.category_path_text ILIKE '%%смартфоны%%'
            AND p.category_path_text NOT ILIKE '%%аксессуар%%'
            AND NOT {accessory_condition}
        )
        """,
    )
    return f"""
        CASE
            WHEN {demote_condition}
            THEN 5
            WHEN p.category_path_text ILIKE '%%аксессуары для смартфонов%%'
              AND {accessory_condition}
            THEN 0
            WHEN {accessory_condition}
              AND {target_condition}
            THEN 1
            WHEN p.category_path_text ILIKE '%%аксессуары для смартфонов%%'
            THEN 2
            ELSE 3
        END ASC,
    """


def _postgres_accessory_target_intent_order_sql(tokens: set[str]) -> str:
    for (
        product_tokens,
        target_tokens,
        product_title_patterns,
        preferred_category_patterns,
        target_category_patterns,
        target_title_patterns,
    ) in ACCESSORY_TARGET_INTENT_RULES:
        if not (tokens & product_tokens and tokens & target_tokens):
            continue
        product_condition = _sql_ilike_any("p.title", product_title_patterns)
        preferred_category_condition = _sql_ilike_any(
            "p.category_path_text",
            preferred_category_patterns,
        )
        target_category_condition = _sql_ilike_any("p.category_path_text", target_category_patterns)
        target_title_condition = _sql_ilike_any("p.title", target_title_patterns)
        false_positive_condition = _accessory_target_false_positive_condition(tokens)
        return f"""
            CASE
                WHEN {false_positive_condition}
                THEN 5
                WHEN {preferred_category_condition}
                  AND {product_condition}
                THEN 0
                WHEN {product_condition}
                  AND {target_title_condition}
                THEN 1
                WHEN {target_category_condition}
                  AND NOT {preferred_category_condition}
                  AND NOT {product_condition}
                THEN 5
                WHEN {preferred_category_condition}
                THEN 2
                ELSE 3
            END ASC,
        """
    return ""


def _accessory_target_false_positive_condition(tokens: set[str]) -> str:
    conditions: list[str] = []
    if tokens & WATCH_STRAP_TOKENS and tokens & WATCH_TARGET_TOKENS:
        conditions.append(_sql_ilike_any("p.title", ("шарм", "подвеск")))
    return _sql_or(*conditions)


def _phone_accessory_title_patterns(tokens: set[str]) -> tuple[str, ...]:
    patterns: list[str] = []
    if tokens & PHONE_CASE_TOKENS:
        patterns.extend(("чехол", "чехлы", "case", "cover"))
    if tokens & PHONE_GLASS_TOKENS:
        patterns.extend(("стекл", "glass"))
    if tokens & PHONE_FILM_TOKENS:
        patterns.extend(("пленк", "плёнк", "film"))
    if tokens & PHONE_CHARGER_TOKENS:
        patterns.extend(("заряд", "адаптер", "блок", "charger", "adapter"))
    if tokens & PHONE_CABLE_TOKENS:
        patterns.extend(("кабел", "провод", "шнур", "usb", "type", "lightning", "cable"))
    if tokens & PHONE_HOLDER_TOKENS:
        patterns.extend(("держател", "подстав", "креплен", "holder", "stand"))
    return tuple(dict.fromkeys(patterns))


def _phone_accessory_false_positive_condition(tokens: set[str]) -> str:
    conditions: list[str] = []
    if tokens & PHONE_CASE_TOKENS:
        conditions.append(
            _sql_ilike_any(
                "p.title",
                ("стикер", "наклей", "этикет", "кабел", "заряд"),
            )
        )
        conditions.append(
            _sql_ilike_any(
                "p.category_path_text",
                ("стикер", "наклей", "этикет", "пленка самоклеящаяся", "плёнка самоклеящаяся"),
            )
        )
    if tokens & PHONE_GLASS_TOKENS:
        conditions.append(_sql_ilike_any("p.title", ("кружк", "стакан", "бокал", "посуда")))
        conditions.append(_sql_ilike_any("p.category_path_text", ("посуда", "кружк", "бокал")))
    if tokens & PHONE_FILM_TOKENS:
        conditions.append(
            _sql_ilike_any(
                "p.category_path_text",
                ("пленка самоклеящаяся", "плёнка самоклеящаяся", "наклей", "этикет"),
            )
        )
    return _sql_or(*conditions)


def _sql_ilike_any(field: str, fragments: Iterable[str]) -> str:
    clauses = [f"{field} ILIKE '%%{fragment}%%'" for fragment in fragments if fragment]
    if not clauses:
        return "FALSE"
    return "(" + " OR ".join(clauses) + ")"


def _sql_or(*conditions: str) -> str:
    clean_conditions = [condition.strip() for condition in conditions if condition.strip()]
    if not clean_conditions:
        return "FALSE"
    return "(" + " OR ".join(clean_conditions) + ")"


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
