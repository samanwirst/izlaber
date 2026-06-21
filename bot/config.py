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
    bot_api_key: str = ""
    product_search_limit: int = 5
    server_api_timeout: float = 10.0


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
        bot_api_key=getenv("BOT_API_KEY", ""),
        product_search_limit=int(getenv("BOT_PRODUCT_SEARCH_LIMIT", "5")),
        server_api_timeout=float(getenv("BOT_SERVER_API_TIMEOUT", "10")),
    )
