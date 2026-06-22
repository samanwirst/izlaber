from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.locales import locale_for, more_button_values


def main_menu_keyboard(language_code: str | None = None) -> ReplyKeyboardRemove:
    del language_code
    return ReplyKeyboardRemove()


def more_results_keyboard(language_code: str | None = None) -> ReplyKeyboardMarkup:
    locale = locale_for(language_code)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=locale.more_button)],
        ],
        resize_keyboard=True,
        input_field_placeholder=locale.more_placeholder,
    )


def is_more_button_text(text: str | None) -> bool:
    normalized_text = (text or "").strip().casefold().replace("ё", "е")
    return normalized_text in more_button_values()
