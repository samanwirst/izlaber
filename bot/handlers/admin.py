from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.services.ai_reranker import probe_openai_availability
from bot.services.ai_runtime import ai_runtime_state
from bot.services.openai_billing import OpenAIBillingError, fetch_openai_cost_summary

router = Router(name="admin")


@router.message(Command("balance"))
async def command_balance(message: Message, config: Config) -> None:
    if not _is_openai_status_admin(message, config):
        return

    probe = await probe_openai_availability(config)
    if probe.ok:
        ai_runtime_state.mark_available()
    elif probe.quota_exhausted:
        ai_runtime_state.mark_quota_exhausted(probe.reason)

    lines = [
        "<b>OpenAI status</b>",
        f"AI mode: <b>{'enabled' if ai_runtime_state.ai_allowed() else 'local-only'}</b>",
        f"API probe: {_format_probe_status(probe.ok, probe.quota_exhausted)}",
        f"Model: <code>{escape(config.openai_model)}</code>",
    ]

    try:
        summary = await fetch_openai_cost_summary(config)
    except OpenAIBillingError as error:
        lines.extend(
            [
                "",
                "<b>Costs</b>",
                "Costs API: unavailable",
                f"Reason: <code>{escape(str(error))}</code>",
                "Exact prepaid balance is not exposed by the regular project API key. "
                "Set <code>OPENAI_ADMIN_API_KEY</code> to show official costs, and "
                "<code>OPENAI_MONTHLY_BUDGET_USD</code> to show remaining budget.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "<b>Costs</b>",
                f"Today: <b>{_format_usd(summary.today_usd)}</b>",
                f"This month: <b>{_format_usd(summary.month_usd)}</b>",
                f"Configured budget: <b>{_format_usd(summary.monthly_budget_usd)}</b>",
                f"Remaining configured budget: "
                f"<b>{_format_usd(summary.remaining_monthly_budget_usd)}</b>",
            ]
        )

    if not probe.ok and probe.reason:
        lines.extend(["", f"Probe reason: <code>{escape(probe.reason[:500])}</code>"])

    await message.answer("\n".join(lines))


def _is_openai_status_admin(message: Message, config: Config) -> bool:
    return bool(
        config.openai_status_notify_user_id is not None
        and message.from_user
        and message.from_user.id == config.openai_status_notify_user_id
    )


def _format_probe_status(ok: bool, quota_exhausted: bool) -> str:
    if ok:
        return "<b>available</b>"
    if quota_exhausted:
        return "<b>quota/balance exhausted</b>"
    return "<b>unavailable or probe failed</b>"


def _format_usd(value: float | None) -> str:
    if value is None:
        return "not configured"
    return f"${value:.4f}"
