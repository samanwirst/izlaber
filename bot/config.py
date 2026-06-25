from dataclasses import dataclass, field
from os import getenv

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class BotConfig:
    token: str
    parse_mode: str | None = "HTML"


@dataclass(frozen=True, slots=True)
class Config:
    bot: BotConfig
    log_level: str = "INFO"
    server_api_base_url: str = "http://127.0.0.1:8000/api"
    public_base_url: str = ""
    bot_api_key: str = ""
    product_search_limit: int = 10
    sponsored_search_limit: int = 1
    server_api_timeout: float = 10.0
    consent_enabled: bool = True
    consent_version: str = "2026-06-consent-v3"
    privacy_policy_url: str = ""
    sponsored_ads_policy_url: str = ""
    analytics_enabled: bool = True
    analytics_timeout: float = 2.0
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"
    openai_rerank_enabled: bool = True
    openai_candidate_limit: int = 30
    openai_timeout: float = 8.0
    openai_max_output_tokens: int = 900
    openai_search_expand_enabled: bool = True
    openai_search_expand_max_queries: int = 3
    openai_search_expand_query_limit: int = 15
    openai_rerank_max_products: int = 80
    openai_rerank_fallback_only: bool = True
    openai_photo_search_enabled: bool = True
    openai_photo_model: str = "gpt-5.4-nano"
    openai_photo_timeout: float = 12.0
    openai_photo_max_output_tokens: int = 500
    openai_photo_detail: str = "high"
    openai_photo_max_pixels: int = 1_048_576
    openai_photo_max_download_bytes: int = 2_000_000
    openai_photo_candidate_limit: int = 60
    openai_photo_visual_rerank_enabled: bool = True
    openai_photo_visual_rerank_limit: int = 16
    openai_photo_visual_rerank_min_score: int = 55
    photo_visual_match_enabled: bool = True
    photo_visual_match_max_distance: int = 10
    openai_photo_text_fallback_enabled: bool = False
    openai_voice_search_enabled: bool = True
    openai_voice_model: str = "gpt-4o-mini-transcribe"
    openai_voice_timeout: float = 20.0
    openai_voice_max_download_bytes: int = 8_000_000
    openai_voice_max_duration_seconds: int = 180
    openai_status_notify_user_id: int | None = 976835256
    openai_admin_api_key: str = ""
    openai_monthly_budget_usd: float | None = None
    openai_balance_probe_interval: float = 60.0
    openai_startup_probe_enabled: bool = True
    guest_search_enabled: bool = True
    rate_limit_enabled: bool = True
    rate_limit_admin_bypass: bool = True
    rate_limit_max_events: int = 30
    rate_limit_window_seconds: float = 60.0
    search_inflight_limit_enabled: bool = True
    search_rate_limit_max_events: int = 12
    search_rate_limit_window_seconds: float = 60.0
    ai_rate_limit_max_events: int = 12
    ai_rate_limit_window_seconds: float = 3600.0
    search_backfill_enabled: bool = True
    search_backfill_wait_seconds: float = 18.0
    search_backfill_poll_seconds: float = 2.0
    search_backfill_limit: int = 30
    search_backfill_max_queries: int = 3
    search_timeout_seconds: float = 60.0
    search_ai_rescue_after_seconds: float = 30.0
    marketplace_custom_emoji_ids: dict[str, str] = field(default_factory=dict)


