from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales import product_label


def product_card_keyboard(
    language_code: str | None,
    *,
    product_url: str,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=product_label("open_product", language_code),
                url=product_url,
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
