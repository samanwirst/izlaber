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
    uzum_graphql_url: str = "https://graphql.umarket.uz/"


def load_config() -> Config:
    load_dotenv()

    token = getenv("BOT_TOKEN")
    if not token:
        msg = "BOT_TOKEN is not set. Add it to .env or export it in the environment."
        raise RuntimeError(msg)

    parse_mode = getenv("BOT_PARSE_MODE", "HTML").strip() or None
    log_level = getenv("LOG_LEVEL", "INFO").upper()

    return Config(
        bot=BotConfig(token=token, parse_mode=parse_mode),
        log_level=log_level,
        uzum_graphql_url=getenv("UZUM_GRAPHQL_URL", "https://graphql.umarket.uz/"),
    )
