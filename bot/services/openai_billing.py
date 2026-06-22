import calendar
import time
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession, ClientTimeout

from bot.config import Config

COSTS_API_URL = "https://api.openai.com/v1/organization/costs"
SECONDS_PER_DAY = 24 * 60 * 60


class OpenAIBillingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenAICostSummary:
    today_usd: float | None
    month_usd: float | None
    monthly_budget_usd: float | None

    @property
    def remaining_monthly_budget_usd(self) -> float | None:
        if self.monthly_budget_usd is None or self.month_usd is None:
            return None
        return max(0.0, self.monthly_budget_usd - self.month_usd)


async def fetch_openai_cost_summary(config: Config) -> OpenAICostSummary:
    if not config.openai_admin_api_key:
        raise OpenAIBillingError("OPENAI_ADMIN_API_KEY is not configured.")

    now = int(time.time())
    day_start = now - (now % SECONDS_PER_DAY)
    month_start = _month_start_timestamp(now)

    costs_by_day = await _fetch_costs(
        config=config,
        start_time=month_start,
        end_time=now,
    )
    today_usd = costs_by_day.get(day_start, 0.0)
    month_usd = sum(costs_by_day.values())
    return OpenAICostSummary(
        today_usd=today_usd,
        month_usd=month_usd,
        monthly_budget_usd=config.openai_monthly_budget_usd,
    )


async def _fetch_costs(
    *,
    config: Config,
    start_time: int,
    end_time: int,
) -> dict[int, float]:
    params = {
        "start_time": str(start_time),
        "end_time": str(end_time),
        "bucket_width": "1d",
        "limit": "31",
    }
    headers = {
        "Authorization": f"Bearer {config.openai_admin_api_key}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=config.openai_timeout)
    costs_by_day: dict[int, float] = {}
    try:
        async with ClientSession(timeout=timeout, headers=headers) as session:
            next_page: str | None = None
            while True:
                request_params = dict(params)
                if next_page:
                    request_params["page"] = next_page
                async with session.get(COSTS_API_URL, params=request_params) as response:
                    body = await response.text()
                    if response.status >= 400:
                        raise OpenAIBillingError(f"HTTP {response.status}: {body[:300]}")
                    data = await response.json(content_type=None)
                _merge_cost_buckets(costs_by_day, data)
                next_page = data.get("next_page")
                if not next_page:
                    break
    except (ClientError, TimeoutError) as error:
        raise OpenAIBillingError(str(error)) from error

    return costs_by_day


def _merge_cost_buckets(costs_by_day: dict[int, float], data: dict) -> None:
    for bucket in data.get("data") or []:
        start_time = bucket.get("start_time")
        if not isinstance(start_time, int):
            continue
        total = 0.0
        for result in bucket.get("results") or []:
            amount = result.get("amount") or {}
            currency = str(amount.get("currency") or "").lower()
            if currency and currency != "usd":
                continue
            value = amount.get("value")
            if isinstance(value, (int, float)):
                total += float(value)
        costs_by_day[start_time] = costs_by_day.get(start_time, 0.0) + total


def _month_start_timestamp(now: int) -> int:
    struct = time.gmtime(now)
    return calendar.timegm((struct.tm_year, struct.tm_mon, 1, 0, 0, 0, 0, 0, 0))
