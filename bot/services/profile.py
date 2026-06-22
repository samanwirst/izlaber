from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import BotCommand

from bot.locales import PROFILE_LANGUAGE_CODES, profile_locale_for

PROFILE_UPDATE_RETRIES = 3
PROFILE_MAX_RETRY_AFTER_SECONDS = 60
T = TypeVar("T")


async def setup_bot_profile(bot: Bot) -> list[str]:
    updated: list[str] = []
    for language_code in PROFILE_LANGUAGE_CODES:
        locale = profile_locale_for(language_code)
        commands = [
            BotCommand(command="start", description=locale.command_descriptions["start"]),
            BotCommand(command="help", description=locale.command_descriptions["help"]),
            BotCommand(command="lang", description=locale.command_descriptions["lang"]),
            BotCommand(command="consent", description=locale.command_descriptions["consent"]),
        ]
        bot_name = locale.bot_name
        short_description = locale.short_description
        description = locale.description
        current_name = await _telegram_call(
            lambda language_code=language_code: bot.get_my_name(language_code=language_code)
        )
        if current_name.name != bot_name:
            await _telegram_call(
                lambda bot_name=bot_name, language_code=language_code: bot.set_my_name(
                    name=bot_name,
                    language_code=language_code,
                )
            )

        current_short_description = await _telegram_call(
            lambda language_code=language_code: bot.get_my_short_description(
                language_code=language_code
            )
        )
        if current_short_description.short_description != short_description:
            await _telegram_call(
                lambda short_description=short_description, language_code=language_code: (
                    bot.set_my_short_description(
                        short_description=short_description,
                        language_code=language_code,
                    )
                )
            )

        current_description = await _telegram_call(
            lambda language_code=language_code: bot.get_my_description(language_code=language_code)
        )
        if current_description.description != description:
            await _telegram_call(
                lambda description=description, language_code=language_code: bot.set_my_description(
                    description=description,
                    language_code=language_code,
                )
            )

        current_commands = await _telegram_call(
            lambda language_code=language_code: bot.get_my_commands(language_code=language_code)
        )
        if _commands_changed(current_commands, commands):
            await _telegram_call(
                lambda commands=commands, language_code=language_code: bot.set_my_commands(
                    commands=commands,
                    language_code=language_code,
                )
            )
        updated.append(language_code or "default")
    return updated


def _commands_changed(current: list[BotCommand], desired: list[BotCommand]) -> bool:
    return [(item.command, item.description) for item in current] != [
        (item.command, item.description) for item in desired
    ]


async def _telegram_call(call: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(1, PROFILE_UPDATE_RETRIES + 1):
        try:
            return await call()
        except TelegramRetryAfter as error:
            if (
                attempt == PROFILE_UPDATE_RETRIES
                or error.retry_after > PROFILE_MAX_RETRY_AFTER_SECONDS
            ):
                raise
            await asyncio.sleep(float(error.retry_after) + 1.0)
        except TelegramNetworkError:
            if attempt == PROFILE_UPDATE_RETRIES:
                raise
            await asyncio.sleep(float(attempt))
    raise RuntimeError("Telegram profile call did not return.")
