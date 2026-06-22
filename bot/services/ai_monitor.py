import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import Config
from bot.services.ai_reranker import probe_openai_availability
from bot.services.ai_runtime import AIStatusEvent, ai_runtime_state

logger = logging.getLogger(__name__)


async def monitor_openai_balance(bot: Bot, config: Config) -> None:
    if not _monitor_enabled(config):
        return

    if config.openai_startup_probe_enabled:
        await _probe_and_update_state(config)

    while True:
        await _send_pending_events(bot, config)
        if ai_runtime_state.quota_disabled:
            await asyncio.sleep(config.openai_balance_probe_interval)
            await _probe_and_update_state(config)
            await _send_pending_events(bot, config)
            continue

        await asyncio.sleep(5)


def _monitor_enabled(config: Config) -> bool:
    return bool(
        config.openai_rerank_enabled
        and config.openai_api_key
        and config.openai_status_notify_user_id
    )


async def _probe_and_update_state(config: Config) -> None:
    result = await probe_openai_availability(config)
    if result.ok:
        ai_runtime_state.mark_available()
        return
    if result.quota_exhausted:
        ai_runtime_state.mark_quota_exhausted(result.reason)
        return
    logger.warning("OpenAI balance probe failed without disabling AI: %s", result.reason)


async def _send_pending_events(bot: Bot, config: Config) -> None:
    for event in ai_runtime_state.consume_events():
        await _send_status_event(bot, config, event)


async def _send_status_event(bot: Bot, config: Config, event: AIStatusEvent) -> None:
    user_id = config.openai_status_notify_user_id
    if user_id is None:
        return

    if event.kind == "disabled":
        text = (
            "OpenAI API quota/balance exhausted. "
            "AI mode is disabled; bot now uses local catalog search only. "
            f"I will retry every {int(config.openai_balance_probe_interval)} seconds and "
            "enable AI automatically after balance is replenished."
        )
    elif event.kind == "enabled":
        text = "OpenAI API is available again. AI mode is enabled automatically."
    else:
        return

    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramAPIError as error:
        logger.warning("Failed to send OpenAI status notification to %s: %s", user_id, error)
