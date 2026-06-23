import logging
import re
from dataclasses import replace
from io import BytesIO
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    PhotoSize,
)

from bot.config import Config
from bot.keyboards.main_menu import is_more_button_text, main_menu_keyboard, more_results_keyboard
from bot.keyboards.product import product_card_keyboard
from bot.locales import format_message, language_from_message
from bot.services.ai_audio import transcribe_voice_message
from bot.services.ai_reranker import SearchExpansion, rank_products, rerank_products
from bot.services.ai_runtime import ai_runtime_state
from bot.services.ai_vision import (
    PhotoSearchQuery,
    identify_product_photo,
    rerank_photo_products_by_image,
)
from bot.services.analytics import track_message_event
from bot.services.api_client import (
    ProductDTO,
    ServerAPIClient,
    ServerAPIError,
    product_click_url,
    render_product_card,
    render_products,
)
from bot.services.image_fingerprint import ImageFingerprintError, image_fingerprint
from bot.services.search_state import SearchSession, search_state

router = Router(name="common")
logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
UZUM_PRODUCT_ID_RE = re.compile(
    r"(?:https?://)?(?:www\.)?uzum\.uz/\S*/product/\S+-(\d+)",
    re.IGNORECASE,
)
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
PHOTO_TEXT_FALLBACK_OBJECT_TOKENS = {
    "батончик",
    "батончики",
    "вафля",
    "вафли",
    "вода",
    "газировка",
    "жвачка",
    "йогурт",
    "карамель",
    "кола",
    "конфета",
    "конфеты",
    "кофе",
    "лапша",
    "леденец",
    "леденцы",
    "молоко",
    "напиток",
    "напитки",
    "паста",
    "печенье",
    "пюре",
    "сок",
    "соус",
    "снек",
    "снэк",
    "снэки",
    "снеки",
    "чай",
    "чипс",
    "чипсы",
    "шоколад",
    "шоколадка",
    "шоколадный",
}
PHOTO_OBJECT_QUERY_ALIASES = {
    "батончик": ("батончик", "шоколадный батончик", "chocolate bar", "snack bar"),
    "батончики": ("батончик", "шоколадный батончик", "chocolate bar", "snack bar"),
    "вода": ("вода", "suv", "water"),
    "газировка": ("газированный напиток", "gazlangan ichimlik", "soft drink"),
    "жвачка": ("жвачка", "saqich", "chewing gum"),
    "йогурт": ("йогурт", "yogurt"),
    "конфета": ("конфета", "konfet", "candy"),
    "конфеты": ("конфета", "konfet", "candy"),
    "кофе": ("кофе", "qahva", "coffee"),
    "напиток": ("напиток", "ichimlik", "drink"),
    "напитки": ("напиток", "ichimlik", "drink"),
    "печенье": ("печенье", "pechenye", "cookies"),
    "сок": ("сок", "sharbat", "juice"),
    "соус": ("соус", "sous", "sauce"),
    "снек": ("снек", "snek", "snack"),
    "снэк": ("снек", "snek", "snack"),
    "снэки": ("снек", "snek", "snack"),
    "снеки": ("снек", "snek", "snack"),
    "чай": ("чай", "choy", "tea"),
    "чипс": ("чипсы", "chips", "chipsi"),
    "чипсы": ("чипсы", "chips", "chipsi"),
    "шоколад": ("шоколад", "shokolad", "chocolate"),
    "шоколадка": ("шоколад", "shokolad", "chocolate"),
    "шоколадный": ("шоколад", "shokolad", "chocolate"),
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

    await track_message_event(
        config=config,
        message=message,
        event_type="more_results",
        language_code=language,
        input_type="button_or_text",
        query=session.query,
        metadata={"offset": session.offset, "candidate_offset": session.candidate_offset},
    )
    status_message = await message.answer(format_message("search_more_processing", language))
    products = await _next_products(session=session, config=config, message=message)
    if products is None:
        await _replace_status_message(
            status_message,
            format_message("catalog_unavailable", language),
            language=language,
            reply_markup=main_menu_keyboard(language),
        )
        return
    if not products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await _replace_status_message(
            status_message,
            format_message("no_more", language, query=session.query),
            language=language,
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
    await _replace_status_message(
        status_message,
        format_message("found_intro", language, query=session.query, count=len(products)),
        language=language,
        reply_markup=more_results_keyboard(language),
    )
    await _send_products(
        message,
        products,
        start_index=session.offset + 1,
        language_code=language,
        query=session.query,
        config=config,
    )


@router.message(F.photo)
async def search_uzum_by_photo(message: Message, config: Config) -> None:
    language = language_from_message(message)
    await track_message_event(
        config=config,
        message=message,
        event_type="photo_search",
        language_code=language,
        input_type="photo",
        query=message.caption or "",
        metadata={"photo_count": len(message.photo or [])},
    )
    photo = _select_photo_for_vision(message.photo or [], config)
    if photo is None:
        await message.answer(
            format_message("photo_download_failed", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    image_bytes = await _download_photo_bytes(message, photo, config)
    if image_bytes is None:
        await message.answer(
            format_message("photo_download_failed", language),
            reply_markup=main_menu_keyboard(language),
        )
        return
    if len(image_bytes) > config.openai_photo_max_download_bytes:
        await message.answer(
            format_message("photo_too_large", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    status_message = await message.answer(format_message("photo_processing", language))
    if _photo_search_available(config):
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        photo_query = await identify_product_photo(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            caption=message.caption or "",
            config=config,
        )
        if photo_query is not None:
            (
                used_query,
                ranked_products,
                photo_match_mode,
            ) = await _load_photo_ranked_candidates(
                image_bytes=image_bytes,
                photo_query=photo_query,
                config=config,
                message=message,
            )
            if ranked_products is None:
                return
            if not ranked_products:
                search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
                await _replace_status_message(
                    status_message,
                    format_message("photo_no_results", language, query=photo_query.query),
                    language=language,
                    reply_markup=main_menu_keyboard(language),
                )
                return

            products = ranked_products[: config.product_search_limit]
            search_state.set(
                chat_id=message.chat.id,
                user_id=_user_id(message),
                query=used_query,
                products=ranked_products,
                offset=len(products),
                candidate_offset=-1,
            )
            await _replace_status_message(
                status_message,
                format_message(
                    _photo_result_intro_key(photo_match_mode),
                    language,
                    query=used_query,
                    count=len(products),
                ),
                language=language,
                reply_markup=more_results_keyboard(language),
            )
            await _send_products(
                message,
                products,
                start_index=1,
                language_code=language,
                query=used_query,
                config=config,
            )
            return

        if not ai_runtime_state.ai_allowed():
            await _replace_status_message(
                status_message,
                format_message("photo_ai_unavailable", language),
                language=language,
                reply_markup=main_menu_keyboard(language),
            )
            return

    visual_products = await _load_visual_match_candidates(
        image_bytes=image_bytes,
        config=config,
        message=message,
    )
    if visual_products is None:
        return
    if visual_products:
        products = visual_products[: config.product_search_limit]
        search_state.set(
            chat_id=message.chat.id,
            user_id=_user_id(message),
            query="photo visual match",
            products=visual_products,
            offset=len(products),
            candidate_offset=-1,
        )
        await _replace_status_message(
            status_message,
            format_message("photo_visual_found_intro", language, count=len(products)),
            language=language,
            reply_markup=more_results_keyboard(language),
        )
        await _send_products(
            message,
            products,
            start_index=1,
            language_code=language,
            query="photo visual match",
            config=config,
        )
        return

    search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
    await _replace_status_message(
        status_message,
        format_message("photo_visual_no_results", language),
        language=language,
        reply_markup=main_menu_keyboard(language),
    )


@router.message(F.voice)
async def search_uzum_by_voice(message: Message, config: Config) -> None:
    language = language_from_message(message)
    voice = message.voice
    if voice is None:
        await message.answer(
            format_message("voice_download_failed", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    await track_message_event(
        config=config,
        message=message,
        event_type="voice_search",
        language_code=language,
        input_type="voice",
        metadata={"duration": voice.duration, "file_size": voice.file_size},
    )
    if voice.duration > config.openai_voice_max_duration_seconds:
        await message.answer(
            format_message("voice_too_long", language),
            reply_markup=main_menu_keyboard(language),
        )
        return
    if voice.file_size and voice.file_size > config.openai_voice_max_download_bytes:
        await message.answer(
            format_message("voice_too_large", language),
            reply_markup=main_menu_keyboard(language),
        )
        return
    if not _voice_search_available(config):
        await message.answer(
            format_message("voice_ai_unavailable", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    status_message = await message.answer(format_message("voice_processing", language))
    audio_bytes = await _download_telegram_file_bytes(
        message=message,
        file_id=voice.file_id,
        timeout_seconds=config.openai_voice_timeout,
    )
    if audio_bytes is None:
        await _replace_status_message(
            status_message,
            format_message("voice_download_failed", language),
            language=language,
            reply_markup=main_menu_keyboard(language),
        )
        return
    if len(audio_bytes) > config.openai_voice_max_download_bytes:
        await _replace_status_message(
            status_message,
            format_message("voice_too_large", language),
            language=language,
            reply_markup=main_menu_keyboard(language),
        )
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    transcript = await transcribe_voice_message(
        audio_bytes=audio_bytes,
        filename="voice.ogg",
        config=config,
        language_hint=language,
    )
    if transcript is None:
        message_key = (
            "voice_ai_unavailable"
            if not ai_runtime_state.ai_allowed()
            else "voice_transcription_failed"
        )
        await _replace_status_message(
            status_message,
            format_message(message_key, language),
            language=language,
            reply_markup=main_menu_keyboard(language),
        )
        return

    await _run_text_search(
        message=message,
        config=config,
        query=transcript,
        input_type="voice",
        status_message=status_message,
        empty_key="voice_transcription_failed",
        no_results_key="no_results",
        intro_key="voice_found_intro",
    )


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    query = (message.text or "").strip()
    language = language_from_message(message)
    status_message = await message.answer(format_message("search_processing", language))
    await _run_text_search(
        message=message,
        config=config,
        query=query,
        status_message=status_message,
    )


async def _next_products(
    *,
    session: SearchSession,
    config: Config,
    message: Message | None,
) -> list[ProductDTO] | None:
    products = session.products[session.offset : session.offset + config.product_search_limit]
    if products:
        return products
    if session.candidate_offset < 0:
        return []

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
    allow_ai_rerank: bool = True,
) -> list[ProductDTO] | None:
    try:
        initial_limit = (
            _initial_candidate_limit(config, candidate_offset)
            if allow_ai_rerank
            else config.product_search_limit
        )
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            products = await client.search_products(
                query=query,
                limit=initial_limit,
                offset=candidate_offset,
            )
            if not _should_use_ai_rerank(
                query=query,
                products=products,
                config=config,
                candidate_offset=candidate_offset,
                allow_ai_rerank=allow_ai_rerank,
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


async def _run_text_search(
    *,
    message: Message,
    config: Config,
    query: str,
    input_type: str = "text",
    status_message: Message | None = None,
    empty_key: str = "empty_query",
    no_results_key: str = "no_results",
    intro_key: str = "found_intro",
) -> None:
    language = language_from_message(message)
    query = " ".join(query.split())
    if not query:
        if status_message is not None:
            await _replace_status_message(
                status_message,
                format_message(empty_key, language),
                language=language,
                reply_markup=main_menu_keyboard(language),
            )
        else:
            await message.answer(
                format_message(empty_key, language),
                reply_markup=main_menu_keyboard(language),
            )
        return

    await track_message_event(
        config=config,
        message=message,
        event_type="search",
        language_code=language,
        input_type=input_type,
        query=query,
    )
    ranked_products = await _load_ranked_candidates(
        query=query,
        candidate_offset=0,
        config=config,
        message=message,
        allow_ai_rerank=True,
    )
    if ranked_products is None:
        return
    candidate_offset = len(ranked_products)
    sponsored_products = await _load_sponsored_products(
        query=query,
        language_code=language,
        config=config,
    )
    if sponsored_products:
        ranked_products = _exclude_product_ids(
            ranked_products,
            {product.id for product in sponsored_products},
        )
    if not ranked_products and not sponsored_products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await track_message_event(
            config=config,
            message=message,
            event_type="search_no_results",
            language_code=language,
            input_type=input_type,
            query=query,
            result_count=0,
        )
        if status_message is not None:
            await _replace_status_message(
                status_message,
                format_message(no_results_key, language, query=query),
                language=language,
                reply_markup=main_menu_keyboard(language),
            )
        else:
            await message.answer(
                format_message(no_results_key, language, query=query),
                reply_markup=main_menu_keyboard(language),
            )
        return

    if not ranked_products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        if status_message is not None:
            await _replace_status_message(
                status_message,
                format_message("sponsored_found_intro", language),
                language=language,
                reply_markup=main_menu_keyboard(language),
            )
        else:
            await message.answer(
                format_message("sponsored_found_intro", language),
                reply_markup=main_menu_keyboard(language),
            )
        await _send_products(
            message,
            sponsored_products,
            start_index=1,
            language_code=language,
            query=query,
            config=config,
        )
        return

    products = ranked_products[: config.product_search_limit]
    search_state.set(
        chat_id=message.chat.id,
        user_id=_user_id(message),
        query=query,
        products=ranked_products,
        offset=len(products),
        candidate_offset=candidate_offset,
    )
    if status_message is not None:
        await _replace_status_message(
            status_message,
            format_message(intro_key, language, query=query, count=len(products)),
            language=language,
            reply_markup=more_results_keyboard(language),
        )
    else:
        await message.answer(
            format_message(intro_key, language, query=query, count=len(products)),
            reply_markup=more_results_keyboard(language),
        )
    if sponsored_products:
        await message.answer(
            format_message("sponsored_found_intro", language),
            disable_web_page_preview=True,
        )
        await _send_products(
            message,
            sponsored_products,
            start_index=1,
            language_code=language,
            query=query,
            config=config,
        )
    await _send_products(
        message,
        products,
        start_index=1,
        language_code=language,
        query=query,
        config=config,
    )


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
    allow_ai_rerank: bool,
) -> bool:
    if not allow_ai_rerank:
        return False
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
        1 for requirement in requirements if _matches_requirement(requirement, text, tokens)
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


async def _load_sponsored_products(
    *,
    query: str,
    language_code: str | None,
    config: Config,
) -> list[ProductDTO]:
    if config.sponsored_search_limit <= 0:
        return []
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            return await client.sponsored_products(
                query=query,
                language_code=language_code,
                limit=config.sponsored_search_limit,
            )
    except ServerAPIError as error:
        logger.warning("Sponsored product search failed for query %r: %s", query, error)
        return []


def _exclude_product_ids(products: list[ProductDTO], product_ids: set[int]) -> list[ProductDTO]:
    if not product_ids:
        return products
    return [product for product in products if product.id not in product_ids]


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


async def _replace_status_message(
    message: Message,
    text: str,
    *,
    language: str,
    reply_markup: object | None = None,
) -> None:
    if reply_markup is not None:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await message.answer(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        return

    try:
        await message.edit_text(
            text,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        await message.answer(
            text,
            reply_markup=main_menu_keyboard(language),
            disable_web_page_preview=True,
        )


def _photo_search_available(config: Config) -> bool:
    return bool(
        config.openai_photo_search_enabled
        and config.openai_api_key
        and ai_runtime_state.ai_allowed()
    )


def _voice_search_available(config: Config) -> bool:
    return bool(
        config.openai_voice_search_enabled
        and config.openai_api_key
        and ai_runtime_state.ai_allowed()
    )


async def _download_photo_bytes(
    message: Message,
    photo: PhotoSize,
    config: Config,
) -> bytes | None:
    return await _download_telegram_file_bytes(
        message=message,
        file_id=photo.file_id,
        timeout_seconds=config.openai_photo_timeout,
    )


async def _download_telegram_file_bytes(
    *,
    message: Message,
    file_id: str,
    timeout_seconds: float,
) -> bytes | None:
    destination = BytesIO()
    try:
        await message.bot.download(
            file_id,
            destination=destination,
            timeout=max(1, int(timeout_seconds)),
        )
    except TelegramAPIError as error:
        logger.warning("Cannot download Telegram file %s: %s", file_id, error)
        return None
    return destination.getvalue()


def _select_photo_for_vision(
    photos: list[PhotoSize],
    config: Config,
) -> PhotoSize | None:
    if not photos:
        return None

    max_pixels = max(1, config.openai_photo_max_pixels)
    max_bytes = max(1, config.openai_photo_max_download_bytes)
    by_pixels = sorted(photos, key=lambda item: item.width * item.height)

    affordable = [
        photo
        for photo in by_pixels
        if photo.width * photo.height <= max_pixels
        and (photo.file_size is None or photo.file_size <= max_bytes)
    ]
    if affordable:
        return affordable[-1]

    by_size = sorted(
        photos,
        key=lambda item: (
            item.file_size if item.file_size is not None else max_bytes + 1,
            item.width * item.height,
        ),
    )
    return by_size[0]


async def _load_photo_ranked_candidates(
    *,
    image_bytes: bytes,
    photo_query: PhotoSearchQuery,
    config: Config,
    message: Message,
) -> tuple[str, list[ProductDTO] | None, str]:
    language = language_from_message(message)
    queries = _photo_search_queries(photo_query)
    query_limit = _photo_candidate_query_limit(config, len(queries))
    products: list[ProductDTO] = []
    used_query = queries[0] if queries else photo_query.query

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            for query in queries:
                query_products = await client.search_products(
                    query=query,
                    limit=query_limit,
                    offset=0,
                )
                if query_products and not products:
                    used_query = query
                products = _merge_unique_products(
                    products,
                    query_products,
                )
                if len(products) >= config.openai_photo_candidate_limit:
                    break
            if not products:
                substitute_query, substitute_products = await _load_photo_substitute_products(
                    client=client,
                    photo_query=photo_query,
                    config=config,
                )
                if substitute_products:
                    return substitute_query, substitute_products, "substitute"
    except ServerAPIError as error:
        logger.warning("Photo product candidate search failed for %r: %s", queries, error)
        await message.answer(
            format_message("catalog_unavailable", language),
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(language),
        )
        return used_query, None, "none"

    products = products[: max(config.product_search_limit, config.openai_photo_candidate_limit)]
    if not products:
        return used_query, [], "none"

    ranked_products = await rerank_photo_products_by_image(
        image_bytes=image_bytes,
        mime_type="image/jpeg",
        photo_query=photo_query,
        products=products,
        config=config,
    )
    if ranked_products is None:
        if config.openai_photo_text_fallback_enabled:
            return used_query, products, "text"
        await message.answer(
            format_message("photo_ai_unavailable", language),
            reply_markup=main_menu_keyboard(language),
        )
        return used_query, None, "none"
    if ranked_products:
        return used_query, ranked_products, "ai"
    safe_text_fallback = _photo_text_fallback_products(
        photo_query=photo_query,
        products=products,
        limit=max(config.product_search_limit, config.openai_photo_candidate_limit),
    )
    if safe_text_fallback:
        return used_query, safe_text_fallback, "text"
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            substitute_query, substitute_products = await _load_photo_substitute_products(
                client=client,
                photo_query=photo_query,
                config=config,
            )
    except ServerAPIError as error:
        logger.warning("Photo substitute search failed for %r: %s", photo_query.query, error)
        substitute_query, substitute_products = used_query, []
    if substitute_products:
        return substitute_query, substitute_products, "substitute"
    return used_query, [], "none"


def _photo_result_intro_key(mode: str) -> str:
    if mode == "substitute":
        return "photo_substitute_intro"
    if mode == "text":
        return "photo_text_fallback_intro"
    return "photo_found_intro"


async def _load_photo_substitute_products(
    *,
    client: ServerAPIClient,
    photo_query: PhotoSearchQuery,
    config: Config,
) -> tuple[str, list[ProductDTO]]:
    if not config.openai_photo_text_fallback_enabled:
        return photo_query.query, []
    if not _photo_brand_tokens(photo_query.brand):
        return photo_query.query, []

    queries = _photo_substitute_queries(photo_query)
    if not queries:
        return photo_query.query, []

    query_limit = _photo_candidate_query_limit(config, len(queries))
    products: list[ProductDTO] = []
    used_query = queries[0]
    for query in queries:
        query_products = await client.search_products(
            query=query,
            limit=query_limit,
            offset=0,
        )
        filtered = _photo_text_fallback_products(
            photo_query=photo_query,
            products=query_products,
            limit=config.openai_photo_candidate_limit,
            require_brand=False,
        )
        if filtered and not products:
            used_query = query
        products = _merge_unique_products(products, filtered)
        if len(products) >= config.product_search_limit:
            break
    return used_query, products[: config.product_search_limit]


def _photo_search_queries(photo_query: PhotoSearchQuery) -> list[str]:
    raw_queries = [
        _photo_core_query(photo_query),
        *_photo_object_alias_queries(photo_query),
        photo_query.query,
        *photo_query.alternative_queries,
        " ".join(
            part
            for part in (
                photo_query.brand,
                photo_query.visible_text,
                photo_query.object_type,
            )
            if part
        ),
    ]
    queries = []
    seen = set()
    for query in raw_queries:
        cleaned = " ".join(query.split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        queries.append(cleaned)
        seen.add(key)
        if len(queries) >= 7:
            break
    return queries or [photo_query.query]


def _photo_substitute_queries(photo_query: PhotoSearchQuery) -> list[str]:
    raw_queries = [
        photo_query.object_type,
        *_photo_object_alias_queries(replace(photo_query, brand="")),
    ]
    queries = []
    seen = set()
    for query in raw_queries:
        cleaned = " ".join(query.split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        queries.append(cleaned)
        seen.add(key)
        if len(queries) >= 5:
            break
    return queries


def _photo_core_query(photo_query: PhotoSearchQuery) -> str:
    parts = []
    if photo_query.brand and LATIN_RE.search(photo_query.brand):
        parts.append(photo_query.brand)
    if photo_query.object_type:
        parts.append(photo_query.object_type)
    if parts:
        return " ".join(parts)
    return photo_query.query


def _photo_object_alias_queries(photo_query: PhotoSearchQuery) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    prefix = photo_query.brand.strip() if photo_query.brand else ""
    for token in _query_tokens(photo_query.object_type):
        for alias in PHOTO_OBJECT_QUERY_ALIASES.get(token, ()):
            query = f"{prefix} {alias}".strip()
            key = query.casefold()
            if not query or key in seen:
                continue
            aliases.append(query)
            seen.add(key)
            if len(aliases) >= 4:
                return aliases
    return aliases


def _photo_text_fallback_products(
    *,
    photo_query: PhotoSearchQuery,
    products: list[ProductDTO],
    limit: int,
    require_brand: bool = True,
) -> list[ProductDTO]:
    object_tokens = set(_query_tokens(photo_query.object_type))
    allowed_tokens = object_tokens & PHOTO_TEXT_FALLBACK_OBJECT_TOKENS
    if not allowed_tokens:
        return []

    brand_tokens = _photo_brand_tokens(photo_query.brand)
    filtered: list[ProductDTO] = []
    for product in products:
        haystack = " ".join(
            part
            for part in (product.title, product.brand, product.category_path_text)
            if part
        )
        product_tokens = set(_query_tokens(haystack))
        if require_brand and brand_tokens and not brand_tokens & product_tokens:
            continue
        if allowed_tokens & product_tokens:
            filtered.append(product)
        if len(filtered) >= limit:
            break
    return filtered


def _photo_brand_tokens(brand: str) -> set[str]:
    return {token for token in _query_tokens(brand) if len(token) >= 3}


def _photo_candidate_query_limit(config: Config, query_count: int) -> int:
    query_count = max(1, query_count)
    per_query = config.openai_photo_candidate_limit // query_count + config.product_search_limit
    return max(config.product_search_limit, min(40, per_query))


async def _load_visual_match_candidates(
    *,
    image_bytes: bytes,
    config: Config,
    message: Message,
) -> list[ProductDTO] | None:
    if not config.photo_visual_match_enabled:
        return []

    language = language_from_message(message)
    try:
        fingerprint = image_fingerprint(image_bytes)
    except ImageFingerprintError as error:
        logger.warning("Cannot fingerprint Telegram photo: %s", error)
        await message.answer(
            format_message("photo_visual_unavailable", language),
            reply_markup=main_menu_keyboard(language),
        )
        return None

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            products = await client.visual_search_products(
                ahash=fingerprint.ahash,
                dhash=fingerprint.dhash,
                max_distance=config.photo_visual_match_max_distance,
                limit=max(config.product_search_limit, 25),
            )
            if products:
                return products

            source_product_ids = _source_product_ids_from_text(message.caption or "")
            if not source_product_ids:
                return []

            stats = await client.index_product_covers(
                source_product_ids=source_product_ids,
                limit=len(source_product_ids),
            )
            logger.info(
                "Indexed product covers on demand from photo caption: ids=%s stats=%s",
                source_product_ids,
                stats,
            )
            return await client.visual_search_products(
                ahash=fingerprint.ahash,
                dhash=fingerprint.dhash,
                max_distance=config.photo_visual_match_max_distance,
                limit=max(config.product_search_limit, 25),
            )
    except ServerAPIError as error:
        logger.warning("Visual product search failed: %s", error)
        await message.answer(
            format_message("catalog_unavailable", language),
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(language),
        )
        return None


def _source_product_ids_from_text(text: str) -> list[str]:
    ids = []
    seen = set()
    for match in UZUM_PRODUCT_ID_RE.finditer(text):
        product_id = match.group(1)
        if product_id not in seen:
            ids.append(product_id)
            seen.add(product_id)
    return ids[:5]


async def _send_products(
    message: Message,
    products: list[ProductDTO],
    *,
    start_index: int,
    language_code: str | None,
    query: str,
    config: Config,
    telegram_user_id: int | None = None,
) -> None:
    for index, product in enumerate(products, start=start_index):
        is_sponsored = product.sponsored_campaign_id is not None
        context_event_id = await track_message_event(
            config=config,
            message=message,
            event_type="sponsored_impression" if is_sponsored else "view_item_list",
            telegram_user_id=telegram_user_id,
            language_code=language_code,
            input_type="sponsored_product_card" if is_sponsored else "product_card",
            query=query,
            product_id=product.id,
            source_product_id=product.source_product_id,
            product_position=index,
            result_count=len(products),
            metadata={
                "item_list_name": query,
                "item_id": product.id,
                "item_name": product.title,
                "source_product_id": product.source_product_id,
                "is_sponsored": is_sponsored,
                "sponsored_campaign_id": (
                    str(product.sponsored_campaign_id) if is_sponsored else ""
                ),
                "sponsored_campaign_name": product.sponsored_campaign_name or "",
                "sponsored_advertiser_name": product.sponsored_advertiser_name or "",
            },
        )
        tracking_url = product_click_url(
            public_base_url=config.public_base_url,
            product_id=product.id,
            context_event_id=context_event_id,
        )
        product_for_render = (
            replace(product, tracking_url=tracking_url) if tracking_url else product
        )
        product_url = product_for_render.tracking_url or product_for_render.canonical_url
        keyboard = product_card_keyboard(language_code, product_url=product_url)
        caption = render_product_card(product_for_render, index, language_code)
        if product.cover_image_url:
            try:
                await message.answer_photo(
                    photo=product.cover_image_url,
                    caption=caption,
                    reply_markup=keyboard,
                )
                continue
            except TelegramBadRequest:
                logger.warning("Telegram rejected product cover: %s", product.cover_image_url)
        await message.answer(
            caption,
            disable_web_page_preview=False,
            reply_markup=keyboard,
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
