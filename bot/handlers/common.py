import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass, replace
from io import BytesIO
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    PhotoSize,
)
from aiohttp import ClientError, ClientSession, ClientTimeout

from bot.config import Config
from bot.keyboards.main_menu import is_more_button_text, main_menu_keyboard, more_results_keyboard
from bot.keyboards.product import product_card_keyboard
from bot.locales import format_message, language_from_message
from bot.services.ai_audio import transcribe_voice_message
from bot.services.ai_reranker import (
    SearchExpansion,
    rank_products,
    rerank_products,
    understand_search_query,
)
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

MAX_COVER_DOWNLOAD_BYTES = 5 * 1024 * 1024
SEARCH_PROGRESS_DELAYS_SECONDS = (5, 10, 10, 10, 10, 10)
WEBP_COVER_RE = re.compile(r"\.webp(?:[?#].*)?$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
UZUM_PRODUCT_ID_RE = re.compile(
    r"(?:https?://)?(?:www\.)?uzum\.uz/\S*/product/\S+-(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class TextSearchRescueResult:
    query: str
    products: list[ProductDTO]
    sponsored_products: list[ProductDTO]
    candidate_offset: int


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
PHOTO_BRAND_TOKEN_ALIASES = {
    "snickers": {"сникерс"},
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
    "или",
    "купить",
    "на",
    "найди",
    "нужен",
    "нужна",
    "нужно",
    "под",
    "при",
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
    if query.startswith("/"):
        await _answer_guest_query(
            message,
            guest_query_id=guest_query_id,
            title=format_message("guest_need_query_title", language, html=False),
            text=format_message("unknown_command", language),
        )
        return

    await _send_guest_search_started_message(message, language)
    inline_message_id = await _answer_guest_query(
        message,
        guest_query_id=guest_query_id,
        title=format_message("guest_search_started_title", language, html=False),
        text=format_message("guest_search_started_text", language),
    )
    try:
        ranked_products = await asyncio.wait_for(
            _load_ranked_candidates(
                query=query,
                candidate_offset=0,
                config=config,
                message=None,
            ),
            timeout=config.search_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "Guest search timed out for query %r after %.1fs",
            query,
            config.search_timeout_seconds,
        )
        await _finish_guest_query(
            message,
            guest_query_id=guest_query_id,
            inline_message_id=inline_message_id,
            title=format_message("guest_search_started_title", language, html=False),
            text=format_message("search_timeout", language),
        )
        return
    if ranked_products is None:
        await _finish_guest_query(
            message,
            guest_query_id=guest_query_id,
            inline_message_id=inline_message_id,
            title=format_message("guest_catalog_unavailable_title", language, html=False),
            text=format_message("guest_catalog_unavailable_text", language),
        )
        return

    products = ranked_products[: config.product_search_limit]
    await _finish_guest_query(
        message,
        guest_query_id=guest_query_id,
        inline_message_id=inline_message_id,
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
    try:
        products = await _wait_for_search_with_progress(
            _next_products(session=session, config=config, message=message),
            timeout=config.search_timeout_seconds,
            message=message,
            language=language,
        )
    except TimeoutError:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await _handle_search_timeout(
            message=message,
            config=config,
            status_message=status_message,
            language=language,
            query=session.query,
            input_type="more",
        )
        return
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
    try:
        await _wait_for_search_with_progress(
            _run_photo_search(
                message=message,
                config=config,
                language=language,
                image_bytes=image_bytes,
                status_message=status_message,
            ),
            timeout=config.search_timeout_seconds,
            message=message,
            language=language,
        )
    except TimeoutError:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await _handle_search_timeout(
            message=message,
            config=config,
            status_message=status_message,
            language=language,
            query=message.caption or "photo",
            input_type="photo",
        )


async def _run_photo_search(
    *,
    message: Message,
    config: Config,
    language: str,
    image_bytes: bytes,
    status_message: Message,
) -> None:
    if _photo_search_available(config):
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        photo_query = await identify_product_photo(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            caption=message.caption or "",
            config=config,
        )
        if photo_query is not None:
            logger.info(
                "Photo identified: query=%r brand=%r object_type=%r confidence=%s "
                "alternatives=%r",
                photo_query.query,
                photo_query.brand,
                photo_query.object_type,
                photo_query.confidence,
                photo_query.alternative_queries,
            )
            await track_message_event(
                config=config,
                message=message,
                event_type="photo_identified",
                language_code=language,
                input_type="photo",
                query=photo_query.query,
                metadata={
                    "brand": photo_query.brand,
                    "object_type": photo_query.object_type,
                    "visible_text": photo_query.visible_text,
                    "visible_product": photo_query.visible_product,
                    "confidence": photo_query.confidence,
                    "alternative_queries": photo_query.alternative_queries,
                },
            )
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
                await _track_photo_search_result(
                    config=config,
                    message=message,
                    language=language,
                    photo_query=photo_query,
                    used_query=used_query,
                    mode=photo_match_mode,
                    result_count=0,
                )
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
            await _track_photo_search_result(
                config=config,
                message=message,
                language=language,
                photo_query=photo_query,
                used_query=used_query,
                mode=photo_match_mode,
                result_count=len(products),
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

    await _run_text_search_with_timeout(
        message=message,
        config=config,
        query=transcript,
        input_type="voice",
        status_message=status_message,
        empty_key="voice_transcription_failed",
        no_results_key="no_results",
        intro_key="voice_found_intro",
    )


def _is_unknown_slash_command(message: Message) -> bool:
    text = (message.text or "").strip()
    return text.startswith("/")


@router.message(_is_unknown_slash_command)
async def unknown_slash_command(message: Message, config: Config) -> None:
    language = language_from_message(message)
    await track_message_event(
        config=config,
        message=message,
        event_type="unknown_command",
        language_code=language,
        input_type="command",
        query=(message.text or "").strip(),
    )
    await message.answer(
        format_message("unknown_command", language),
        reply_markup=main_menu_keyboard(language),
    )


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    query = (message.text or "").strip()
    language = language_from_message(message)
    status_message = await message.answer(format_message("search_processing", language))
    await _run_text_search_with_timeout(
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
            timeout=_catalog_search_api_timeout(config),
        ) as client:
            products = await client.search_products(
                query=query,
                limit=initial_limit,
                offset=candidate_offset,
                balance_page_size=config.product_search_limit,
            )
            if not _should_use_ai_rerank(
                query=query,
                products=products,
                config=config,
                candidate_offset=candidate_offset,
                allow_ai_rerank=allow_ai_rerank,
            ):
                return _balance_products_by_marketplace(
                    products,
                    page_size=config.product_search_limit,
                )

            candidate_limit = _candidate_limit(config)
            if len(products) < candidate_limit:
                products = await client.search_products(
                    query=query,
                    limit=candidate_limit,
                    offset=candidate_offset,
                    balance_page_size=config.product_search_limit,
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
                    reranked_products = await rerank_products(
                        query=query,
                        products=merged_products,
                        config=config,
                    )
                    return _balance_products_by_marketplace(
                        reranked_products,
                        page_size=config.product_search_limit,
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

    return _balance_products_by_marketplace(
        ranked_result.products,
        page_size=config.product_search_limit,
    )


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
    stop_progress=None,
) -> None:
    language = language_from_message(message)
    query = " ".join(query.split())
    if not query:
        if stop_progress is not None:
            stop_progress()
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
    original_query = query
    understanding = await understand_search_query(query=query, config=config)
    if understanding.query and understanding.query != query:
        query = understanding.query
        logger.info(
            "Understood text search query %r as %r via %s.",
            original_query,
            query,
            understanding.source,
        )
        await track_message_event(
            config=config,
            message=message,
            event_type="search_query_understood",
            language_code=language,
            input_type=input_type,
            query=query,
            metadata={
                "original_query": original_query,
                "source": understanding.source,
                "search_queries": [
                    {
                        "query": expansion.query,
                        "min_price": expansion.min_price,
                        "max_price": expansion.max_price,
                    }
                    for expansion in understanding.search_queries
                ],
            },
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
    if understanding.source != "original" and _local_results_need_ai(
        query,
        ranked_products,
        min_results=config.product_search_limit,
    ):
        expanded_products = await _load_understanding_expanded_products(
            expansions=understanding.search_queries[1:],
            config=config,
        )
        if expanded_products:
            merged_products = _merge_unique_products(ranked_products, expanded_products)
            if len(merged_products) > len(ranked_products):
                ranked_products = await rerank_products(
                    query=query,
                    products=merged_products,
                    config=config,
                )
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
        backfilled = await _request_search_backfill_and_wait(
            queries=[expansion.query for expansion in understanding.search_queries] or [query],
            config=config,
            message=message,
            source=f"bot_{input_type}_search_miss",
        )
        if backfilled:
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
        if stop_progress is not None:
            stop_progress()
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
        if stop_progress is not None:
            stop_progress()
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
    if stop_progress is not None:
        stop_progress()
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


def _catalog_search_api_timeout(config: Config) -> float:
    return max(config.server_api_timeout, config.search_timeout_seconds + 1.0)


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
    if _has_generic_phone_accessory_query_intent(token_set):
        skip_tokens.update(GENERIC_PHONE_TOKENS)

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
                    balance_page_size=config.product_search_limit,
                )
            )
        except ServerAPIError as error:
            logger.warning(
                "Expanded product search failed for query %r: %s",
                expansion.query,
                error,
            )
    return products


async def _load_understanding_expanded_products(
    *,
    expansions: list[SearchExpansion],
    config: Config,
) -> list[ProductDTO]:
    if not expansions:
        return []
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=_catalog_search_api_timeout(config),
        ) as client:
            return await _load_expanded_products(
                client=client,
                expansions=expansions,
                config=config,
            )
    except ServerAPIError as error:
        logger.warning(
            "Understood query expansion failed for %r: %s",
            [expansion.query for expansion in expansions],
            error,
        )
        return []


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


def _search_ai_rescue_after_seconds(config: Config) -> float | None:
    rescue_after = config.search_ai_rescue_after_seconds
    if rescue_after <= 0 or rescue_after >= config.search_timeout_seconds:
        return None
    if not (
        config.openai_api_key
        and config.openai_rerank_enabled
        and config.openai_search_expand_enabled
        and ai_runtime_state.ai_allowed()
    ):
        return None
    return rescue_after


async def _run_text_search_ai_rescue(
    *,
    message: Message,
    config: Config,
    query: str,
    input_type: str,
    intro_key: str,
) -> TextSearchRescueResult | None:
    language = language_from_message(message)
    query = " ".join(query.split())
    if not query:
        return None

    await message.answer(
        format_message("search_ai_rescue", language),
        disable_web_page_preview=True,
    )
    await track_message_event(
        config=config,
        message=message,
        event_type="search_ai_rescue_started",
        language_code=language,
        input_type=input_type,
        query=query,
        metadata={"after_seconds": config.search_ai_rescue_after_seconds},
    )

    understanding = await understand_search_query(query=query, config=config, force_ai=True)
    rescue_query = understanding.query or query
    expansions = understanding.search_queries or [SearchExpansion(rescue_query)]
    if understanding.query and (
        understanding.query != query or understanding.source != "original"
    ):
        await track_message_event(
            config=config,
            message=message,
            event_type="search_query_understood",
            language_code=language,
            input_type=input_type,
            query=understanding.query,
            metadata={
                "original_query": query,
                "source": f"{understanding.source}_rescue",
                "search_queries": [
                    {
                        "query": expansion.query,
                        "min_price": expansion.min_price,
                        "max_price": expansion.max_price,
                    }
                    for expansion in expansions
                ],
            },
        )

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=_catalog_search_api_timeout(config),
        ) as client:
            products = await _load_expanded_products(
                client=client,
                expansions=expansions,
                config=config,
            )
    except ServerAPIError as error:
        logger.warning("AI rescue product search failed for query %r: %s", query, error)
        return None

    products = _merge_unique_products([], products)
    if products:
        products = await rerank_products(query=rescue_query, products=products, config=config)
        products = _balance_products_by_marketplace(
            products,
            page_size=config.product_search_limit,
        )

    sponsored_products = await _load_sponsored_products(
        query=rescue_query,
        language_code=language,
        config=config,
    )
    if sponsored_products:
        products = _exclude_product_ids(
            products,
            {product.id for product in sponsored_products},
        )
    if not products and not sponsored_products:
        await track_message_event(
            config=config,
            message=message,
            event_type="search_ai_rescue_no_results",
            language_code=language,
            input_type=input_type,
            query=rescue_query,
            result_count=0,
            metadata={"original_query": query},
        )
        return None

    await track_message_event(
        config=config,
        message=message,
        event_type="search_ai_rescue_succeeded",
        language_code=language,
        input_type=input_type,
        query=rescue_query,
        result_count=len(products) + len(sponsored_products),
        metadata={
            "original_query": query,
            "intro_key": intro_key,
            "search_queries": [expansion.query for expansion in expansions],
        },
    )
    return TextSearchRescueResult(
        query=rescue_query,
        products=products,
        sponsored_products=sponsored_products,
        candidate_offset=len(products),
    )


async def _deliver_text_search_ai_rescue(
    *,
    message: Message,
    config: Config,
    status_message: Message | None,
    language: str,
    intro_key: str,
    rescue_result: TextSearchRescueResult,
) -> None:
    if not rescue_result.products:
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
            rescue_result.sponsored_products,
            start_index=1,
            language_code=language,
            query=rescue_result.query,
            config=config,
        )
        return

    products = rescue_result.products[: config.product_search_limit]
    search_state.set(
        chat_id=message.chat.id,
        user_id=_user_id(message),
        query=rescue_result.query,
        products=rescue_result.products,
        offset=len(products),
        candidate_offset=rescue_result.candidate_offset,
    )
    if status_message is not None:
        await _replace_status_message(
            status_message,
            format_message(intro_key, language, query=rescue_result.query, count=len(products)),
            language=language,
            reply_markup=more_results_keyboard(language),
        )
    else:
        await message.answer(
            format_message(intro_key, language, query=rescue_result.query, count=len(products)),
            reply_markup=more_results_keyboard(language),
        )
    if rescue_result.sponsored_products:
        await message.answer(
            format_message("sponsored_found_intro", language),
            disable_web_page_preview=True,
        )
        await _send_products(
            message,
            rescue_result.sponsored_products,
            start_index=1,
            language_code=language,
            query=rescue_result.query,
            config=config,
        )
    await _send_products(
        message,
        products,
        start_index=1,
        language_code=language,
        query=rescue_result.query,
        config=config,
    )


async def _run_text_search_with_timeout(
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
    rescue_after = _search_ai_rescue_after_seconds(config)
    progress_stop_event = asyncio.Event()
    try:
        await _wait_for_search_with_progress(
            _run_text_search(
                message=message,
                config=config,
                query=query,
                input_type=input_type,
                status_message=status_message,
                empty_key=empty_key,
                no_results_key=no_results_key,
                intro_key=intro_key,
                stop_progress=progress_stop_event.set,
            ),
            timeout=config.search_timeout_seconds,
            message=message,
            language=language,
            progress_stop_event=progress_stop_event,
            rescue_after=rescue_after,
            rescue_factory=lambda: _run_text_search_ai_rescue(
                message=message,
                config=config,
                query=query,
                input_type=input_type,
                intro_key=intro_key,
            ),
            rescue_delivery=lambda rescue_result: _deliver_text_search_ai_rescue(
                message=message,
                config=config,
                status_message=status_message,
                language=language,
                intro_key=intro_key,
                rescue_result=rescue_result,
            ),
        )
    except TimeoutError:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await _handle_search_timeout(
            message=message,
            config=config,
            status_message=status_message,
            language=language,
            query=query,
            input_type=input_type,
        )


async def _wait_for_search_with_progress(
    awaitable,
    *,
    timeout: float,
    message: Message,
    language: str,
    progress_stop_event: asyncio.Event | None = None,
    rescue_after: float | None = None,
    rescue_factory=None,
    rescue_delivery=None,
):
    task = asyncio.create_task(awaitable)
    progress_stop_event = progress_stop_event or asyncio.Event()
    progress_task = asyncio.create_task(
        _send_search_progress_pings(message, language, stop_event=progress_stop_event)
    )
    rescue_task = (
        asyncio.create_task(_run_search_ai_rescue_after_delay(rescue_after, rescue_factory))
        if rescue_after is not None and rescue_factory is not None
        else None
    )
    try:
        if rescue_task is None:
            return await asyncio.wait_for(task, timeout=timeout)

        deadline = asyncio.get_running_loop().time() + timeout
        pending = {task, rescue_task}
        while pending:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError
            done, pending = await asyncio.wait(
                pending,
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise TimeoutError
            if task in done:
                return task.result()
            if rescue_task in done:
                rescue_result = rescue_task.result()
                if rescue_result:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    progress_stop_event.set()
                    progress_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await progress_task
                    if rescue_delivery is not None:
                        await rescue_delivery(rescue_result)
                    return True
                pending.discard(rescue_task)
        return await task
    finally:
        progress_stop_event.set()
        task.cancel()
        if rescue_task is not None:
            rescue_task.cancel()
        progress_task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        if rescue_task is not None:
            with suppress(asyncio.CancelledError):
                await rescue_task
        with suppress(asyncio.CancelledError):
            await progress_task


async def _run_search_ai_rescue_after_delay(delay: float, rescue_factory):
    await asyncio.sleep(delay)
    try:
        return await rescue_factory()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("AI search rescue failed.")
        return False


async def _send_search_progress_pings(
    message: Message,
    language: str,
    *,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop_event = stop_event or asyncio.Event()
    for delay in SEARCH_PROGRESS_DELAYS_SECONDS:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
            return
        except TimeoutError:
            pass
        if stop_event.is_set():
            return
        await message.answer(
            format_message("search_still_processing", language),
            disable_web_page_preview=True,
        )


async def _handle_search_timeout(
    *,
    message: Message,
    config: Config,
    status_message: Message | None,
    language: str,
    query: str,
    input_type: str,
) -> None:
    logger.warning(
        "Search timed out for input_type=%s query=%r after %.1fs",
        input_type,
        query,
        config.search_timeout_seconds,
    )
    await track_message_event(
        config=config,
        message=message,
        event_type="search_timeout",
        language_code=language,
        input_type=input_type,
        query=query,
    )
    text = format_message("search_timeout", language)
    if status_message is not None:
        await _replace_status_message(
            status_message,
            text,
            language=language,
            reply_markup=main_menu_keyboard(language),
        )
        return
    await message.answer(text, reply_markup=main_menu_keyboard(language))


async def _request_search_backfill_and_wait(
    *,
    queries: list[str],
    config: Config,
    message: Message,
    source: str,
    client: ServerAPIClient | None = None,
) -> bool:
    if not config.search_backfill_enabled or config.search_backfill_wait_seconds <= 0:
        return False

    normalized_queries = _unique_nonempty_queries(queries, limit=config.search_backfill_max_queries)
    if not normalized_queries:
        return False

    async def request_with_client(active_client: ServerAPIClient) -> bool:
        request_ids: list[int] = []
        for query in normalized_queries:
            try:
                data = await active_client.create_search_backfill_request(
                    query=query,
                    source=source,
                    telegram_user_id=_user_id(message),
                    limit=config.search_backfill_limit,
                )
            except ServerAPIError as error:
                logger.warning("Cannot create search backfill request for %r: %s", query, error)
                continue
            try:
                request_id = int(data["id"])
            except (KeyError, TypeError, ValueError):
                continue
            request_ids.append(request_id)

        if not request_ids:
            return False

        await track_message_event(
            config=config,
            message=message,
            event_type="search_backfill_requested",
            language_code=language_from_message(message),
            input_type=source,
            query=normalized_queries[0],
            metadata={"queries": normalized_queries, "request_ids": request_ids},
        )

        deadline = asyncio.get_running_loop().time() + config.search_backfill_wait_seconds
        pending_ids = set(request_ids)
        completed = False
        while pending_ids and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(config.search_backfill_poll_seconds)
            for request_id in list(pending_ids):
                try:
                    data = await active_client.get_search_backfill_request(request_id)
                except ServerAPIError as error:
                    logger.warning(
                        "Cannot poll search backfill request %s: %s",
                        request_id,
                        error,
                    )
                    pending_ids.discard(request_id)
                    continue
                status = str(data.get("status") or "")
                if status in {"success", "partial"}:
                    completed = True
                    pending_ids.discard(request_id)
                elif status == "failed":
                    pending_ids.discard(request_id)

        return completed or bool(request_ids)

    if client is not None:
        return await request_with_client(client)

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as owned_client:
            return await request_with_client(owned_client)
    except ServerAPIError as error:
        logger.warning("Search backfill request failed for %r: %s", normalized_queries, error)
        return False


def _unique_nonempty_queries(queries: list[str], *, limit: int) -> list[str]:
    cleaned_queries: list[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = " ".join(str(query or "").split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        cleaned_queries.append(cleaned)
        seen.add(key)
        if len(cleaned_queries) >= limit:
            break
    return cleaned_queries


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


def _balance_products_by_marketplace(
    products: list[ProductDTO],
    *,
    page_size: int,
) -> list[ProductDTO]:
    if not products or page_size <= 1:
        return products

    marketplace_order = ["uzum", "wildberries"]
    grouped: dict[str, list[ProductDTO]] = {code: [] for code in marketplace_order}
    other_products: list[ProductDTO] = []
    for product in products:
        marketplace_code = (product.marketplace_code or "").casefold()
        if marketplace_code in grouped:
            grouped[marketplace_code].append(product)
        else:
            other_products.append(product)
    for product in other_products:
        grouped.setdefault(product.marketplace_code or "", []).append(product)

    codes = [code for code in grouped if grouped[code]]
    if len(codes) <= 1:
        return products

    page_size = max(1, page_size)
    cursors = {code: 0 for code in codes}
    balanced: list[ProductDTO] = []
    while len(balanced) < len(products):
        page_limit = min(page_size, len(products) - len(balanced))
        page_codes = [code for code in codes if cursors[code] < len(grouped[code])]
        if not page_codes:
            break
        targets = _marketplace_page_targets(
            page_codes,
            page_limit=page_limit,
            grouped=grouped,
            cursors=cursors,
        )
        if not any(targets.values()):
            break

        while len(balanced) < len(products) and any(targets.values()):
            progressed = False
            for code in page_codes:
                if targets[code] <= 0:
                    continue
                balanced.append(grouped[code][cursors[code]])
                cursors[code] += 1
                targets[code] -= 1
                progressed = True
                if len(balanced) >= len(products):
                    break
            if not progressed:
                break

    return balanced


def _marketplace_page_targets(
    codes: list[str],
    *,
    page_limit: int,
    grouped: dict[str, list[ProductDTO]],
    cursors: dict[str, int],
) -> dict[str, int]:
    base_target, extra = divmod(page_limit, len(codes))
    targets = {
        code: base_target + (1 if index < extra else 0)
        for index, code in enumerate(codes)
    }

    deficit = 0
    for code in codes:
        available = len(grouped[code]) - cursors[code]
        if targets[code] > available:
            deficit += targets[code] - available
            targets[code] = available

    while deficit > 0:
        progressed = False
        for code in codes:
            spare = len(grouped[code]) - cursors[code] - targets[code]
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
            timeout=_catalog_search_api_timeout(config),
        ) as client:
            for query in queries:
                query_products = await client.search_products(
                    query=query,
                    limit=query_limit,
                    offset=0,
                    balance_page_size=config.product_search_limit,
                )
                logger.info(
                    "Photo candidate query=%r returned %s products.",
                    query,
                    len(query_products),
                )
                if query_products and not products:
                    used_query = query
                products = _merge_unique_products(
                    products,
                    query_products,
                )
                if len(products) >= config.openai_photo_candidate_limit:
                    break
            exact_products = _photo_exact_candidate_products(
                photo_query=photo_query,
                products=products,
            )
            if (not products or (_photo_brand_tokens(photo_query.brand) and not exact_products)):
                backfilled = await _request_search_backfill_and_wait(
                    queries=queries,
                    config=config,
                    message=message,
                    source="bot_photo_search_miss",
                    client=client,
                )
                if backfilled:
                    products = []
                    for query in queries:
                        query_products = await client.search_products(
                            query=query,
                            limit=query_limit,
                            offset=0,
                            balance_page_size=config.product_search_limit,
                        )
                        logger.info(
                            "Photo candidate query=%r returned %s products after backfill.",
                            query,
                            len(query_products),
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
                if _photo_brand_tokens(photo_query.brand):
                    return used_query, [], "none"
                substitute_query, substitute_products = await _load_photo_substitute_products(
                    client=client,
                    photo_query=photo_query,
                    config=config,
                )
                if substitute_products:
                    return (
                        substitute_query,
                        _balance_products_by_marketplace(
                            substitute_products,
                            page_size=config.product_search_limit,
                        ),
                        "substitute",
                    )
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
    exact_products = _photo_exact_candidate_products(photo_query=photo_query, products=products)
    if _photo_brand_tokens(photo_query.brand) and not exact_products:
        return used_query, [], "none"
    if exact_products:
        products = exact_products

    ranked_products = await rerank_photo_products_by_image(
        image_bytes=image_bytes,
        mime_type="image/jpeg",
        photo_query=photo_query,
        products=products,
        config=config,
    )
    if ranked_products is None:
        if config.openai_photo_text_fallback_enabled:
            return (
                used_query,
                _balance_products_by_marketplace(
                    products,
                    page_size=config.product_search_limit,
                ),
                "text",
            )
        await message.answer(
            format_message("photo_ai_unavailable", language),
            reply_markup=main_menu_keyboard(language),
        )
        return used_query, None, "none"
    if ranked_products:
        ranked_products = _photo_exact_candidate_products(
            photo_query=photo_query,
            products=ranked_products,
        )
    if ranked_products:
        return (
            used_query,
            _balance_products_by_marketplace(
                ranked_products,
                page_size=config.product_search_limit,
            ),
            "ai",
        )
    safe_text_fallback = _photo_text_fallback_products(
        photo_query=photo_query,
        products=products,
        limit=max(config.product_search_limit, config.openai_photo_candidate_limit),
    )
    if safe_text_fallback:
        return (
            used_query,
            _balance_products_by_marketplace(
                safe_text_fallback,
                page_size=config.product_search_limit,
            ),
            "text",
        )
    if _photo_brand_tokens(photo_query.brand):
        return used_query, [], "none"
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=_catalog_search_api_timeout(config),
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
        return (
            substitute_query,
            _balance_products_by_marketplace(
                substitute_products,
                page_size=config.product_search_limit,
            ),
            "substitute",
        )
    return used_query, [], "none"


async def _track_photo_search_result(
    *,
    config: Config,
    message: Message,
    language: str,
    photo_query: PhotoSearchQuery,
    used_query: str,
    mode: str,
    result_count: int,
) -> None:
    await track_message_event(
        config=config,
        message=message,
        event_type="photo_search_result",
        language_code=language,
        input_type="photo",
        query=used_query,
        result_count=result_count,
        metadata={
            "mode": mode,
            "identified_query": photo_query.query,
            "brand": photo_query.brand,
            "object_type": photo_query.object_type,
            "visible_text": photo_query.visible_text,
            "visible_product": photo_query.visible_product,
            "confidence": photo_query.confidence,
            "alternative_queries": photo_query.alternative_queries,
        },
    )


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
            balance_page_size=config.product_search_limit,
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
        photo_query.brand,
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
    tokens = {token for token in _query_tokens(brand) if len(token) >= 3}
    expanded = set(tokens)
    for token in tokens:
        expanded.update(PHOTO_BRAND_TOKEN_ALIASES.get(token, set()))
    return expanded


def _photo_exact_candidate_products(
    *,
    photo_query: PhotoSearchQuery,
    products: list[ProductDTO],
) -> list[ProductDTO]:
    brand_tokens = _photo_brand_tokens(photo_query.brand)
    if not brand_tokens:
        return products

    object_tokens = set(_query_tokens(photo_query.object_type))
    allowed_object_tokens = object_tokens & PHOTO_TEXT_FALLBACK_OBJECT_TOKENS
    filtered = []
    for product in products:
        product_tokens = _product_tokens(product)
        if not brand_tokens & product_tokens:
            continue
        if allowed_object_tokens and not allowed_object_tokens & product_tokens:
            continue
        filtered.append(product)
    return filtered


def _product_tokens(product: ProductDTO) -> set[str]:
    return set(
        _query_tokens(
            " ".join(
                part
                for part in (product.title, product.brand, product.category_path_text)
                if part
            )
        )
    )


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
            timeout=_catalog_search_api_timeout(config),
        ) as client:
            products = await client.visual_search_products(
                ahash=fingerprint.ahash,
                dhash=fingerprint.dhash,
                max_distance=config.photo_visual_match_max_distance,
                limit=max(config.product_search_limit, 25),
            )
            if products:
                return _balance_products_by_marketplace(
                    products,
                    page_size=config.product_search_limit,
                )

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
            products = await client.visual_search_products(
                ahash=fingerprint.ahash,
                dhash=fingerprint.dhash,
                max_distance=config.photo_visual_match_max_distance,
                limit=max(config.product_search_limit, 25),
            )
            return _balance_products_by_marketplace(
                products,
                page_size=config.product_search_limit,
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
                "marketplace_code": product.marketplace_code or "",
                "marketplace_name": product.marketplace_name or "",
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
        caption = render_product_card(
            product_for_render,
            index,
            language_code,
            marketplace_custom_emoji_ids=config.marketplace_custom_emoji_ids,
        )
        if product.cover_image_url:
            photo = await _telegram_cover_photo(product.cover_image_url, config)
            try:
                await message.answer_photo(
                    photo=photo,
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


async def _telegram_cover_photo(
    cover_image_url: str,
    config: Config,
) -> str | BufferedInputFile:
    if not _cover_url_needs_jpeg_upload(cover_image_url):
        return cover_image_url

    image_bytes = await _download_cover_image(
        cover_image_url,
        timeout=min(max(config.server_api_timeout, 1.0), 10.0),
    )
    if image_bytes is None:
        return cover_image_url

    jpeg_bytes = _cover_image_to_jpeg(image_bytes)
    if jpeg_bytes is None:
        return cover_image_url
    return BufferedInputFile(jpeg_bytes, filename="product-cover.jpg")


def _cover_url_needs_jpeg_upload(cover_image_url: str) -> bool:
    return bool(WEBP_COVER_RE.search(cover_image_url))


async def _download_cover_image(cover_image_url: str, *, timeout: float) -> bytes | None:
    headers = {
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (compatible; IzlaberBot/1.0)",
    }
    try:
        async with ClientSession(timeout=ClientTimeout(total=timeout), headers=headers) as session:
            async with session.get(cover_image_url) as response:
                if response.status != 200:
                    logger.warning(
                        "Cannot download product cover %s: HTTP %s",
                        cover_image_url,
                        response.status,
                    )
                    return None
                content_length = response.content_length
                if content_length and content_length > MAX_COVER_DOWNLOAD_BYTES:
                    logger.warning(
                        "Product cover is too large: %s bytes for %s",
                        content_length,
                        cover_image_url,
                    )
                    return None
                image_bytes = await response.read()
    except (TimeoutError, ClientError) as error:
        logger.warning("Cannot download product cover %s: %s", cover_image_url, error)
        return None

    if len(image_bytes) > MAX_COVER_DOWNLOAD_BYTES:
        logger.warning(
            "Product cover is too large after download: %s bytes for %s",
            len(image_bytes),
            cover_image_url,
        )
        return None
    return image_bytes


def _cover_image_to_jpeg(image_bytes: bytes) -> bytes | None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as error:
        logger.warning("Pillow is required to convert product cover: %s", error)
        return None

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except (OSError, UnidentifiedImageError) as error:
        logger.warning("Cannot convert product cover to JPEG: %s", error)
        return None


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


async def _send_guest_search_started_message(message: Message, language: str) -> Message | None:
    topic_id = _direct_messages_topic_id(message)
    try:
        return await message.answer(
            format_message("search_processing", language),
            direct_messages_topic_id=topic_id,
            disable_web_page_preview=True,
        )
    except TelegramAPIError as error:
        logger.warning("Telegram rejected guest search status message: %s", error)
        return None


def _direct_messages_topic_id(message: Message) -> int | None:
    topic = getattr(message, "direct_messages_topic", None)
    topic_id = getattr(topic, "topic_id", None)
    return topic_id if isinstance(topic_id, int) else None


async def _answer_guest_query(
    message: Message,
    *,
    guest_query_id: str,
    title: str,
    text: str,
    description: str | None = None,
    thumbnail_url: str | None = None,
) -> str | None:
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
        sent_message = await message.bot.answer_guest_query(
            guest_query_id=guest_query_id,
            result=result,
        )
    except TelegramAPIError as error:
        logger.warning("Telegram rejected guest query answer %s: %s", guest_query_id, error)
        return None
    return sent_message.inline_message_id


async def _edit_guest_message(
    message: Message,
    *,
    inline_message_id: str | None,
    text: str,
) -> None:
    if not inline_message_id:
        logger.warning("Cannot edit guest result: inline_message_id is empty.")
        return
    try:
        await message.bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramAPIError as error:
        logger.warning("Telegram rejected guest result edit %s: %s", inline_message_id, error)


async def _finish_guest_query(
    message: Message,
    *,
    guest_query_id: str,
    inline_message_id: str | None,
    title: str,
    text: str,
    description: str | None = None,
    thumbnail_url: str | None = None,
) -> None:
    if inline_message_id:
        await _edit_guest_message(message, inline_message_id=inline_message_id, text=text)
        return
    await _answer_guest_query(
        message,
        guest_query_id=guest_query_id,
        title=title,
        text=text,
        description=description,
        thumbnail_url=thumbnail_url,
    )


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
