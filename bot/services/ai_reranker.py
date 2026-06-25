import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from bot.config import Config
from bot.services.ai_runtime import ai_runtime_state
from bot.services.api_client import ProductDTO

logger = logging.getLogger(__name__)

RESPONSES_API_URL = "https://api.openai.com/v1/responses"
OPENAI_PROBE_MAX_OUTPUT_TOKENS = 16


class AIRerankError(RuntimeError):
    def __init__(self, message: str, *, quota_exhausted: bool = False) -> None:
        super().__init__(message)
        self.quota_exhausted = quota_exhausted


@dataclass(frozen=True, slots=True)
class OpenAIProbeResult:
    ok: bool
    quota_exhausted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SearchExpansion:
    query: str
    min_price: int | None = None
    max_price: int | None = None


@dataclass(frozen=True, slots=True)
class SearchQueryUnderstanding:
    query: str
    search_queries: list[SearchExpansion]
    source: str


@dataclass(frozen=True, slots=True)
class ProductRankResult:
    products: list[ProductDTO]
    should_expand: bool
    search_queries: list[SearchExpansion]


async def rerank_products(
    *,
    query: str,
    products: list[ProductDTO],
    config: Config,
) -> list[ProductDTO]:
    result = await rank_products(
        query=query,
        products=products,
        config=config,
        expansion_allowed=False,
    )
    return result.products


async def understand_search_query(
    *,
    query: str,
    config: Config,
    force_ai: bool = False,
) -> SearchQueryUnderstanding:
    normalized_query = _compact_text(query, 500)
    needs_understanding = _query_needs_understanding(normalized_query)
    if not normalized_query or (not force_ai and not needs_understanding):
        return SearchQueryUnderstanding(
            query=normalized_query,
            search_queries=[SearchExpansion(normalized_query)] if normalized_query else [],
            source="original",
        )

    fallback = (
        _local_query_understanding(normalized_query)
        if needs_understanding
        else SearchQueryUnderstanding(
            query=normalized_query,
            search_queries=[SearchExpansion(normalized_query)],
            source="original",
        )
    )
    if not _enabled(config) or not config.openai_search_expand_enabled:
        return fallback

    try:
        ai_result = await _request_query_understanding(query=normalized_query, config=config)
    except AIRerankError as error:
        logger.warning("OpenAI query understanding failed: %s", error)
        if error.quota_exhausted:
            ai_runtime_state.mark_quota_exhausted(str(error))
        return fallback

    return ai_result or fallback


async def rank_products(
    *,
    query: str,
    products: list[ProductDTO],
    config: Config,
    expansion_allowed: bool,
) -> ProductRankResult:
    if not _enabled(config) or (len(products) <= 1 and not expansion_allowed):
        return ProductRankResult(products=products, should_expand=False, search_queries=[])

    try:
        ai_result = await _request_rank_result(
            query=query,
            products=_products_for_model(products, config),
            config=config,
            expansion_allowed=expansion_allowed,
        )
    except AIRerankError as error:
        logger.warning("OpenAI product rerank failed: %s", error)
        if error.quota_exhausted:
            ai_runtime_state.mark_quota_exhausted(str(error))
        return ProductRankResult(products=products, should_expand=False, search_queries=[])

    ranked = _rank_products_from_ids(products=products, ranked_ids=ai_result["ranked_ids"])
    return ProductRankResult(
        products=ranked,
        should_expand=ai_result["should_expand"],
        search_queries=ai_result["search_queries"],
    )


def _rank_products_from_ids(
    *,
    products: list[ProductDTO],
    ranked_ids: list[int],
) -> list[ProductDTO]:
    by_id = {product.id: product for product in products}
    ranked: list[ProductDTO] = []
    seen_ids: set[int] = set()
    for product_id in ranked_ids:
        product = by_id.get(product_id)
        if product is None or product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        ranked.append(product)

    ranked.extend(product for product in products if product.id not in seen_ids)
    return ranked


