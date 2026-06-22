from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.locales import locale_for, more_button_values


def main_menu_keyboard(language_code: str | None = None) -> ReplyKeyboardMarkup:
    locale = locale_for(language_code)
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=locale.main_buttons[0]),
                KeyboardButton(text=locale.main_buttons[1]),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder=locale.main_placeholder,
    )


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
    return (text or "").strip().casefold() in more_button_values()
