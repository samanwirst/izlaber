import asyncio
import logging
import sys

from bot.config import load_config
from bot.loader import create_bot, create_dispatcher


async def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    bot = create_bot(config.bot)
    dispatcher = create_dispatcher(config)

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")