async def _request_rank_result(
    *,
    query: str,
    products: list[ProductDTO],
    config: Config,
    expansion_allowed: bool,
) -> dict[str, Any]:
    payload = {
        "model": config.openai_model,
        "instructions": _instructions(),
        "input": json.dumps(
            {
                "query": query,
                "expansion_allowed": expansion_allowed,
                "products": [_product_for_prompt(product) for product in products],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "max_output_tokens": config.openai_max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "product_rerank",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "ranked_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "should_expand": {"type": "boolean"},
                        "search_queries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "query": {"type": "string"},
                                    "min_price": {"type": ["integer", "null"]},
                                    "max_price": {"type": ["integer", "null"]},
                                },
                                "required": ["query", "min_price", "max_price"],
                            },
                        }
                    },
                    "required": ["ranked_ids", "should_expand", "search_queries"],
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(RESPONSES_API_URL, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise AIRerankError(
                        f"HTTP {response.status}: {body[:300]}",
                        quota_exhausted=_is_quota_exhausted_response(
                            status=response.status,
                            body=body,
                        ),
                    )
                data = json.loads(body)
    except (ClientError, TimeoutError, json.JSONDecodeError) as error:
        raise AIRerankError(str(error)) from error

    output_text = _extract_output_text(data)
    if not output_text:
        raise AIRerankError("empty model output")
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise AIRerankError(f"invalid JSON output: {output_text[:300]}") from error

    ranked_ids = parsed.get("ranked_ids")
    if not isinstance(ranked_ids, list):
        raise AIRerankError("ranked_ids is missing")
    return {
        "ranked_ids": [product_id for product_id in ranked_ids if isinstance(product_id, int)],
        "should_expand": bool(parsed.get("should_expand")),
        "search_queries": _parse_search_expansions(
            parsed.get("search_queries"),
            max_queries=config.openai_search_expand_max_queries,
        ),
    }


async def _request_query_understanding(
    *,
    query: str,
    config: Config,
) -> SearchQueryUnderstanding | None:
    payload = {
        "model": config.openai_model,
        "instructions": _query_understanding_instructions(),
        "input": json.dumps(
            {"query": query},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "max_output_tokens": min(max(160, config.openai_max_output_tokens), 320),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "product_query_understanding",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary_query": {"type": "string"},
                        "search_queries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "query": {"type": "string"},
                                    "min_price": {"type": ["integer", "null"]},
                                    "max_price": {"type": ["integer", "null"]},
                                },
                                "required": ["query", "min_price", "max_price"],
                            },
                        },
                    },
                    "required": ["primary_query", "search_queries"],
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(RESPONSES_API_URL, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise AIRerankError(
                        f"HTTP {response.status}: {body[:300]}",
                        quota_exhausted=_is_quota_exhausted_response(
                            status=response.status,
                            body=body,
                        ),
                    )
                data = json.loads(body)
    except (ClientError, TimeoutError, json.JSONDecodeError) as error:
        raise AIRerankError(str(error)) from error

    output_text = _extract_output_text(data)
    if not output_text:
        raise AIRerankError("empty model output")
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise AIRerankError(f"invalid JSON output: {output_text[:300]}") from error

    primary_query = _clean_query(parsed.get("primary_query"))
    expansions = _parse_search_expansions(
        parsed.get("search_queries"),
        max_queries=config.openai_search_expand_max_queries,
    )
    if not primary_query and expansions:
        primary_query = expansions[0].query
    if not primary_query:
        return None
    return SearchQueryUnderstanding(
        query=primary_query,
        search_queries=_dedupe_expansions([SearchExpansion(primary_query), *expansions]),
        source="ai",
    )


def _enabled(config: Config) -> bool:
    return bool(
        config.openai_rerank_enabled
        and config.openai_api_key
        and ai_runtime_state.ai_allowed()
    )


async def probe_openai_availability(config: Config) -> OpenAIProbeResult:
    if not config.openai_api_key:
        return OpenAIProbeResult(ok=False, quota_exhausted=False, reason="OPENAI_API_KEY missing")

    payload = {
        "model": config.openai_model,
        "input": "Reply with OK.",
        "max_output_tokens": OPENAI_PROBE_MAX_OUTPUT_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(RESPONSES_API_URL, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    quota_exhausted = _is_quota_exhausted_response(
                        status=response.status,
                        body=body,
                    )
                    return OpenAIProbeResult(
                        ok=False,
                        quota_exhausted=quota_exhausted,
                        reason=f"HTTP {response.status}: {body[:300]}",
                    )
                return OpenAIProbeResult(ok=True, quota_exhausted=False, reason="")
    except (ClientError, TimeoutError) as error:
        return OpenAIProbeResult(ok=False, quota_exhausted=False, reason=str(error))


def _instructions() -> str:
    return (
        "Ты ранжируешь товары маркетплейса под запрос пользователя и проверяешь, "
        "достаточно ли хороши кандидаты локального поиска. "
        "Верни только JSON по схеме. Используй только переданные product.id. "
        "Сначала ставь товары, которые точно соответствуют намерению запроса. "
        "Уточняющие признаки из запроса считаются обязательными: форма выреза, цвет, пол, "
        "размер, материал, сезонность и тип товара. "
        "Если пользователь просит V/v-образный вырез, товары с круглым, квадратным, "
        "лодочкой или без указанного V-выреза должны быть ниже товаров с V-вырезом. "
        "Если пользователь ищет основной товар, не поднимай аксессуары выше самого товара. "
        "Если пользователь ищет аксессуар, наоборот поднимай аксессуары. "
        "При близкой релевантности предпочитай лучшую цену, высокий рейтинг и больше отзывов. "
        "Если продукты не соответствуют обязательным признакам, слишком общие, "
        "или их мало, выставь should_expand=true. "
        "Если expansion_allowed=false, всегда верни should_expand=false и пустой search_queries. "
        "Когда should_expand=true, предложи 1-3 коротких поисковых запроса для локального "
        "индекса, которые могут достать правильные товары из БД. "
        "Запросы должны содержать только важные слова товара и обязательных признаков, "
        "без слов 'найди', 'купить', 'недорогой', 'до', 'тысяч'. "
        "Цены вроде 'до 300 тысяч', 'дешевле 100к' переносись в max_price числом в UZS. "
        "Добавляй варианты написания: слитно/раздельно, русский/английский, дефисы. "
        "Не выдумывай характеристики, которых нет в данных."
    )


def _query_understanding_instructions() -> str:
    return (
        "Ты превращаешь человеческое описание или историю в короткие поисковые запросы "
        "для маркетплейса. Верни только JSON по схеме. "
        "Главная задача: извлечь товар, который пользователь хочет найти, и обязательные "
        "атрибуты: тип товара, цвет, материал, форма, назначение, бренд, размер. "
        "Игнорируй путешествия, эмоции, место воспоминания, слова 'хочу', 'видел', "
        "'не знаю', 'красивый', если они не описывают товар. "
        "primary_query должен быть на русском, 2-7 слов, без лишней истории и без слов "
        "'купить', 'найди', 'покажи'. "
        "Если материал неизвестен, сохрани общий материал из описания: например "
        "'зеленая каменная тарелка', а вероятные названия материала вроде 'оникс' "
        "или 'малахит' добавляй только в дополнительные search_queries. "
        "Для рассказа про зеленую тарелку из зеленого камня с кольцами суть запроса: "
        "'зеленая каменная тарелка'. "
        "Если запрос уже короткий и прямой, сохрани его смысл, но добавь полезные "
        "варианты написания, перевода, транслитерации и категории товара. Например, "
        "'виндовс 10' можно расширить до запросов про Windows 10, Windows 10 Pro "
        "и лицензионный ключ, если это подходит намерению пользователя. "
        "search_queries: 1-3 коротких варианта для поиска в БД; не выдумывай бренд. "
        "Если в запросе есть цена, перенеси ее в min_price/max_price числом в UZS."
    )


def _product_for_prompt(product: ProductDTO) -> dict[str, Any]:
    return {
        "id": product.id,
        "title": _short(product.title, 140),
        "brand": _short(product.brand, 60),
        "category": _short(product.category_path_text, 100),
        "price": product.current_price,
        "old_price": product.old_price,
        "currency": product.currency,
        "rating": product.rating,
        "reviews_count": product.reviews_count,
    }


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    chunks: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _parse_search_expansions(
    value: Any,
    *,
    max_queries: int,
) -> list[SearchExpansion]:
    if not isinstance(value, list) or max_queries <= 0:
        return []

    expansions: list[SearchExpansion] = []
    seen_queries: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        query = _clean_query(item.get("query"))
        if not query:
            continue
        query_key = query.casefold()
        if query_key in seen_queries:
            continue

        min_price = _clean_price(item.get("min_price"))
        max_price = _clean_price(item.get("max_price"))
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = None, None

        seen_queries.add(query_key)
        expansions.append(
            SearchExpansion(query=query, min_price=min_price, max_price=max_price)
        )
        if len(expansions) >= max_queries:
            break
    return expansions


def _query_needs_understanding(query: str) -> bool:
    tokens = _tokens(query)
    if len(tokens) >= 14:
        return True
    normalized = query.casefold()
    if len(query) >= 90:
        return True
    sentence_marks = normalized.count(".") + normalized.count("!") + normalized.count("?")
    return sentence_marks >= 1 and bool(_NARRATIVE_MARKER_RE.search(normalized))


def _local_query_understanding(query: str) -> SearchQueryUnderstanding:
    tokens = _tokens(query)
    useful: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        normalized = _NARRATIVE_TOKEN_ALIASES.get(token, token)
        if normalized in _NARRATIVE_STOP_TOKENS or normalized.isdigit():
            continue
        if len(normalized) <= 2 and normalized not in {"v"}:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        useful.append(normalized)

    product_tokens = [token for token in useful if token in _PRODUCT_OBJECT_TOKENS]
    color_tokens = [token for token in useful if token in _COLOR_TOKENS]
    material_tokens = [token for token in useful if token in _MATERIAL_TOKENS]
    descriptor_tokens = [
        token
        for token in useful
        if token not in {*product_tokens, *color_tokens, *material_tokens}
    ]

    primary_parts = [*color_tokens[:1], *product_tokens[:1], *material_tokens[:1]]
    if not primary_parts:
        primary_parts = useful[:6]
    elif not product_tokens and descriptor_tokens:
        primary_parts.append(descriptor_tokens[0])
    primary_query = " ".join(primary_parts) or query

    extra_queries = [SearchExpansion(primary_query)]
    if product_tokens and color_tokens and material_tokens:
        extra_queries.append(
            SearchExpansion(" ".join([product_tokens[0], color_tokens[0], material_tokens[0]]))
        )
    if product_tokens and color_tokens:
        extra_queries.append(SearchExpansion(" ".join([color_tokens[0], product_tokens[0]])))
    if "камень" in material_tokens and product_tokens and color_tokens:
        for stone in ("оникс", "малахит"):
            extra_queries.append(SearchExpansion(" ".join([product_tokens[0], stone])))
            extra_queries.append(
                SearchExpansion(" ".join([color_tokens[0], product_tokens[0], stone]))
            )

    return SearchQueryUnderstanding(
        query=primary_query,
        search_queries=_dedupe_expansions(
            extra_queries,
            max_queries=3,
        ),
        source="local",
    )


def _dedupe_expansions(
    expansions: list[SearchExpansion],
    *,
    max_queries: int | None = None,
) -> list[SearchExpansion]:
    deduped: list[SearchExpansion] = []
    seen: set[str] = set()
    for expansion in expansions:
        query = _clean_query(expansion.query)
        key = query.casefold()
        if not query or key in seen:
            continue
        seen.add(key)
        deduped.append(
            SearchExpansion(
                query=query,
                min_price=expansion.min_price,
                max_price=expansion.max_price,
            )
        )
        if max_queries is not None and len(deduped) >= max_queries:
            break
    return deduped


def _is_quota_exhausted_response(*, status: int, body: str) -> bool:
    if status not in {403, 429}:
        return False

    error_code = ""
    error_type = ""
    message = body
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {}

    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        error_code = str(error.get("code") or "").lower()
        error_type = str(error.get("type") or "").lower()
        message = str(error.get("message") or body)

    normalized_message = message.lower()
    if error_code in {
        "billing_hard_limit_reached",
        "insufficient_quota",
        "unsupported_country_region_territory",
    }:
        return True
    if error_type in {"insufficient_quota", "billing_error"}:
        return True
    if "rate limit" in normalized_message and "quota" not in normalized_message:
        return False
    return any(
        marker in normalized_message
        for marker in (
            "exceeded your current quota",
            "check your plan and billing",
            "run out of credits",
            "consumed all your credits",
            "monthly spend",
            "usage limit",
            "billing details",
            "country, region, or territory not supported",
        )
    )


def _products_for_model(products: list[ProductDTO], config: Config) -> list[ProductDTO]:
    max_products = max(1, config.openai_rerank_max_products)
    return products[:max_products]


def _clean_query(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:120]


def _clean_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        return None
    if parsed <= 0:
        return None
    return min(parsed, 1_000_000_000)


def _compact_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"


def _short(value: str | None, max_length: int) -> str | None:
    if not value:
        return None
    value = value.strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9a-zа-яё]+", value.casefold())


_NARRATIVE_MARKER_RE = re.compile(
    r"\b(?:я|мы|видел\w*|увидел\w*|хочу|хотел\w*|нужн\w*|похож\w*|"
    r"не\s+знаю|как\s+то|когда|где|помню)\b",
    re.IGNORECASE,
)

_NARRATIVE_STOP_TOKENS = {
    "а",
    "бы",
    "был",
    "была",
    "были",
    "было",
    "в",
    "во",
    "где",
    "для",
    "домой",
    "его",
    "ее",
    "её",
    "если",
    "за",
    "и",
    "из",
    "или",
    "интересного",
    "как",
    "какой",
    "когда",
    "которую",
    "который",
    "которым",
    "красивая",
    "красивое",
    "красивой",
    "красивую",
    "красивый",
    "мне",
    "мы",
    "на",
    "не",
    "но",
    "он",
    "она",
    "оно",
    "очень",
    "похожий",
    "похожую",
    "похожая",
    "помню",
    "с",
    "себе",
    "словно",
    "так",
    "там",
    "то",
    "турции",
    "увидел",
    "увидела",
    "хотел",
    "хотела",
    "хочу",
    "что",
    "это",
    "эта",
    "эту",
    "я",
}

_NARRATIVE_TOKEN_ALIASES = {
    "камня": "камень",
    "камнем": "камень",
    "каменная": "камень",
    "каменной": "камень",
    "каменную": "камень",
    "каменный": "камень",
    "тарелка": "тарелка",
    "тарелке": "тарелка",
    "тарелки": "тарелка",
    "тарелкой": "тарелка",
    "тарелку": "тарелка",
    "зеленого": "зеленая",
    "зеленой": "зеленая",
    "зеленую": "зеленая",
    "зеленый": "зеленая",
    "зелёного": "зеленая",
    "зелёной": "зеленая",
    "зелёную": "зеленая",
    "зелёный": "зеленая",
}

_PRODUCT_OBJECT_TOKENS = {
    "ботинки",
    "брюки",
    "ваза",
    "кружка",
    "куртка",
    "лампа",
    "ноутбук",
    "платье",
    "постер",
    "рубашка",
    "светильник",
    "свитер",
    "смартфон",
    "стол",
    "стул",
    "сумка",
    "тарелка",
    "телефон",
    "чашка",
    "чехол",
}

_COLOR_TOKENS = {
    "бежевый",
    "белая",
    "белый",
    "голубой",
    "желтая",
    "желтый",
    "зеленая",
    "зеленый",
    "коричневый",
    "красная",
    "красный",
    "розовый",
    "серая",
    "серый",
    "синий",
    "черная",
    "черный",
}

_MATERIAL_TOKENS = {
    "дерево",
    "золото",
    "камень",
    "керамика",
    "кожа",
    "металл",
    "мрамор",
    "оникс",
    "пластик",
    "серебро",
    "стекло",
    "ткань",
    "фарфор",
}
