from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import load_config
from bot.loader import create_bot
from bot.services.profile import setup_bot_profile


async def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    bot = create_bot(config.bot)
    try:
        updated_languages = await setup_bot_profile(bot)
    finally:
        await bot.session.close()
    print("Updated bot profile languages: " + ", ".join(updated_languages))


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
