import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.config import Config
from bot.keyboards.main_menu import MORE_BUTTON_TEXT, main_menu_keyboard, more_results_keyboard
from bot.services.api_client import (
    ProductDTO,
    ServerAPIClient,
    ServerAPIError,
    render_product_card,
)
from bot.services.search_state import search_state

router = Router(name="common")
logger = logging.getLogger(__name__)


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

    products = await _load_products(
        query=session.query,
        offset=session.offset,
        config=config,
        message=message,
    )
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
        offset=session.offset + len(products),
    )
    await _send_products(message, products, start_index=session.offset + 1)


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Напишите название товара.", reply_markup=main_menu_keyboard())
        return

    products = await _load_products(query=query, offset=0, config=config, message=message)
    if products is None:
        return
    if not products:
        search_state.clear(chat_id=message.chat.id, user_id=_user_id(message))
        await message.answer(
            f"В каталоге пока нет товаров по запросу «{query}».",
            reply_markup=main_menu_keyboard(),
        )
        return

    search_state.set(
        chat_id=message.chat.id,
        user_id=_user_id(message),
        query=query,
        offset=len(products),
    )
    await message.answer(
        f"Нашел карточки по запросу «{query}». Показываю первые {len(products)}:",
        reply_markup=more_results_keyboard(),
    )
    await _send_products(message, products, start_index=1)


async def _load_products(
    *,
    query: str,
    offset: int,
    config: Config,
    message: Message,
) -> list[ProductDTO] | None:
    limit = config.product_search_limit

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            return await client.search_products(query=query, limit=limit, offset=offset)
    except ServerAPIError as error:
        logger.warning("Product search failed for query %r: %s", query, error)
        await message.answer(
            "Каталог сейчас недоступен. Попробуйте позже.",
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(),
        )
        return None


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
