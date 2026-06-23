from aiogram.types import ReplyKeyboardRemove

from bot.config import BotConfig, Config
from bot.keyboards.consent import consent_request_keyboard, consent_status_keyboard
from bot.keyboards.language import language_selection_keyboard
from bot.keyboards.main_menu import is_more_button_text, main_menu_keyboard, more_results_keyboard
from bot.keyboards.product import product_card_keyboard
from bot.locales import (
    LOCALES,
    PROFILE_LANGUAGE_CODES,
    language_from_message,
    locale_for,
    normalize_language_code,
    product_noun,
    review_text,
)
from bot.services.language_store import language_preferences


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
        assert set(locale.command_descriptions) == {"start", "help", "lang", "consent"}
        for command_description in locale.command_descriptions.values():
            assert 1 <= len(command_description) <= 256


def test_locale_key_sets_match():
    message_keys = set(LOCALES["uz"].messages)
    product_label_keys = set(LOCALES["uz"].product_labels)
    for locale in LOCALES.values():
        assert set(locale.messages) == message_keys
        assert set(locale.product_labels) == product_label_keys


def test_more_button_accepts_all_localized_values():
    assert is_more_button_text("Yana")
    assert is_more_button_text("yana")
    assert is_more_button_text(" еще ")
    assert is_more_button_text("ещё")
    assert is_more_button_text("MORE")
    assert is_more_button_text("more")
    assert not is_more_button_text("iphone")
    assert not is_more_button_text("ещё, пожалуйста")


def test_keyboards_are_localized():
    uz_keyboard = more_results_keyboard("uz")
    ru_keyboard = more_results_keyboard("ru")
    en_keyboard = main_menu_keyboard("en")
    language_keyboard = language_selection_keyboard()
    consent_config = Config(
        bot=BotConfig(token="test"),
        privacy_policy_url="https://example.com/privacy",
        sponsored_ads_policy_url="https://example.com/ads",
    )
    consent_keyboard = consent_request_keyboard("ru", consent_config)
    consent_status = consent_status_keyboard("en", consent_config)

    assert uz_keyboard.keyboard[0][0].text == "Yana ko'rsatish"
    assert ru_keyboard.keyboard[0][0].text == "Показать ещё"
    assert isinstance(en_keyboard, ReplyKeyboardRemove)
    assert [button.text for button in language_keyboard.inline_keyboard[0]] == [
        "O'zbek",
        "Русский",
        "English",
    ]
    assert consent_keyboard.inline_keyboard[0][0].text == "✅ Согласен, начать поиск"
    assert consent_keyboard.inline_keyboard[1][0].text == "Не сейчас"
    assert [button.url for button in consent_keyboard.inline_keyboard[2]] == [
        "https://example.com/privacy",
        "https://example.com/ads",
    ]
    assert consent_status.inline_keyboard[0][0].text == "Revoke consent"

    product_keyboard = product_card_keyboard(
        "en",
        product_url="https://example.com/product",
        include_more=True,
    )
    assert product_keyboard.inline_keyboard[0][0].text == "Open product"
    assert product_keyboard.inline_keyboard[0][0].url == "https://example.com/product"
    assert product_keyboard.inline_keyboard[1][0].text == "Show more"


def test_language_override_takes_precedence_over_telegram_locale():
    class User:
        id = 123
        language_code = "en"

    class Message:
        from_user = User()

    language_preferences.clear_cached(123)
    try:
        assert language_from_message(Message()) == "en"
        language_preferences.set_cached(123, "ru")
        assert language_from_message(Message()) == "ru"
    finally:
        language_preferences.clear_cached(123)


def test_product_copy_pluralization():
    assert review_text(1, "ru") == "1 отзыв"
    assert review_text(2, "ru") == "2 отзыва"
    assert review_text(5, "ru") == "5 отзывов"
    assert review_text(1, "en") == "1 review"
    assert review_text(2, "en") == "2 reviews"
    assert review_text(8, "uz") == "8 sharh"
    assert product_noun(5, "ru") == "товаров"
    assert locale_for("fr").code == "uz"
