from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards.consent import (
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_DECLINE_CALLBACK,
    CONSENT_REVOKE_CALLBACK,
    consent_request_keyboard,
    consent_status_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.locales import format_message, language_from_message, locale_for
from bot.services.api_client import ServerAPIClient, ServerAPIError
from bot.services.consent_store import user_consents

router = Router(name="consent")


@router.message(Command("consent"))
async def command_consent(message: Message, config: Config) -> None:
    language = language_from_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_consents.has_active(user_id):
        await message.answer(
            format_message("consent_status_active", language),
            reply_markup=consent_status_keyboard(language, config),
        )
        return

    await message.answer(
        format_message("consent_required", language),
        reply_markup=consent_request_keyboard(language, config),
    )


@router.callback_query(F.data.in_({CONSENT_ACCEPT_CALLBACK, CONSENT_DECLINE_CALLBACK}))
async def choose_consent(callback: CallbackQuery, config: Config) -> None:
    if callback.data is None:
        await callback.answer()
        return

    language = language_from_message(callback)
    action = callback.data.split(":", maxsplit=1)[1]
    active = await _persist_consent(callback, config, action=action, language_code=language)
    if active is None:
        return

    await callback.answer()
    if callback.message is None:
        return

    if action == "accept" and active:
        locale = locale_for(language)
        await callback.message.edit_text(
            "\n\n".join(
                [
                    format_message("consent_accepted", language),
                    locale.start_text,
                ]
            ),
            reply_markup=None,
        )
        await callback.message.answer(
            format_message("consent_ready", language),
            reply_markup=main_menu_keyboard(language),
        )
        return

    await callback.message.edit_text(
        format_message("consent_declined", language),
        reply_markup=consent_request_keyboard(language, config),
    )


@router.callback_query(F.data == CONSENT_REVOKE_CALLBACK)
async def revoke_consent(callback: CallbackQuery, config: Config) -> None:
    language = language_from_message(callback)
    active = await _persist_consent(callback, config, action="revoke", language_code=language)
    if active is None:
        return

    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(
            format_message("consent_revoked", language),
            reply_markup=consent_request_keyboard(language, config),
        )


async def _persist_consent(
    callback: CallbackQuery,
    config: Config,
    *,
    action: str,
    language_code: str,
) -> bool | None:
    user_id = callback.from_user.id if callback.from_user else None
    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            return await user_consents.set_consent(
                user_id=user_id,
                action=action,
                consent_version=config.consent_version,
                language_code=language_code,
                client=client,
            )
    except ServerAPIError:
        await callback.answer(format_message("consent_save_failed", language_code, html=False))
        if callback.message is not None:
            await callback.message.answer(format_message("consent_save_failed", language_code))
        return None
