import asyncio
import logging
import sys
from contextlib import suppress
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import load_config
from bot.loader import create_bot, create_dispatcher
from bot.services.ai_monitor import monitor_openai_balance
from bot.services.api_client import ServerAPIClient, ServerAPIError
from bot.services.consent_store import user_consents
from bot.services.language_store import language_preferences

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if config.openai_rerank_enabled and not config.openai_api_key:
        logger.warning("OPENAI_API_KEY is not set; AI rerank is disabled.")

    bot = create_bot(config.bot)
    dispatcher = create_dispatcher(config)

    if config.bot_api_key:
        try:
            async with ServerAPIClient(
                config.server_api_base_url,
                config.bot_api_key,
                timeout=config.server_api_timeout,
            ) as client:
                await language_preferences.preload(client)
                await user_consents.preload(client, config.consent_version)
        except ServerAPIError as error:
            logger.warning("Bot user state preload failed: %s", error)

    monitor_task: asyncio.Task[None] | None = None
    try:
        await _delete_webhook_with_retries(bot)
        monitor_task = asyncio.create_task(monitor_openai_balance(bot, config))
        await dispatcher.start_polling(bot)
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await monitor_task
        await bot.session.close()


async def _delete_webhook_with_retries(bot: Bot, *, attempts: int = 4) -> None:
    for attempt in range(1, attempts + 1):
        try:
            await bot.delete_webhook(drop_pending_updates=True, request_timeout=30)
            return
        except TelegramNetworkError as error:
            if attempt >= attempts:
                raise
            delay = min(5 * attempt, 20)
            logger.warning(
                "Telegram delete_webhook failed on attempt %s/%s: %s. Retrying in %ss.",
                attempt,
                attempts,
                error,
                delay,
            )
            await asyncio.sleep(delay)


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")


if __name__ == "__main__":
    run()
