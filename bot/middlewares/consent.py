from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import Config
from bot.keyboards.consent import (
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_REVOKE_CALLBACK,
    consent_request_keyboard,
    is_consent_accept_text,
)
from bot.locales import consent_multilingual_button, format_consent_prompt
from bot.services.consent_store import user_consents

CONSENT_CALLBACKS = {
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_REVOKE_CALLBACK,
}


class ConsentMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        config = data.get("config")
        if not isinstance(config, Config) or not config.consent_enabled:
            return await handler(event, data)

        user_id = _user_id(event)
        if user_consents.has_active(user_id) or _is_consent_event(event):
            return await handler(event, data)

        await _send_consent_prompt(event, config)
        return None


def _user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    return getattr(user, "id", None)


def _is_consent_event(event: TelegramObject) -> bool:
    if isinstance(event, CallbackQuery):
        return event.data in CONSENT_CALLBACKS
    if isinstance(event, Message):
        command = (event.text or "").strip().split(maxsplit=1)[0].casefold()
        return (
            command == "/consent"
            or command.startswith("/consent@")
            or is_consent_accept_text(event.text)
        )
    return False


async def _send_consent_prompt(event: TelegramObject, config: Config) -> None:
    text = format_consent_prompt(
        None,
        privacy_policy_url=config.privacy_policy_url,
        sponsored_ads_policy_url=config.sponsored_ads_policy_url,
        multilingual=True,
    )
    keyboard = consent_request_keyboard(None, config, multilingual=True)

    if isinstance(event, CallbackQuery):
        await event.answer(consent_multilingual_button("consent_first_alert"))
        if event.message is not None:
            await event.message.answer(text, reply_markup=keyboard)
        return

    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard)
