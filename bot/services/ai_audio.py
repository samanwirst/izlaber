from __future__ import annotations

import logging

from aiohttp import ClientError, ClientSession, ClientTimeout, FormData

from bot.config import Config
from bot.services.ai_reranker import _is_quota_exhausted_response
from bot.services.ai_runtime import ai_runtime_state

logger = logging.getLogger(__name__)

AUDIO_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"


class AIVoiceSearchError(RuntimeError):
    def __init__(self, message: str, *, quota_exhausted: bool = False) -> None:
        super().__init__(message)
        self.quota_exhausted = quota_exhausted


async def transcribe_voice_message(
    *,
    audio_bytes: bytes,
    filename: str,
    config: Config,
    language_hint: str | None = None,
) -> str | None:
    if not _enabled(config):
        return None

    try:
        transcript = await _request_transcription(
            audio_bytes=audio_bytes,
            filename=filename,
            config=config,
            language_hint=language_hint,
        )
    except AIVoiceSearchError as error:
        logger.warning("OpenAI voice transcription failed: %s", error)
        if error.quota_exhausted:
            ai_runtime_state.mark_quota_exhausted(str(error))
        return None
    return transcript or None


def _enabled(config: Config) -> bool:
    return bool(
        config.openai_voice_search_enabled
        and config.openai_api_key
        and ai_runtime_state.ai_allowed()
    )


async def _request_transcription(
    *,
    audio_bytes: bytes,
    filename: str,
    config: Config,
    language_hint: str | None,
) -> str:
    form = FormData()
    form.add_field(
        "file",
        audio_bytes,
        filename=filename,
        content_type="audio/ogg",
    )
    form.add_field("model", config.openai_voice_model)
    form.add_field("response_format", "text")
    if prompt := _transcription_prompt(language_hint):
        form.add_field("prompt", prompt)

    headers = {
        "Authorization": f"Bearer {config.openai_api_key}",
    }
    timeout = ClientTimeout(total=config.openai_voice_timeout)
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(AUDIO_TRANSCRIPTIONS_URL, data=form) as response:
                body = await response.text()
                if response.status >= 400:
                    raise AIVoiceSearchError(
                        f"HTTP {response.status}: {body[:300]}",
                        quota_exhausted=_is_quota_exhausted_response(
                            status=response.status,
                            body=body,
                        ),
                    )
    except (ClientError, TimeoutError) as error:
        raise AIVoiceSearchError(str(error)) from error

    return " ".join(body.split())


def _transcription_prompt(language_hint: str | None) -> str:
    language_name = _language_name(language_hint)
    if language_name:
        return (
            "Transcribe the user's voice message as spoken text. "
            "The message is likely in "
            f"{language_name}. "
            "The user is probably describing a product to search on Uzum Market. "
            "Return only the transcription text."
        )
    return (
        "Transcribe the user's voice message as spoken text. "
        "The user is probably describing a product to search on Uzum Market. "
        "Return only the transcription text."
    )


def _language_name(language_hint: str | None) -> str:
    normalized = (language_hint or "").strip().lower()
    if normalized.startswith("uz"):
        return "Uzbek"
    if normalized.startswith("ru"):
        return "Russian"
    if normalized.startswith("en"):
        return "English"
    return ""
