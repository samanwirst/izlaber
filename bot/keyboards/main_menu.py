from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MORE_BUTTON_TEXT = "Еще"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="iphone"), KeyboardButton(text="ноутбук")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите товар для поиска",
    )


def more_results_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MORE_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Нажмите Еще или введите новый товар",
    )