def load_config() -> Config:
    load_dotenv()

    token = getenv("TELEGRAM_BOT_TOKEN") or getenv("BOT_TOKEN")
    if not token:
        msg = "TELEGRAM_BOT_TOKEN is not set. Add it to .env or export it in the environment."
        raise RuntimeError(msg)

    parse_mode = getenv("BOT_PARSE_MODE", "HTML").strip() or None
    log_level = getenv("LOG_LEVEL", "INFO").upper()
    public_base_url = getenv("BOT_PUBLIC_BASE_URL", "").rstrip("/")
    privacy_policy_url = _policy_url(
        getenv("BOT_PRIVACY_POLICY_URL"),
        public_base_url,
        "/legal/privacy/",
    )
    sponsored_ads_policy_url = _policy_url(
        getenv("BOT_SPONSORED_ADS_POLICY_URL"),
        public_base_url,
        "/legal/sponsored-ads/",
    )

    return Config(
        bot=BotConfig(token=token, parse_mode=parse_mode),
        log_level=log_level,
        server_api_base_url=getenv("SERVER_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
        public_base_url=public_base_url,
        bot_api_key=getenv("BOT_API_KEY", ""),
        product_search_limit=int(getenv("BOT_PRODUCT_SEARCH_LIMIT", "10")),
        sponsored_search_limit=max(0, int(getenv("BOT_SPONSORED_SEARCH_LIMIT", "1"))),
        server_api_timeout=float(getenv("BOT_SERVER_API_TIMEOUT", "10")),
        consent_enabled=getenv("BOT_CONSENT_ENABLED", "true").lower() in {"1", "true", "yes"},
        consent_version=getenv("BOT_CONSENT_VERSION", "2026-06-consent-v3").strip()
        or "2026-06-consent-v3",
        privacy_policy_url=privacy_policy_url,
        sponsored_ads_policy_url=sponsored_ads_policy_url,
        analytics_enabled=getenv("BOT_ANALYTICS_ENABLED", "true").lower() in {"1", "true", "yes"},
        analytics_timeout=float(getenv("BOT_ANALYTICS_TIMEOUT", "2")),
        openai_api_key=getenv("OPENAI_API_KEY", ""),
        openai_model=getenv("OPENAI_RERANK_MODEL", "gpt-5.4-nano"),
        openai_rerank_enabled=getenv("OPENAI_RERANK_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        openai_candidate_limit=int(getenv("OPENAI_RERANK_CANDIDATE_LIMIT", "30")),
        openai_timeout=float(getenv("OPENAI_RERANK_TIMEOUT", "8")),
        openai_max_output_tokens=int(getenv("OPENAI_RERANK_MAX_OUTPUT_TOKENS", "900")),
        openai_search_expand_enabled=getenv("OPENAI_SEARCH_EXPAND_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        openai_search_expand_max_queries=int(getenv("OPENAI_SEARCH_EXPAND_MAX_QUERIES", "3")),
        openai_search_expand_query_limit=int(getenv("OPENAI_SEARCH_EXPAND_QUERY_LIMIT", "15")),
        openai_rerank_max_products=int(getenv("OPENAI_RERANK_MAX_PRODUCTS", "80")),
        openai_rerank_fallback_only=getenv("OPENAI_RERANK_FALLBACK_ONLY", "true").lower()
        in {"1", "true", "yes"},
        openai_photo_search_enabled=getenv("OPENAI_PHOTO_SEARCH_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        openai_photo_model=getenv(
            "OPENAI_PHOTO_MODEL",
            getenv("OPENAI_RERANK_MODEL", "gpt-5.4-nano"),
        ),
        openai_photo_timeout=float(getenv("OPENAI_PHOTO_TIMEOUT", "12")),
        openai_photo_max_output_tokens=int(getenv("OPENAI_PHOTO_MAX_OUTPUT_TOKENS", "500")),
        openai_photo_detail=_photo_detail(getenv("OPENAI_PHOTO_DETAIL", "high")),
        openai_photo_max_pixels=int(getenv("OPENAI_PHOTO_MAX_PIXELS", "1048576")),
        openai_photo_max_download_bytes=int(getenv("OPENAI_PHOTO_MAX_DOWNLOAD_BYTES", "2000000")),
        openai_photo_candidate_limit=int(getenv("OPENAI_PHOTO_CANDIDATE_LIMIT", "60")),
        openai_photo_visual_rerank_enabled=getenv(
            "OPENAI_PHOTO_VISUAL_RERANK_ENABLED",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        openai_photo_visual_rerank_limit=int(getenv("OPENAI_PHOTO_VISUAL_RERANK_LIMIT", "16")),
        openai_photo_visual_rerank_min_score=int(
            getenv("OPENAI_PHOTO_VISUAL_RERANK_MIN_SCORE", "55")
        ),
        photo_visual_match_enabled=getenv("PHOTO_VISUAL_MATCH_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        photo_visual_match_max_distance=int(getenv("PHOTO_VISUAL_MATCH_MAX_DISTANCE", "10")),
        openai_photo_text_fallback_enabled=getenv(
            "OPENAI_PHOTO_TEXT_FALLBACK_ENABLED",
            "false",
        ).lower()
        in {"1", "true", "yes"},
        openai_voice_search_enabled=getenv("OPENAI_VOICE_SEARCH_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        openai_voice_model=getenv("OPENAI_VOICE_MODEL", "gpt-4o-mini-transcribe"),
        openai_voice_timeout=float(getenv("OPENAI_VOICE_TIMEOUT", "20")),
        openai_voice_max_download_bytes=int(getenv("OPENAI_VOICE_MAX_DOWNLOAD_BYTES", "8000000")),
        openai_voice_max_duration_seconds=int(getenv("OPENAI_VOICE_MAX_DURATION_SECONDS", "180")),
        openai_status_notify_user_id=_optional_int(
            getenv("OPENAI_STATUS_NOTIFY_USER_ID"),
            default=976835256,
        ),
        openai_admin_api_key=getenv("OPENAI_ADMIN_API_KEY", ""),
        openai_monthly_budget_usd=_optional_float(
            getenv("OPENAI_MONTHLY_BUDGET_USD"),
            default=None,
        ),
        openai_balance_probe_interval=float(getenv("OPENAI_BALANCE_PROBE_INTERVAL", "60")),
        openai_startup_probe_enabled=getenv("OPENAI_STARTUP_PROBE_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        guest_search_enabled=getenv("BOT_GUEST_SEARCH_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        rate_limit_enabled=getenv("BOT_RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes"},
        rate_limit_admin_bypass=getenv("BOT_RATE_LIMIT_ADMIN_BYPASS", "true").lower()
        in {"1", "true", "yes"},
        rate_limit_max_events=max(1, int(getenv("BOT_RATE_LIMIT_MAX_EVENTS", "30"))),
        rate_limit_window_seconds=max(
            1.0,
            float(getenv("BOT_RATE_LIMIT_WINDOW_SECONDS", "60")),
        ),
        search_inflight_limit_enabled=getenv(
            "BOT_SEARCH_INFLIGHT_LIMIT_ENABLED",
            "true",
        ).lower()
        in {"1", "true", "yes"},
        search_rate_limit_max_events=max(
            1,
            int(getenv("BOT_SEARCH_RATE_LIMIT_MAX_EVENTS", "12")),
        ),
        search_rate_limit_window_seconds=max(
            1.0,
            float(getenv("BOT_SEARCH_RATE_LIMIT_WINDOW_SECONDS", "60")),
        ),
        ai_rate_limit_max_events=max(1, int(getenv("BOT_AI_RATE_LIMIT_MAX_EVENTS", "12"))),
        ai_rate_limit_window_seconds=max(
            1.0,
            float(getenv("BOT_AI_RATE_LIMIT_WINDOW_SECONDS", "3600")),
        ),
        search_backfill_enabled=getenv("BOT_SEARCH_BACKFILL_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        search_backfill_wait_seconds=max(
            0.0,
            float(getenv("BOT_SEARCH_BACKFILL_WAIT_SECONDS", "18")),
        ),
        search_backfill_poll_seconds=max(
            0.5,
            float(getenv("BOT_SEARCH_BACKFILL_POLL_SECONDS", "2")),
        ),
        search_backfill_limit=max(1, int(getenv("BOT_SEARCH_BACKFILL_LIMIT", "30"))),
        search_backfill_max_queries=max(1, int(getenv("BOT_SEARCH_BACKFILL_MAX_QUERIES", "3"))),
        search_timeout_seconds=max(60.0, float(getenv("BOT_SEARCH_TIMEOUT_SECONDS", "60"))),
        search_ai_rescue_after_seconds=max(
            0.0,
            float(getenv("BOT_SEARCH_AI_RESCUE_AFTER_SECONDS", "30")),
        ),
        marketplace_custom_emoji_ids=_marketplace_custom_emoji_ids(),
    )


def _optional_int(value: str | None, *, default: int | None) -> int | None:
    if value is None:
        return default
    value = value.strip()
    if not value:
        return None
    return int(value)


def _optional_float(value: str | None, *, default: float | None) -> float | None:
    if value is None:
        return default
    value = value.strip()
    if not value:
        return None
    return float(value)


def _policy_url(value: str | None, public_base_url: str, path: str) -> str:
    explicit = (value or "").strip()
    if explicit:
        return explicit
    if not public_base_url:
        return ""
    return f"{public_base_url}{path}"


def _photo_detail(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"low", "high", "auto"}:
        return normalized
    return "low"


def _marketplace_custom_emoji_ids() -> dict[str, str]:
    ids = {
        "uzum": getenv("BOT_MARKETPLACE_CUSTOM_EMOJI_UZUM", "").strip(),
        "wildberries": getenv("BOT_MARKETPLACE_CUSTOM_EMOJI_WILDBERRIES", "").strip(),
    }
    return {code: emoji_id for code, emoji_id in ids.items() if emoji_id}
