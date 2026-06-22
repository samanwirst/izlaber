from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class ParserConfig:
    server_api_base_url: str
    parser_api_key: str
    crawl_delay_seconds: float = 1.5
    max_retries: int = 3
    batch_size: int = 50
    delta_compare_batch_size: int = 1000
    request_timeout: float = 20.0
    state_dir: Path = Path(".parser_state/uzum_market")
    browser_executable_path: str = "/usr/bin/google-chrome-stable"
    browser_profile_source: Path = Path.home() / ".config/google-chrome"
    browser_profile_name: str = "Default"
    browser_runtime_profile_dir: Path = Path(".parser_state/uzum_market/browser-profile")
    browser_headless: bool = True
    browser_slow_mo_ms: int = 0
    browser_navigation_timeout_ms: int = 45_000
    browser_scroll_pause_ms: int = 1_000
    browser_scroll_max_rounds: int = 60
    browser_interactive_captcha_timeout_seconds: int = 300
    discovery_start_urls: tuple[str, ...] = ("https://uzum.uz/ru/category/vse-kategorii-1",)


def load_config() -> ParserConfig:
    load_dotenv()
    raw_start_urls = getenv("UZUM_DISCOVERY_START_URLS", "https://uzum.uz/ru/category/vse-kategorii-1")
    return ParserConfig(
        server_api_base_url=getenv("SERVER_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
        parser_api_key=getenv("PARSER_API_KEY", ""),
        crawl_delay_seconds=float(getenv("UZUM_CRAWL_DELAY_SECONDS", "1.5")),
        max_retries=int(getenv("UZUM_MAX_RETRIES", "3")),
        batch_size=int(getenv("UZUM_BATCH_SIZE", "50")),
        delta_compare_batch_size=int(getenv("UZUM_DELTA_COMPARE_BATCH_SIZE", "1000")),
        request_timeout=float(getenv("UZUM_REQUEST_TIMEOUT", "20")),
        state_dir=Path(getenv("UZUM_STATE_DIR", ".parser_state/uzum_market")),
        browser_executable_path=getenv(
            "UZUM_BROWSER_EXECUTABLE_PATH",
            "/usr/bin/google-chrome-stable",
        ),
        browser_profile_source=Path(
            getenv("UZUM_BROWSER_PROFILE_SOURCE", str(Path.home() / ".config/google-chrome"))
        ).expanduser(),
        browser_profile_name=getenv("UZUM_BROWSER_PROFILE_NAME", "Default"),
        browser_runtime_profile_dir=Path(
            getenv(
                "UZUM_BROWSER_RUNTIME_PROFILE_DIR",
                ".parser_state/uzum_market/browser-profile",
            )
        ).expanduser(),
        browser_headless=getenv("UZUM_BROWSER_HEADLESS", "true").lower() in {"1", "true", "yes"},
        browser_slow_mo_ms=int(getenv("UZUM_BROWSER_SLOW_MO_MS", "0")),
        browser_navigation_timeout_ms=int(getenv("UZUM_BROWSER_NAVIGATION_TIMEOUT_MS", "45000")),
        browser_scroll_pause_ms=int(getenv("UZUM_BROWSER_SCROLL_PAUSE_MS", "1000")),
        browser_scroll_max_rounds=int(getenv("UZUM_BROWSER_SCROLL_MAX_ROUNDS", "60")),
        browser_interactive_captcha_timeout_seconds=int(
            getenv("UZUM_BROWSER_CAPTCHA_TIMEOUT_SECONDS", "300")
        ),
        discovery_start_urls=tuple(
            url.strip() for url in raw_start_urls.split(",") if url.strip()
        ),
    )
