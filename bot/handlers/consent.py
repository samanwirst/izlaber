from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards.consent import (
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_REVOKE_CALLBACK,
    consent_request_keyboard,
    is_consent_accept_text,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.locales import (
    format_consent_policy_links,
    format_consent_prompt,
    format_message,
    language_from_message,
    locale_for,
)
from bot.services.api_client import ServerAPIClient, ServerAPIError
from bot.services.consent_store import user_consents

router = Router(name="consent")
REVOKE_COMMAND_ARGS = {
    "revoke",
    "cancel",
    "withdraw",
    "отозвать",
    "отмена",
    "bekor",
    "bekor qilish",
}


@router.message(Command("consent"))
async def command_consent(message: Message, config: Config) -> None:
    language = language_from_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_consents.has_active(user_id) and _is_revoke_command(message):
        active = await _persist_message_consent(
            message,
            config,
            action="revoke",
            language_code=language,
        )
        if active is None:
            return
        await _send_revoked_prompt(message, config, language)
        return

    if user_consents.has_active(user_id):
        policy_links = format_consent_policy_links(
            language,
            privacy_policy_url=config.privacy_policy_url,
            sponsored_ads_policy_url=config.sponsored_ads_policy_url,
        )
        text = format_message("consent_status_active", language)
        if policy_links:
            text = f"{text}\n\n{policy_links}"
        await message.answer(
            text,
            reply_markup=main_menu_keyboard(language),
        )
        return

    await message.answer(
        format_consent_prompt(
            language,
            privacy_policy_url=config.privacy_policy_url,
            sponsored_ads_policy_url=config.sponsored_ads_policy_url,
            multilingual=True,
        ),
        reply_markup=consent_request_keyboard(language, config, multilingual=True),
    )


@router.message(F.text.func(is_consent_accept_text))
async def accept_consent_message(message: Message, config: Config) -> None:
    language = language_from_message(message)
    active = await _persist_message_consent(
        message,
        config,
        action="accept",
        language_code=language,
    )
    if active:
        await _send_accept_success(message, language)


@router.callback_query(F.data == CONSENT_ACCEPT_CALLBACK)
async def accept_consent_callback(callback: CallbackQuery, config: Config) -> None:
    if callback.data is None:
        await callback.answer()
        return

    language = language_from_message(callback)
    active = await _persist_callback_consent(
        callback,
        config,
        action="accept",
        language_code=language,
    )
    if active is None:
        return

    await callback.answer()
    if callback.message is None:
        return

    if active:
        await callback.message.edit_text(
            _accepted_text(language),
            reply_markup=None,
        )
        await callback.message.answer(
            format_message("consent_ready", language),
            reply_markup=main_menu_keyboard(language),
        )


@router.callback_query(F.data == CONSENT_REVOKE_CALLBACK)
async def revoke_consent(callback: CallbackQuery, config: Config) -> None:
    language = language_from_message(callback)
    active = await _persist_callback_consent(
        callback,
        config,
        action="revoke",
        language_code=language,
    )
    if active is None:
        return

    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(
            format_message("consent_revoked", language),
            reply_markup=None,
        )
        await callback.message.answer(
            format_consent_prompt(
                language,
                privacy_policy_url=config.privacy_policy_url,
                sponsored_ads_policy_url=config.sponsored_ads_policy_url,
                multilingual=True,
            ),
            reply_markup=consent_request_keyboard(language, config, multilingual=True),
        )


async def _persist_callback_consent(
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


async def _persist_message_consent(
    message: Message,
    config: Config,
    *,
    action: str,
    language_code: str,
) -> bool | None:
    user_id = message.from_user.id if message.from_user else None
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
        await message.answer(format_message("consent_save_failed", language_code))
        return None


async def _send_accept_success(message: Message, language_code: str) -> None:
    await message.answer(
        _accepted_text(language_code),
        reply_markup=main_menu_keyboard(language_code),
    )
    await message.answer(
        format_message("consent_ready", language_code),
        reply_markup=main_menu_keyboard(language_code),
    )


async def _send_revoked_prompt(message: Message, config: Config, language_code: str) -> None:
    await message.answer(
        "\n\n".join(
            [
                format_message("consent_revoked", language_code),
                format_consent_prompt(
                    language_code,
                    privacy_policy_url=config.privacy_policy_url,
                    sponsored_ads_policy_url=config.sponsored_ads_policy_url,
                    multilingual=True,
                ),
            ]
        ),
        reply_markup=consent_request_keyboard(language_code, config, multilingual=True),
    )


def _accepted_text(language_code: str) -> str:
    locale = locale_for(language_code)
    return "\n\n".join(
        [
            format_message("consent_accepted", language_code),
            locale.start_text,
        ]
    )


def _is_revoke_command(message: Message) -> bool:
    args = (message.text or "").strip().split(maxsplit=1)
    if len(args) < 2:
        return False
    return args[1].strip().casefold() in REVOKE_COMMAND_ARGS
