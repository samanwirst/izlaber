import logging
import re
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, Message

from bot.config import Config
from bot.keyboards.main_menu import MORE_BUTTON_TEXT, main_menu_keyboard, more_results_keyboard
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


@router.guest_message(F.text)
async def guest_search_uzum(message: Message, config: Config) -> None:
    if not config.guest_search_enabled:
        return

    guest_query_id = message.guest_query_id
    if not guest_query_id:
        logger.warning("Guest message without guest_query_id: %s", message.message_id)
        return

    query = await _guest_query_text(message)
    if not query:
        await _answer_guest_query(
            message,
            guest_query_id=guest_query_id,
            title="Что искать на Uzum?",
            text="Напишите товар рядом с упоминанием бота, например: @bot iphone 15.",
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
            title="Каталог временно недоступен",
            text="Не смог получить товары из каталога. Попробуйте повторить запрос позже.",
        )
        return

    products = ranked_products[: config.product_search_limit]
    await _answer_guest_query(
        message,
        guest_query_id=guest_query_id,
        title=_guest_result_title(query, products),
        text=render_products(products, query),
        description=_guest_result_description(products),
        thumbnail_url=_guest_thumbnail_url(products),
    )


def _is_more_button(message: Message) -> bool:
    return (message.text or "").strip().casefold() == MORE_BUTTON_TEXT.casefold()


@router.message(_is_more_button)
async def search_more(message: Message, config: Config) -> None:
    session = search_state.get(chat_id=message.chat.id, user_id=_user_id(message))
    if session is None:
        await message.answer(
            "Сначала напишите название товара, потом нажимайте «Еще».",
            reply_markup=main_menu_keyboard(),
        )
        return

    products = await _next_products(session=session, config=config, message=message)
    if products is None:
        return
    if not products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await message.answer(
            f"Больше карточек по запросу «{session.query}» не нашел.",
            reply_markup=main_menu_keyboard(),
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
    await _send_products(message, products, start_index=session.offset + 1)


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Напишите название товара.", reply_markup=main_menu_keyboard())
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
            f"В каталоге пока нет товаров по запросу «{query}».",
            reply_markup=main_menu_keyboard(),
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
        f"Нашел карточки по запросу «{query}». Показываю первые {len(products)}:",
        reply_markup=more_results_keyboard(),
    )
    await _send_products(message, products, start_index=1)


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
    limit = _candidate_limit(config)

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            products = await client.search_products(
                query=query,
                limit=limit,
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
            await message.answer(
                "Каталог сейчас недоступен. Попробуйте позже.",
                disable_web_page_preview=True,
                reply_markup=main_menu_keyboard(),
            )
        return None

    return ranked_result.products


def _candidate_limit(config: Config) -> int:
    if config.openai_rerank_enabled and config.openai_api_key:
        return max(config.product_search_limit, config.openai_candidate_limit)
    return config.product_search_limit


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


async def _send_products(message: Message, products: list[ProductDTO], *, start_index: int) -> None:
    for index, product in enumerate(products, start=start_index):
        caption = render_product_card(product, index)
        if product.cover_image_url:
            try:
                await message.answer_photo(
                    photo=product.cover_image_url,
                    caption=caption,
                    reply_markup=more_results_keyboard(),
                )
                continue
            except TelegramBadRequest:
                logger.warning("Telegram rejected product cover: %s", product.cover_image_url)
        await message.answer(
            caption,
            disable_web_page_preview=False,
            reply_markup=more_results_keyboard(),
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


def _guest_result_title(query: str, products: list[ProductDTO]) -> str:
    if not products:
        return f"Ничего не найдено: {query}"
    return f"Топ-{len(products)} на Uzum: {query}"


def _guest_result_description(products: list[ProductDTO]) -> str | None:
    if not products:
        return "В каталоге нет подходящих товаров."
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
