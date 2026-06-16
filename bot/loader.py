from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BotConfig, Config
from bot.handlers import routers
from bot.middlewares import register_middlewares


def create_bot(config: BotConfig) -> Bot:
    parse_mode = ParseMode.HTML if config.parse_mode == "HTML" else config.parse_mode
    return Bot(
        token=config.token,
        default=DefaultBotProperties(parse_mode=parse_mode),
    )


def create_dispatcher(config: Config | None = None) -> Dispatcher:
    workflow_data = {}
    if config is not None:
        workflow_data["config"] = config

    dispatcher = Dispatcher(name="main_dispatcher", **workflow_data)
    register_middlewares(dispatcher)
    dispatcher.include_routers(*routers)
    return dispatcher
