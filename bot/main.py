import asyncio
import logging
import sys
from contextlib import suppress
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import load_config
from bot.loader import create_bot, create_dispatcher
from bot.services.ai_monitor import monitor_openai_balance


async def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if config.openai_rerank_enabled and not config.openai_api_key:
        logging.getLogger(__name__).warning("OPENAI_API_KEY is not set; AI rerank is disabled.")

    bot = create_bot(config.bot)
    dispatcher = create_dispatcher(config)

    await bot.delete_webhook(drop_pending_updates=True)
    monitor_task = asyncio.create_task(monitor_openai_balance(bot, config))
    try:
        await dispatcher.start_polling(bot)
    finally:
        monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")


if __name__ == "__main__":
    run()
