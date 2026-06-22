from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu import main_menu_keyboard
from bot.locales import language_from_message, locale_for

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    language = language_from_message(message)
    locale = locale_for(language)
    await message.answer(
        locale.start_text,
        reply_markup=main_menu_keyboard(language),
    )


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    language = language_from_message(message)
    locale = locale_for(language)
    await message.answer(
        locale.help_text,
        reply_markup=main_menu_keyboard(language),
    )
