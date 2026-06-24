from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def language_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:en"),
            ]
        ]
    )
