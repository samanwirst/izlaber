from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import BotCommand

from bot.locales import PROFILE_LANGUAGE_CODES, profile_locale_for

PROFILE_UPDATE_RETRIES = 3


async def setup_bot_profile(bot: Bot) -> list[str]:
    updated: list[str] = []
    for language_code in PROFILE_LANGUAGE_CODES:
        locale = profile_locale_for(language_code)
        commands = [
            BotCommand(command="start", description=locale.command_descriptions["start"]),
            BotCommand(command="help", description=locale.command_descriptions["help"]),
        ]
        bot_name = locale.bot_name
        short_description = locale.short_description
        description = locale.description
        await _telegram_call(
            lambda bot_name=bot_name, language_code=language_code: bot.set_my_name(
                name=bot_name,
                language_code=language_code,
            )
        )
        await _telegram_call(
            lambda short_description=short_description, language_code=language_code: (
                bot.set_my_short_description(
                    short_description=short_description,
                    language_code=language_code,
                )
            )
        )
        await _telegram_call(
            lambda description=description, language_code=language_code: bot.set_my_description(
                description=description,
                language_code=language_code,
            )
        )
        await _telegram_call(
            lambda commands=commands, language_code=language_code: bot.set_my_commands(
                commands=commands,
                language_code=language_code,
            )
        )
        updated.append(language_code or "default")
    return updated


async def _telegram_call(call: Callable[[], Awaitable[bool]]) -> bool:
    for attempt in range(1, PROFILE_UPDATE_RETRIES + 1):
        try:
            return await call()
        except TelegramRetryAfter as error:
            if attempt == PROFILE_UPDATE_RETRIES:
                raise
            await asyncio.sleep(float(error.retry_after) + 1.0)
        except TelegramNetworkError:
            if attempt == PROFILE_UPDATE_RETRIES:
                raise
            await asyncio.sleep(float(attempt))
    return False
