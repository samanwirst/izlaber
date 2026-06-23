from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import Config
from bot.keyboards.consent import is_consent_accept_text
from bot.keyboards.main_menu import is_more_button_text
from bot.locales import format_message, language_from_message, normalize_language_code
from bot.services.rate_limit import RateLimitRule, rate_limiter, search_inflight_gate

GENERAL_SCOPE = "general"
SEARCH_SCOPE = "search"
AI_SCOPE = "ai"
NOTICE_SCOPE = "rate_limit_notice"
SEARCH_IN_PROGRESS_SCOPE = "search_in_progress"
NOTICE_RULE = RateLimitRule(scope=NOTICE_SCOPE, max_events=1, window_seconds=10)
SEARCH_IN_PROGRESS_NOTICE_RULE = RateLimitRule(
    scope=f"{SEARCH_IN_PROGRESS_SCOPE}_notice",
    max_events=1,
    window_seconds=8,
)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        config = data.get("config")
        if not isinstance(config, Config) or not config.rate_limit_enabled:
            return await handler(event, data)

        user_id = _user_id(event)
        if user_id is None:
            return await handler(event, data)

        rules = _event_rules(event, config)
        scopes = {rule.scope for rule in rules}
        gate_acquired = False

        if config.search_inflight_limit_enabled and SEARCH_SCOPE in scopes:
            gate_acquired = await search_inflight_gate.acquire(
                user_id=user_id,
                scope=SEARCH_IN_PROGRESS_SCOPE,
            )
            if not gate_acquired:
                async with self._lock:
                    can_notify = rate_limiter.check(
                        user_id=user_id,
                        rule=SEARCH_IN_PROGRESS_NOTICE_RULE,
                    ).allowed
                if can_notify:
                    await _send_search_in_progress_notice(event)
                return None

        try:
            if _admin_bypasses_limit(user_id, config, scopes=scopes):
                return await handler(event, data)

            async with self._lock:
                decision = rate_limiter.check_many(user_id=user_id, rules=rules)
                can_notify = decision.allowed or rate_limiter.check(
                    user_id=user_id,
                    rule=NOTICE_RULE,
                ).allowed

            if decision.allowed:
                return await handler(event, data)

            if can_notify:
                await _send_rate_limit_notice(
                    event,
                    scope=decision.scope,
                    retry_after_seconds=decision.retry_after_seconds,
                )
            return None
        finally:
            if gate_acquired:
                await search_inflight_gate.release(
                    user_id=user_id,
                    scope=SEARCH_IN_PROGRESS_SCOPE,
                )


def _event_rules(event: TelegramObject, config: Config) -> list[RateLimitRule]:
    scopes = _event_scopes(event)
    rules = [
        RateLimitRule(
            scope=GENERAL_SCOPE,
            max_events=config.rate_limit_max_events,
            window_seconds=config.rate_limit_window_seconds,
        )
    ]
    if SEARCH_SCOPE in scopes:
        rules.append(
            RateLimitRule(
                scope=SEARCH_SCOPE,
                max_events=config.search_rate_limit_max_events,
                window_seconds=config.search_rate_limit_window_seconds,
            )
        )
    if AI_SCOPE in scopes or _text_search_can_use_ai(event, config):
        rules.append(
            RateLimitRule(
                scope=AI_SCOPE,
                max_events=config.ai_rate_limit_max_events,
                window_seconds=config.ai_rate_limit_window_seconds,
            )
        )
    return rules


def _text_search_can_use_ai(event: TelegramObject, config: Config) -> bool:
    if not isinstance(event, Message):
        return False
    text = (event.text or "").strip()
    if (
        not text
        or text.startswith("/")
        or is_more_button_text(text)
        or is_consent_accept_text(text)
    ):
        return False
    return bool(config.openai_rerank_enabled or config.openai_search_expand_enabled)


def _event_scopes(event: TelegramObject) -> set[str]:
    scopes = {GENERAL_SCOPE}
    if not isinstance(event, Message):
        return scopes

    if event.photo or event.voice:
        scopes.update({SEARCH_SCOPE, AI_SCOPE})
        return scopes

    text = (event.text or "").strip()
    if not text:
        return scopes
    if is_consent_accept_text(text):
        return scopes
    if is_more_button_text(text) or not text.startswith("/"):
        scopes.add(SEARCH_SCOPE)
    return scopes


def _user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    user_id = getattr(user, "id", None)
    if user_id is not None:
        return int(user_id)

    chat = getattr(event, "chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is not None:
        return int(chat_id)
    if isinstance(event, CallbackQuery) and event.message is not None:
        chat = getattr(event.message, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is not None:
            return int(chat_id)
    return None


def _admin_bypasses_limit(
    user_id: int,
    config: Config,
    *,
    scopes: set[str] | None = None,
) -> bool:
    if scopes and (SEARCH_SCOPE in scopes or AI_SCOPE in scopes):
        return False
    return bool(
        config.rate_limit_admin_bypass
        and config.openai_status_notify_user_id is not None
        and user_id == config.openai_status_notify_user_id
    )


async def _send_rate_limit_notice(
    event: TelegramObject,
    *,
    scope: str,
    retry_after_seconds: int,
) -> None:
    language = language_from_message(event)
    retry_after = _format_retry_after(retry_after_seconds, language)
    key = "ai_rate_limited" if scope == AI_SCOPE else "rate_limited"
    text = format_message(key, language, retry_after=retry_after)

    if isinstance(event, CallbackQuery):
        await event.answer(format_message(key, language, html=False, retry_after=retry_after))
        return
    if isinstance(event, Message):
        await event.answer(text)


async def _send_search_in_progress_notice(event: TelegramObject) -> None:
    language = language_from_message(event)
    text = format_message("search_in_progress", language)

    if isinstance(event, CallbackQuery):
        await event.answer(format_message("search_in_progress", language, html=False))
        return
    if isinstance(event, Message):
        await event.answer(text)


def _format_retry_after(seconds: int, language_code: str | None) -> str:
    language = normalize_language_code(language_code)
    seconds = max(1, int(seconds))
    if seconds < 60:
        if language == "ru":
            return f"{seconds} сек."
        if language == "en":
            return f"{seconds} sec"
        return f"{seconds} soniya"

    minutes = max(1, (seconds + 59) // 60)
    if language == "ru":
        return f"{minutes} мин."
    if language == "en":
        return f"{minutes} min"
    return f"{minutes} daqiqa"
