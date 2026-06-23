from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales import locale_for, product_label

MORE_RESULTS_CALLBACK = "products:more"


def product_card_keyboard(
    language_code: str | None,
    *,
    product_url: str,
    include_more: bool,
) -> InlineKeyboardMarkup:
    locale = locale_for(language_code)
    rows = [
        [
            InlineKeyboardButton(
                text=product_label("open_product", language_code),
                url=product_url,
            )
        ]
    ]
    if include_more:
        rows.append(
            [
                InlineKeyboardButton(
                    text=locale.more_button,
                    callback_data=MORE_RESULTS_CALLBACK,
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
