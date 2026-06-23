from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.config import Config
from bot.locales import consent_multilingual_button, format_message

CONSENT_ACCEPT_CALLBACK = "consent:accept"
CONSENT_REVOKE_CALLBACK = "consent:revoke"
CONSENT_ACCEPT_TEXT_ALIASES = {
    "roziman",
    "согласен",
    "согласна",
    "i agree",
    "agree",
}


def consent_request_keyboard(
    language_code: str | None,
    config: Config,
    *,
    multilingual: bool = False,
) -> ReplyKeyboardMarkup:
    del config
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=_button_text("consent_accept_button", language_code, multilingual),
                )
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def is_consent_accept_text(text: str | None) -> bool:
    normalized_text = _normalize_accept_text(text)
    return normalized_text in {
        _normalize_accept_text(_button_text("consent_accept_button", language, False))
        for language in ("uz", "ru", "en")
    } | {
        _normalize_accept_text(_button_text("consent_accept_button", None, True)),
        *CONSENT_ACCEPT_TEXT_ALIASES,
    }


def _button_text(key: str, language_code: str | None, multilingual: bool) -> str:
    if multilingual:
        return consent_multilingual_button(key)
    return format_message(key, language_code, html=False)


def _normalize_accept_text(text: str | None) -> str:
    return (text or "").strip().casefold()
