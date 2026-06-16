import logging

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Config
from bot.services.uzum import (
    UzumSearchError,
    UzumSearchService,
    render_products,
    render_search_unavailable,
)

router = Router(name="common")
logger = logging.getLogger(__name__)


@router.message(F.text)
async def search_uzum(message: Message, config: Config) -> None:
    query = message.text or ""
    service = UzumSearchService(config.uzum_graphql_url)

    try:
        products = await service.search(query, limit=3)
    except UzumSearchError as error:
        logger.warning("Uzum search failed for query %r: %s", query, error)
        await message.answer(
            render_search_unavailable(query),
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        render_products(products, query),
        disable_web_page_preview=True,
    )
