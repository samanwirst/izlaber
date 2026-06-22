from bot.keyboards.main_menu import is_more_button_text, main_menu_keyboard, more_results_keyboard
from bot.locales import (
    LOCALES,
    PROFILE_LANGUAGE_CODES,
    locale_for,
    normalize_language_code,
    product_noun,
    review_text,
)


def test_language_code_normalization_uses_uzbek_fallback():
    assert normalize_language_code(None) == "uz"
    assert normalize_language_code("uz-Cyrl") == "uz"
    assert normalize_language_code("ru-RU") == "ru"
    assert normalize_language_code("en_US") == "en"
    assert normalize_language_code("de") == "uz"


def test_profile_texts_match_telegram_limits():
    assert PROFILE_LANGUAGE_CODES == (None, "uz", "ru", "en")
    for locale in LOCALES.values():
        assert len(locale.bot_name) <= 64
        assert len(locale.short_description) <= 120
        assert len(locale.description) <= 512
        assert set(locale.command_descriptions) == {"start", "help"}
        for command_description in locale.command_descriptions.values():
            assert 1 <= len(command_description) <= 256


def test_more_button_accepts_all_localized_values():
    assert is_more_button_text("Yana")
    assert is_more_button_text(" еще ")
    assert is_more_button_text("MORE")
    assert not is_more_button_text("iphone")


def test_keyboards_are_localized():
    uz_keyboard = more_results_keyboard("uz")
    ru_keyboard = more_results_keyboard("ru")
    en_keyboard = main_menu_keyboard("en")

    assert uz_keyboard.keyboard[0][0].text == "Yana"
    assert ru_keyboard.keyboard[0][0].text == "Еще"
    assert en_keyboard.input_field_placeholder == "Type a product to search"


def test_product_copy_pluralization():
    assert review_text(1, "ru") == "1 отзыв"
    assert review_text(2, "ru") == "2 отзыва"
    assert review_text(5, "ru") == "5 отзывов"
    assert review_text(1, "en") == "1 review"
    assert review_text(2, "en") == "2 reviews"
    assert review_text(8, "uz") == "8 sharh"
    assert product_noun(5, "ru") == "товаров"
    assert locale_for("fr").code == "uz"
