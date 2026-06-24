from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class ParserConfig:
    server_api_base_url: str
    parser_api_key: str
    request_timeout: float = 20.0
    crawl_delay_seconds: float = 1.0
    retry_base_delay_seconds: float = 2.0
    max_retries: int = 5
    batch_size: int = 100
    delta_compare_batch_size: int = 1000
    state_dir: Path = Path(".parser_state/wildberries")
    menu_url: str = "https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json"
    catalog_api_base_url: str = "https://catalog.wb.ru"
    search_url: str = "https://search.wb.ru/exactmatch/ru/common/v18/search"
    marketplace_code: str = "wildberries"
    destination_ids: str = "123585551"
    currency_param: str = "uzs"
    currency_code: str = "UZS"
    locale: str = "ru"
    language: str = "ru"
    sort: str = "popular"
    spp: int = 30
    page_size: int = 100
    max_pages_per_segment: int = 100
    category_limit: int | None = None
    price_split_enabled: bool = True
    price_split_total_threshold: int = 9_000
    price_split_max_depth: int = 16
    price_split_min_step_u: int = 1_000_000
    price_split_max_u: int = 10_000_000_000


def load_config() -> ParserConfig:
    load_dotenv()
    return ParserConfig(
        server_api_base_url=getenv("SERVER_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
        parser_api_key=getenv("PARSER_API_KEY", ""),
        request_timeout=float(getenv("WB_REQUEST_TIMEOUT", "20")),
        crawl_delay_seconds=float(getenv("WB_CRAWL_DELAY_SECONDS", "1.0")),
        retry_base_delay_seconds=float(getenv("WB_RETRY_BASE_DELAY_SECONDS", "2")),
        max_retries=int(getenv("WB_MAX_RETRIES", "5")),
        batch_size=int(getenv("WB_BATCH_SIZE", "100")),
        delta_compare_batch_size=int(getenv("WB_DELTA_COMPARE_BATCH_SIZE", "1000")),
        state_dir=Path(getenv("WB_STATE_DIR", ".parser_state/wildberries")).expanduser(),
        menu_url=getenv(
            "WB_MENU_URL",
            "https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json",
        ),
        catalog_api_base_url=getenv("WB_CATALOG_API_BASE_URL", "https://catalog.wb.ru").rstrip("/"),
        search_url=getenv(
            "WB_SEARCH_URL",
            "https://search.wb.ru/exactmatch/ru/common/v18/search",
        ),
        marketplace_code=getenv("WB_MARKETPLACE_CODE", "wildberries"),
        destination_ids=getenv("WB_DESTINATION_IDS", "123585551"),
        currency_param=getenv("WB_CURRENCY_PARAM", "uzs"),
        currency_code=getenv("WB_CURRENCY_CODE", "UZS"),
        locale=getenv("WB_LOCALE", "ru"),
        language=getenv("WB_LANGUAGE", "ru"),
        sort=getenv("WB_SORT", "popular"),
        spp=int(getenv("WB_SPP", "30")),
        page_size=int(getenv("WB_PAGE_SIZE", "100")),
        max_pages_per_segment=int(getenv("WB_MAX_PAGES_PER_SEGMENT", "100")),
        category_limit=_optional_int(getenv("WB_CATEGORY_LIMIT")),
        price_split_enabled=getenv("WB_PRICE_SPLIT_ENABLED", "true").lower()
        in {"1", "true", "yes"},
        price_split_total_threshold=int(getenv("WB_PRICE_SPLIT_TOTAL_THRESHOLD", "9000")),
        price_split_max_depth=int(getenv("WB_PRICE_SPLIT_MAX_DEPTH", "16")),
        price_split_min_step_u=int(getenv("WB_PRICE_SPLIT_MIN_STEP_U", "1000000")),
        price_split_max_u=int(getenv("WB_PRICE_SPLIT_MAX_U", "10000000000")),
    )


def _optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
