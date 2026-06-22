from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards.language import language_selection_keyboard
from bot.locales import format_message, language_from_message, normalize_language_code
from bot.services.analytics import track_callback_event, track_message_event
from bot.services.api_client import ServerAPIClient, ServerAPIError
from bot.services.language_store import language_preferences

router = Router(name="language")


@router.message(Command("lang"))
async def command_lang(message: Message, config: Config) -> None:
    language = language_from_message(message)
    await track_message_event(
        config=config,
        message=message,
        event_type="language_prompt",
        language_code=language,
        input_type="command",
    )
    await message.answer(
        format_message("language_prompt", language),
        reply_markup=language_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def choose_language(callback: CallbackQuery, config: Config) -> None:
    user = callback.from_user
    if user is None or callback.data is None:
        await callback.answer()
        return

    language_code = normalize_language_code(callback.data.split(":", maxsplit=1)[1])
    await callback.answer()

    try:
        async with ServerAPIClient(
            config.server_api_base_url,
            config.bot_api_key,
            timeout=config.server_api_timeout,
        ) as client:
            language_code = await language_preferences.set(user.id, language_code, client)
    except ServerAPIError:
        language_preferences.set_cached(user.id, language_code)

    await track_callback_event(
        config=config,
        callback=callback,
        event_type="language_select",
        language_code=language_code,
        metadata={"selected_language": language_code},
    )
    if callback.message is not None:
        await callback.message.edit_text(
            format_message(
                "language_changed",
                language_code,
                language=_language_label(language_code),
            ),
            reply_markup=None,
        )


def _language_label(language_code: str) -> str:
    if language_code == "uz":
        return "O'zbek"
    if language_code == "ru":
        return "Русский"
    return "English"
