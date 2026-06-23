import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from bot.config import Config
from bot.services.ai_reranker import (
    RESPONSES_API_URL,
    _extract_output_text,
    _is_quota_exhausted_response,
)
from bot.services.ai_runtime import ai_runtime_state
from bot.services.api_client import ProductDTO

logger = logging.getLogger(__name__)


class AIPhotoSearchError(RuntimeError):
    def __init__(self, message: str, *, quota_exhausted: bool = False) -> None:
        super().__init__(message)
        self.quota_exhausted = quota_exhausted


@dataclass(frozen=True, slots=True)
class PhotoSearchQuery:
    query: str
    alternative_queries: list[str]
    confidence: str
    visible_product: str
    object_type: str = ""
    brand: str = ""
    visible_text: str = ""
    key_features: list[str] | None = None


@dataclass(frozen=True, slots=True)
class PhotoVisualRankResult:
    ranked_ids: list[int]
    no_good_match: bool


async def identify_product_photo(
    *,
    image_bytes: bytes,
    mime_type: str,
    caption: str,
    config: Config,
) -> PhotoSearchQuery | None:
    if not _enabled(config):
        return None

    try:
        result = await _request_photo_search_query(
            image_bytes=image_bytes,
            mime_type=mime_type,
            caption=caption,
            config=config,
        )
    except AIPhotoSearchError as error:
        logger.warning("OpenAI photo product identification failed: %s", error)
        if error.quota_exhausted:
            ai_runtime_state.mark_quota_exhausted(str(error))
        return None

    if not result.query:
        return None
    return result


async def rerank_photo_products_by_image(
    *,
    image_bytes: bytes,
    mime_type: str,
    photo_query: PhotoSearchQuery,
    products: list[ProductDTO],
    config: Config,
) -> list[ProductDTO] | None:
    if not _enabled(config) or not config.openai_photo_visual_rerank_enabled:
        return products

    candidates = [product for product in products if product.cover_image_url][
        : max(1, config.openai_photo_visual_rerank_limit)
    ]
    if not candidates:
        return []

    try:
        result = await _request_photo_visual_rank(
            image_bytes=image_bytes,
            mime_type=mime_type,
            photo_query=photo_query,
            products=candidates,
            config=config,
        )
    except AIPhotoSearchError as error:
        logger.warning("OpenAI photo visual rerank failed: %s", error)
        if error.quota_exhausted:
            ai_runtime_state.mark_quota_exhausted(str(error))
        return None

    if result.no_good_match or not result.ranked_ids:
        return []

    by_id = {product.id: product for product in candidates}
    ranked = []
    seen_ids: set[int] = set()
    for product_id in result.ranked_ids:
        product = by_id.get(product_id)
        if product is None or product_id in seen_ids:
            continue
        ranked.append(product)
        seen_ids.add(product_id)
    return ranked


