from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.locales import consent_multilingual_button, format_message

CONSENT_ACCEPT_CALLBACK = "consent:accept"
CONSENT_DECLINE_CALLBACK = "consent:decline"
CONSENT_REVOKE_CALLBACK = "consent:revoke"


def consent_request_keyboard(
    language_code: str | None,
    config: Config,
    *,
    multilingual: bool = False,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=_button_text("consent_accept_button", language_code, multilingual),
                callback_data=CONSENT_ACCEPT_CALLBACK,
            )
        ],
        [
            InlineKeyboardButton(
                text=_button_text("consent_decline_button", language_code, multilingual),
                callback_data=CONSENT_DECLINE_CALLBACK,
            )
        ],
    ]
    buttons.extend(_policy_buttons(language_code, config, multilingual=multilingual))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def consent_status_keyboard(language_code: str | None, config: Config) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=format_message("consent_revoke_button", language_code, html=False),
                callback_data=CONSENT_REVOKE_CALLBACK,
            )
        ],
    ]
    buttons.extend(_policy_buttons(language_code, config))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _policy_buttons(
    language_code: str | None,
    config: Config,
    *,
    multilingual: bool = False,
) -> list[list[InlineKeyboardButton]]:
    row = []
    if config.privacy_policy_url:
        row.append(
            InlineKeyboardButton(
                text=_button_text("consent_privacy_button", language_code, multilingual),
                url=config.privacy_policy_url,
            )
        )
    if config.sponsored_ads_policy_url:
        row.append(
            InlineKeyboardButton(
                text=_button_text("consent_ads_button", language_code, multilingual),
                url=config.sponsored_ads_policy_url,
            )
        )
    return [row] if row else []


def _button_text(key: str, language_code: str | None, multilingual: bool) -> str:
    if multilingual:
        return consent_multilingual_button(key)
    return format_message(key, language_code, html=False)
