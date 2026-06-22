from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import Config
from bot.keyboards.main_menu import main_menu_keyboard
from bot.locales import language_from_message, locale_for
from bot.services.analytics import track_message_event

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message, config: Config) -> None:
    language = language_from_message(message)
    locale = locale_for(language)
    await track_message_event(
        config=config,
        message=message,
        event_type="bot_start",
        language_code=language,
        input_type="command",
    )
    await message.answer(
        locale.start_text,
        reply_markup=main_menu_keyboard(language),
    )


@router.message(Command("help"))
async def command_help(message: Message, config: Config) -> None:
    language = language_from_message(message)
    locale = locale_for(language)
    await track_message_event(
        config=config,
        message=message,
        event_type="bot_help",
        language_code=language,
        input_type="command",
    )
    await message.answer(
        locale.help_text,
        reply_markup=main_menu_keyboard(language),
    )
