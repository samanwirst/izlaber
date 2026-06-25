from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from aiogram import BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    TelegramObject,
)

from bot.config import Config
from bot.keyboards.consent import (
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_REVOKE_CALLBACK,
    consent_request_keyboard,
    is_consent_accept_text,
)
from bot.locales import (
    consent_multilingual_button,
    format_consent_prompt,
    format_message,
    language_from_message,
)
from bot.services.consent_store import user_consents
from bot.services.telegram_messages import answer_message

logger = logging.getLogger(__name__)
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

        if _is_guest_message(event):
            await _answer_guest_start_required(event)
            return None

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


def _is_guest_message(event: TelegramObject) -> bool:
    return isinstance(event, Message) and bool(getattr(event, "guest_query_id", None))


async def _answer_guest_start_required(message: Message) -> None:
    guest_query_id = getattr(message, "guest_query_id", None)
    if not guest_query_id:
        return

    language = language_from_message(message)
    bot_reference = await _bot_reference(message)
    result = InlineQueryResultArticle(
        id=f"guest-start-required-{uuid4().hex}",
        title=format_message("guest_start_required_title", language, html=False),
        description=format_message("guest_start_required_description", language, html=False),
        input_message_content=InputTextMessageContent(
            message_text=format_message(
                "guest_start_required_text",
                language,
                bot_reference=bot_reference,
            ),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        ),
    )
    try:
        await message.bot.answer_guest_query(guest_query_id=guest_query_id, result=result)
    except TelegramAPIError as error:
        logger.warning(
            "Telegram rejected guest start-required answer %s: %s",
            guest_query_id,
            error,
        )


async def _bot_reference(message: Message) -> str:
    try:
        bot_user = await message.bot.get_me()
    except TelegramAPIError:
        return "Izlaber"
    username = getattr(bot_user, "username", None)
    return f"@{username}" if username else "Izlaber"


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
            await answer_message(event.message, text, reply_markup=keyboard)
        return

    if isinstance(event, Message):
        await answer_message(event, text, reply_markup=keyboard)