async def _request_photo_search_query(
    *,
    image_bytes: bytes,
    mime_type: str,
    caption: str,
    config: Config,
) -> PhotoSearchQuery:
    payload = {
        "model": config.openai_photo_model,
        "instructions": _instructions(),
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _user_prompt(caption),
                    },
                    {
                        "type": "input_image",
                        "image_url": _data_url(image_bytes, mime_type),
                        "detail": config.openai_photo_detail,
                    },
                ],
            }
        ],
        "max_output_tokens": config.openai_photo_max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "photo_product_search_query",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "query": {"type": "string"},
                        "alternative_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "visible_product": {"type": "string"},
                        "object_type": {"type": "string"},
                        "brand": {"type": "string"},
                        "visible_text": {"type": "string"},
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "query",
                        "alternative_queries",
                        "confidence",
                        "visible_product",
                        "object_type",
                        "brand",
                        "visible_text",
                        "key_features",
                    ],
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_photo_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(RESPONSES_API_URL, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise AIPhotoSearchError(
                        f"HTTP {response.status}: {body[:300]}",
                        quota_exhausted=_is_quota_exhausted_response(
                            status=response.status,
                            body=body,
                        ),
                    )
                data = json.loads(body)
    except (ClientError, TimeoutError, json.JSONDecodeError) as error:
        raise AIPhotoSearchError(str(error)) from error

    output_text = _extract_output_text(data)
    if not output_text:
        raise AIPhotoSearchError("empty model output")
    try:
        return parse_photo_search_output(output_text)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AIPhotoSearchError(f"invalid JSON output: {output_text[:300]}") from error


def parse_photo_search_output(output_text: str) -> PhotoSearchQuery:
    value = json.loads(output_text)
    if not isinstance(value, dict):
        raise TypeError("photo output must be an object")

    query = _clean_query(value.get("query"))
    alternatives = _clean_alternatives(value.get("alternative_queries"), query)
    confidence = str(value.get("confidence") or "low").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"

    visible_product = value.get("visible_product")
    object_type = value.get("object_type")
    brand = value.get("brand")
    visible_text = value.get("visible_text")
    key_features = value.get("key_features")
    return PhotoSearchQuery(
        query=query,
        alternative_queries=alternatives,
        confidence=confidence,
        visible_product=_short(visible_product if isinstance(visible_product, str) else "", 120),
        object_type=_short(object_type if isinstance(object_type, str) else "", 80),
        brand=_short(brand if isinstance(brand, str) else "", 80),
        visible_text=_short(visible_text if isinstance(visible_text, str) else "", 160),
        key_features=_clean_features(key_features),
    )


def _enabled(config: Config) -> bool:
    return bool(
        config.openai_photo_search_enabled
        and config.openai_api_key
        and ai_runtime_state.ai_allowed()
    )


def _instructions() -> str:
    return (
        "Ты превращаешь фото товара в точный поисковый запрос для каталога Uzum Market. "
        "Верни только JSON по схеме. Определи главный продаваемый товар на фото. "
        "Не выдумывай бренд, модель, материал, пол или назначение, если это не видно. "
        "Если видна упаковка, этикетка или логотип, распознай текст максимально точно: "
        "бренд, линейку, назначение, объем, вкус/аромат, SPF, модель. "
        "Бренд пиши как на упаковке, особенно латиницу: Snickers, CeraVe, Nivea. "
        "Не заменяй латинский бренд русской транскрипцией, если оригинальное написание видно. "
        "Рекламные слоганы и фразы без идентификации товара не добавляй в query; "
        "их можно указать только в visible_text. "
        "Сначала укажи бренд/модель или видимый текст, затем тип товара и ключевые "
        "визуальные признаки: цвет, форма, рисунок, крышка, ручка, трубочка, фасон, "
        "материал, объем, назначение. "
        "query должен быть на русском, 2-10 важных слов, без слов 'найди', 'купить', "
        "'похожий', 'товар'. alternative_queries - 0-3 коротких варианта с синонимами "
        "или английским/узбекским написанием, если это поможет поиску. "
        "Если на фото нет понятного товара для маркетплейса, верни пустой query, "
        "пустые alternative_queries и confidence='low'."
    )


def _user_prompt(caption: str) -> str:
    caption = " ".join(caption.split())[:160]
    if caption:
        return (
            "Определи товар на фото и составь поисковый запрос для БД. "
            f"Подсказка пользователя: {caption}"
        )
    return "Определи товар на фото и составь поисковый запрос для БД."


async def _request_photo_visual_rank(
    *,
    image_bytes: bytes,
    mime_type: str,
    photo_query: PhotoSearchQuery,
    products: list[ProductDTO],
    config: Config,
) -> PhotoVisualRankResult:
    payload = {
        "model": config.openai_photo_model,
        "instructions": _visual_rank_instructions(config.openai_photo_visual_rerank_min_score),
        "input": [
            {
                "role": "user",
                "content": _visual_rank_content(
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    photo_query=photo_query,
                    products=products,
                    config=config,
                ),
            }
        ],
        "max_output_tokens": max(350, config.openai_photo_max_output_tokens),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "photo_product_visual_rank",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "ranked_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "no_good_match": {"type": "boolean"},
                    },
                    "required": ["ranked_ids", "no_good_match"],
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_photo_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(RESPONSES_API_URL, json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise AIPhotoSearchError(
                        f"HTTP {response.status}: {body[:300]}",
                        quota_exhausted=_is_quota_exhausted_response(
                            status=response.status,
                            body=body,
                        ),
                    )
                data = json.loads(body)
    except (ClientError, TimeoutError, json.JSONDecodeError) as error:
        raise AIPhotoSearchError(str(error)) from error

    output_text = _extract_output_text(data)
    if not output_text:
        raise AIPhotoSearchError("empty model output")
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise AIPhotoSearchError(f"invalid JSON output: {output_text[:300]}") from error

    ranked_ids = parsed.get("ranked_ids")
    if not isinstance(ranked_ids, list):
        raise AIPhotoSearchError("ranked_ids is missing")
    return PhotoVisualRankResult(
        ranked_ids=[product_id for product_id in ranked_ids if isinstance(product_id, int)],
        no_good_match=bool(parsed.get("no_good_match")),
    )


def _visual_rank_content(
    *,
    image_bytes: bytes,
    mime_type: str,
    photo_query: PhotoSearchQuery,
    products: list[ProductDTO],
    config: Config,
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "task": "Rank candidate Uzum products by visual similarity to the user photo.",
                    "user_photo": {
                        "query": photo_query.query,
                        "object_type": photo_query.object_type,
                        "brand": photo_query.brand,
                        "visible_text": photo_query.visible_text,
                        "visible_product": photo_query.visible_product,
                        "key_features": photo_query.key_features or [],
                    },
                    "candidates": [_candidate_for_prompt(product) for product in products],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
        {
            "type": "input_image",
            "image_url": _data_url(image_bytes, mime_type),
            "detail": config.openai_photo_detail,
        },
    ]
    for product in products:
        content.extend(
            [
                {
                    "type": "input_text",
                    "text": f"Candidate product_id={product.id}",
                },
                {
                    "type": "input_image",
                    "image_url": product.cover_image_url or "",
                    "detail": "low",
                },
            ]
        )
    return content


def _visual_rank_instructions(min_score: int) -> str:
    return (
        "Ты работаешь как экономный Google Lens для Uzum Market. "
        "Первое изображение - фото пользователя. Остальные изображения идут парами "
        "после текста Candidate product_id=... и являются обложками карточек. "
        "Верни только JSON по схеме. Нужно выбрать только товары, которые визуально "
        "похожи на фото пользователя, а не просто из той же категории. "
        "Если на фото читается бренд или логотип, кандидат с другим брендом или без "
        "этого бренда в названии/бренде не является точным совпадением. "
        "Для упаковок и косметики бренд, читаемый текст, цвет упаковки, форма флакона, "
        "крышка, этикетка и объем важнее общей категории. Крем другого бренда или с "
        "другой упаковкой не подходит. "
        "Для посуды сравнивай форму, материал, цвет, рисунок, крышку, трубочку, ручку "
        "и объем. Обычная кружка не подходит, если на фото кружка с крышкой/трубочкой "
        "или специфичным декором. "
        "Для одежды сравнивай тип вещи, крой, цвет, вырез, длину, рукава, материал "
        "и принт. "
        "Если видимого совпадения нет, верни ranked_ids=[] и no_good_match=true. "
        f"В ranked_ids включай только кандидатов с примерной похожестью не ниже {min_score}/100. "
        "Сортируй от самого похожего к менее похожему. Используй только переданные id."
    )


def _candidate_for_prompt(product: ProductDTO) -> dict[str, Any]:
    return {
        "id": product.id,
        "title": _short(product.title, 160),
        "brand": _short(product.brand, 80),
        "category": _short(product.category_path_text, 120),
        "price": product.current_price,
        "rating": product.rating,
        "reviews_count": product.reviews_count,
    }


def _data_url(image_bytes: bytes, mime_type: str) -> str:
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{image_base64}"


def _clean_alternatives(value: Any, query: str) -> list[str]:
    if not isinstance(value, list):
        return []

    alternatives: list[str] = []
    seen = {query.casefold()} if query else set()
    for item in value:
        cleaned = _clean_query(item)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        alternatives.append(cleaned)
        seen.add(key)
        if len(alternatives) >= 3:
            break
    return alternatives


def _clean_query(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _short(" ".join(value.split()), 120)


def _clean_features(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    features = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = _short(" ".join(item.split()), 60)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        features.append(cleaned)
        seen.add(key)
        if len(features) >= 8:
            break
    return features


def _short(value: str | None, max_length: int) -> str:
    if not value:
        return ""
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."
