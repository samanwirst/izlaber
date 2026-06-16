from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="iphone")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите товар для поиска",
    )
