import logging
import re
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, Message

from bot.config import Config
from bot.keyboards.main_menu import is_more_button_text, main_menu_keyboard, more_results_keyboard
from bot.locales import format_message, language_from_message
from bot.services.ai_reranker import SearchExpansion, rank_products, rerank_products
from bot.services.api_client import (
    ProductDTO,
    ServerAPIClient,
    ServerAPIError,
    render_product_card,
    render_products,
)
from bot.services.search_state import SearchSession, search_state

router = Router(name="common")
logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
V_NECK_RE = re.compile(
    r"(?<![0-9a-zа-яё])v\s*[-–—]?\s*(?:образн\w*|вырез\w*)"
    r"|(?<![0-9a-zа-яё])v[-\s]?neck(?![0-9a-zа-яё])"
    r"|треугольн\w*\s+вырез\w*",
    re.IGNORECASE,
)
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
NECKLINE_TOKENS = {
    "горловина",
    "горловиной",
    "вырез",
    "выреза",
    "вырезом",
    "вырезы",
    "вырезами",
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
QUERY_STOP_TOKENS = {
    "для",
    "купить",
    "найди",
    "нужен",
    "нужна",
    "нужно",
    "товар",
    "товары",
}
REQUIREMENT_VNECK = "__vneck__"
REQUIREMENT_SWEATER = "__sweater__"
REQUIREMENT_COMPRESSION_WEAR = "__compressionwear__"


@router.guest_message(F.text)
async def guest_search_uzum(message: Message, config: Config) -> None:
    if not config.guest_search_enabled:
        return
    language = language_from_message(message)

    guest_query_id = message.guest_query_id
    if not guest_query_id:
        logger.warning("Guest message without guest_query_id: %s", message.message_id)
        return

    query = await _guest_query_text(message)
    if not query:
        await _answer_guest_query(
            message,
            guest_query_id=guest_query_id,
            title=format_message("guest_need_query_title", language, html=False),
            text=format_message("guest_need_query_text", language),
        )
        return

    ranked_products = await _load_ranked_candidates(
        query=query,
        candidate_offset=0,
        config=config,
        message=None,
    )
    if ranked_products is None:
        await _answer_guest_query(
            message,
            guest_query_id=guest_query_id,
            title=format_message("guest_catalog_unavailable_title", language, html=False),
            text=format_message("guest_catalog_unavailable_text", language),
        )
        return

    products = ranked_products[: config.product_search_limit]
    await _answer_guest_query(
        message,
        guest_query_id=guest_query_id,
        title=_guest_result_title(query, products, language),
        text=render_products(products, query, language),
        description=_guest_result_description(products, language),
        thumbnail_url=_guest_thumbnail_url(products),
    )


def _is_more_button(message: Message) -> bool:
    return is_more_button_text(message.text)


@router.message(_is_more_button)
async def search_more(message: Message, config: Config) -> None:
    language = language_from_message(message)
    session = search_state.get(chat_id=message.chat.id, user_id=_user_id(message))
    if session is None:
        await message.answer(
            format_message("no_session", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    products = await _next_products(session=session, config=config, message=message)
    if products is None:
        return
    if not products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await message.answer(
            format_message("no_more", language, query=session.query),
            reply_markup=main_menu_keyboard(language),
        )
        return

    search_state.set(
        chat_id=message.chat.id,
        user_id=_user_id(message),
        query=session.query,
        products=session.products,
        offset=session.offset + len(products),
        candidate_offset=session.candidate_offset,
    )
    await _send_products(message, products, start_index=session.offset + 1, language_code=language)


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    language = language_from_message(message)
    query = (message.text or "").strip()
    if not query:
        await message.answer(
            format_message("empty_query", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    ranked_products = await _load_ranked_candidates(
        query=query,
        candidate_offset=0,
        config=config,
        message=message,
    )
    if ranked_products is None:
        return
    if not ranked_products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await message.answer(
            format_message("no_results", language, query=query),
            reply_markup=main_menu_keyboard(language),
        )
        return

    products = ranked_products[: config.product_search_limit]
    search_state.set(
        chat_id=message.chat.id,
        user_id=_user_id(message),
        query=query,
        products=ranked_products,
        offset=len(products),
        candidate_offset=len(ranked_products),
    )
    await message.answer(
        format_message("found_intro", language, query=query, count=len(products)),
        reply_markup=more_results_keyboard(language),
    )
    await _send_products(message, products, start_index=1, language_code=language)


async def _next_products(
    *,
    session: SearchSession,
    config: Config,
    message: Message,
) -> list[ProductDTO] | None:
    products = session.products[session.offset : session.offset + config.product_search_limit]
    if products:
        return products

    next_products = await _load_ranked_candidates(
        query=session.query,
        candidate_offset=session.candidate_offset,
        config=config,
        message=message,
    )
    if next_products is None:
        return None
    if not next_products:
        return []

    session.products.extend(next_products)
    session.candidate_offset += len(next_products)
    return session.products[session.offset : session.offset + config.product_search_limit]


async def _load_ranked_candidates(
    *,
    query: str,
    candidate_offset: int,
    config: Config,
    message: Message | None,
) -> list[ProductDTO] | None:
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            products = await client.search_products(
                query=query,
                limit=_initial_candidate_limit(config, candidate_offset),
                offset=candidate_offset,
            )
            if not _should_use_ai_rerank(
                query=query,
                products=products,
                config=config,
                candidate_offset=candidate_offset,
            ):
                return products

            candidate_limit = _candidate_limit(config)
            if len(products) < candidate_limit:
                products = await client.search_products(
                    query=query,
                    limit=candidate_limit,
                    offset=candidate_offset,
                )
            ranked_result = await rank_products(
                query=query,
                products=products,
                config=config,
                expansion_allowed=_search_expansion_allowed(
                    config=config,
                    candidate_offset=candidate_offset,
                ),
            )
            if ranked_result.should_expand and ranked_result.search_queries:
                expanded_products = await _load_expanded_products(
                    client=client,
                    expansions=ranked_result.search_queries,
                    config=config,
                )
                merged_products = _merge_unique_products(products, expanded_products)
                if len(merged_products) > len(products):
                    logger.info(
                        "Expanded product search for query %r from %d to %d candidates.",
                        query,
                        len(products),
                        len(merged_products),
                    )
                    return await rerank_products(
                        query=query,
                        products=merged_products,
                        config=config,
                    )
    except ServerAPIError as error:
        logger.warning("Product search failed for query %r: %s", query, error)
        if message is not None:
            language = language_from_message(message)
            await message.answer(
                format_message("catalog_unavailable", language),
                disable_web_page_preview=True,
                reply_markup=main_menu_keyboard(language),
            )
        return None

    return ranked_result.products


def _candidate_limit(config: Config) -> int:
    if config.openai_rerank_enabled and config.openai_api_key:
        return max(config.product_search_limit, config.openai_candidate_limit)
    return config.product_search_limit


def _initial_candidate_limit(config: Config, candidate_offset: int) -> int:
    if (
        candidate_offset == 0
        and config.openai_rerank_enabled
        and config.openai_api_key
        and config.openai_rerank_fallback_only
    ):
        return config.product_search_limit
    return _candidate_limit(config)


def _should_use_ai_rerank(
    *,
    query: str,
    products: list[ProductDTO],
    config: Config,
    candidate_offset: int,
) -> bool:
    if not config.openai_rerank_enabled or not config.openai_api_key:
        return False
    if not config.openai_rerank_fallback_only:
        return True
    if candidate_offset != 0:
        return False
    return _local_results_need_ai(query, products, min_results=config.product_search_limit)


def _local_results_need_ai(
    query: str,
    products: list[ProductDTO],
    *,
    min_results: int,
) -> bool:
    if len(products) < min_results:
        return True

    requirements = _query_requirements(query)
    if not requirements:
        return False

    top_products = products[:min_results]
    full_matches = 0
    partial_scores = 0.0
    for product in top_products:
        score = _product_requirement_score(product, requirements)
        partial_scores += score
        if score >= 0.999:
            full_matches += 1

    required_full_matches = 2 if len(requirements) > 1 else 3
    return full_matches < required_full_matches and partial_scores / len(top_products) < 0.75


def _query_requirements(query: str) -> list[set[str]]:
    tokens = _query_tokens(query)
    token_set = set(tokens)
    skip_tokens = _price_skip_tokens(tokens) | PRICE_STOP_TOKENS | QUERY_STOP_TOKENS
    requirements: list[set[str]] = []

    if token_set & SWEATER_TOKENS:
        requirements.append({REQUIREMENT_SWEATER})
        skip_tokens.update(SWEATER_TOKENS)
    if _query_has_v_neck(query, token_set):
        requirements.append({REQUIREMENT_VNECK})
        skip_tokens.update(V_NECK_HINT_TOKENS)
        skip_tokens.update(NECKLINE_TOKENS)
    if _has_compression_term(token_set):
        requirements.append({REQUIREMENT_COMPRESSION_WEAR})
        skip_tokens.update(COMPRESSION_TOKENS)

    for token in tokens:
        if token in skip_tokens or token.isdigit():
            continue
        if token in {"iphone", "айфон"}:
            requirements.append({"iphone", "айфон"})
            skip_tokens.update({"iphone", "айфон"})
            continue
        requirements.append({token})

    deduped: list[set[str]] = []
    seen: set[tuple[str, ...]] = set()
    for requirement in requirements:
        key = tuple(sorted(requirement))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(requirement)
    return deduped[:6]


def _product_requirement_score(product: ProductDTO, requirements: list[set[str]]) -> float:
    text = " ".join(
        value or ""
        for value in (
            product.title,
            product.brand,
            product.category_path_text,
        )
    ).casefold()
    tokens = set(_query_tokens(text))
    matched = sum(
        1
        for requirement in requirements
        if _matches_requirement(requirement, text, tokens)
    )
    return matched / len(requirements)


def _matches_requirement(requirement: set[str], text: str, tokens: set[str]) -> bool:
    if REQUIREMENT_VNECK in requirement:
        return bool(V_NECK_RE.search(text))
    if REQUIREMENT_SWEATER in requirement:
        return bool(tokens & SWEATER_TOKENS)
    if REQUIREMENT_COMPRESSION_WEAR in requirement:
        return _has_compression_term(tokens) and bool(tokens & COMPRESSION_WEAR_TOKENS)
    return bool(tokens & requirement)


def _query_tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(value.casefold())


def _query_has_v_neck(query: str, tokens: set[str]) -> bool:
    if V_NECK_RE.search(query):
        return True
    return bool(tokens & {"v", "vneck"} and tokens & NECKLINE_TOKENS)


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


async def _load_expanded_products(
    *,
    client: ServerAPIClient,
    expansions: list[SearchExpansion],
    config: Config,
) -> list[ProductDTO]:
    products: list[ProductDTO] = []
    for expansion in expansions:
        try:
            products.extend(
                await client.search_products(
                    query=expansion.query,
                    filters=_expansion_filters(expansion),
                    limit=config.openai_search_expand_query_limit,
                    offset=0,
                )
            )
        except ServerAPIError as error:
            logger.warning(
                "Expanded product search failed for query %r: %s",
                expansion.query,
                error,
            )
    return products


def _expansion_filters(expansion: SearchExpansion) -> dict[str, int]:
    filters: dict[str, int] = {}
    if expansion.min_price is not None:
        filters["min_price"] = expansion.min_price
    if expansion.max_price is not None:
        filters["max_price"] = expansion.max_price
    return filters


def _merge_unique_products(*product_groups: list[ProductDTO]) -> list[ProductDTO]:
    products: list[ProductDTO] = []
    seen_ids: set[int] = set()
    for group in product_groups:
        for product in group:
            if product.id in seen_ids:
                continue
            seen_ids.add(product.id)
            products.append(product)
    return products


def _search_expansion_allowed(*, config: Config, candidate_offset: int) -> bool:
    return bool(
        candidate_offset == 0
        and config.openai_search_expand_enabled
        and config.openai_rerank_enabled
        and config.openai_api_key
    )


async def _send_products(
    message: Message,
    products: list[ProductDTO],
    *,
    start_index: int,
    language_code: str | None,
) -> None:
    for index, product in enumerate(products, start=start_index):
        caption = render_product_card(product, index, language_code)
        if product.cover_image_url:
            try:
                await message.answer_photo(
                    photo=product.cover_image_url,
                    caption=caption,
                    reply_markup=more_results_keyboard(language_code),
                )
                continue
            except TelegramBadRequest:
                logger.warning("Telegram rejected product cover: %s", product.cover_image_url)
        await message.answer(
            caption,
            disable_web_page_preview=False,
            reply_markup=more_results_keyboard(language_code),
        )


def _user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


async def _guest_query_text(message: Message) -> str:
    text = (message.text or "").strip()
    if not text:
        return ""

    try:
        bot = await message.bot.get_me()
    except TelegramAPIError as error:
        logger.warning("Cannot fetch bot username for guest query normalization: %s", error)
        return _compact_whitespace(text)

    return _strip_bot_username(text, bot.username)


def _strip_bot_username(text: str, bot_username: str | None) -> str:
    if not bot_username:
        return _compact_whitespace(text)

    username = bot_username.lstrip("@")
    pattern = re.compile(rf"(?<!\w)@{re.escape(username)}\b", flags=re.IGNORECASE)
    return _compact_whitespace(pattern.sub(" ", text))


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


async def _answer_guest_query(
    message: Message,
    *,
    guest_query_id: str,
    title: str,
    text: str,
    description: str | None = None,
    thumbnail_url: str | None = None,
) -> None:
    result = InlineQueryResultArticle(
        id=f"uzum-{uuid4().hex}",
        title=title[:64],
        description=description,
        thumbnail_url=thumbnail_url,
        input_message_content=InputTextMessageContent(
            message_text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        ),
    )
    try:
        await message.bot.answer_guest_query(guest_query_id=guest_query_id, result=result)
    except TelegramAPIError as error:
        logger.warning("Telegram rejected guest query answer %s: %s", guest_query_id, error)


def _guest_result_title(query: str, products: list[ProductDTO], language_code: str) -> str:
    if not products:
        return format_message("guest_empty_title", language_code, query=query, html=False)
    return format_message(
        "guest_top_title",
        language_code,
        query=query,
        count=len(products),
        html=False,
    )


def _guest_result_description(products: list[ProductDTO], language_code: str) -> str | None:
    if not products:
        return format_message("guest_empty_description", language_code, html=False)
    return "; ".join(_short_text(product.title, 48) for product in products[:3])


def _guest_thumbnail_url(products: list[ProductDTO]) -> str | None:
    for product in products:
        if product.cover_image_url:
            return product.cover_image_url
    return None


def _short_text(value: str, max_length: int) -> str:
    value = value.strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."
