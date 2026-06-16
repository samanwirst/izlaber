from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(
        "Напишите название товара, и я найду 3 карточки на Uzum.",
        reply_markup=main_menu_keyboard(),
    )
