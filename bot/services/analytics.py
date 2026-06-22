from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.locales import language_from_message
from bot.services.api_client import ServerAPIClient, ServerAPIError

logger = logging.getLogger(__name__)


async def track_message_event(
    *,
    config: Config,
    message: Message,
    event_type: str,
    language_code: str | None = None,
    input_type: str = "",
    query: str = "",
    product_id: int | None = None,
    source_product_id: str | None = None,
    product_position: int | None = None,
    result_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> UUID | None:
    if not config.analytics_enabled or not config.bot_api_key:
        return None
    user = message.from_user
    payload = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "source": "bot",
        "telegram_user_id": user.id if user else None,
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "language_code": language_code or language_from_message(message),
        "input_type": input_type,
        "query": query,
        "product": product_id,
        "source_product_id": source_product_id,
        "product_position": product_position,
        "result_count": result_count,
        "metadata": metadata or {},
    }
    return await _send_event(config=config, payload=_strip_none(payload))


async def track_callback_event(
    *,
    config: Config,
    callback: CallbackQuery,
    event_type: str,
    language_code: str | None = None,
    input_type: str = "callback",
    metadata: dict[str, Any] | None = None,
) -> UUID | None:
    if not config.analytics_enabled or not config.bot_api_key:
        return None
    message = callback.message
    user = callback.from_user
    payload = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "source": "bot",
        "telegram_user_id": user.id if user else None,
        "chat_id": message.chat.id if message else None,
        "message_id": message.message_id if message else None,
        "language_code": language_code or "",
        "input_type": input_type,
        "metadata": metadata or {},
    }
    return await _send_event(config=config, payload=_strip_none(payload))


async def _send_event(*, config: Config, payload: dict[str, Any]) -> UUID | None:
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.analytics_timeout,
        ) as client:
            return await client.create_analytics_event(payload)
    except (ServerAPIError, RuntimeError, ValueError) as error:
        logger.debug("Analytics event %s was not stored: %s", payload.get("event_type"), error)
        return None


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
