from dataclasses import dataclass
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
    product_search_limit: int = 5
    server_api_timeout: float = 10.0
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


def load_config() -> Config:
    load_dotenv()

    token = getenv("TELEGRAM_BOT_TOKEN") or getenv("BOT_TOKEN")
    if not token:
        msg = "TELEGRAM_BOT_TOKEN is not set. Add it to .env or export it in the environment."
        raise RuntimeError(msg)

    parse_mode = getenv("BOT_PARSE_MODE", "HTML").strip() or None
    log_level = getenv("LOG_LEVEL", "INFO").upper()

    return Config(
        bot=BotConfig(token=token, parse_mode=parse_mode),
        log_level=log_level,
        server_api_base_url=getenv("SERVER_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
        public_base_url=getenv("BOT_PUBLIC_BASE_URL", "").rstrip("/"),
        bot_api_key=getenv("BOT_API_KEY", ""),
        product_search_limit=int(getenv("BOT_PRODUCT_SEARCH_LIMIT", "5")),
        server_api_timeout=float(getenv("BOT_SERVER_API_TIMEOUT", "10")),
        analytics_enabled=getenv("BOT_ANALYTICS_ENABLED", "true").lower()
        in {"1", "true", "yes"},
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
        openai_photo_visual_rerank_limit=int(
            getenv("OPENAI_PHOTO_VISUAL_RERANK_LIMIT", "16")
        ),
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
        openai_voice_max_download_bytes=int(
            getenv("OPENAI_VOICE_MAX_DOWNLOAD_BYTES", "8000000")
        ),
        openai_voice_max_duration_seconds=int(
            getenv("OPENAI_VOICE_MAX_DURATION_SECONDS", "180")
        ),
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


def _photo_detail(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"low", "high", "auto"}:
        return normalized
    return "low"
