import asyncio
import json
import logging
import random
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen

from parsers.wildberries.config import ParserConfig

logger = logging.getLogger(__name__)


class WildberriesForbiddenError(RuntimeError):
    pass


class WildberriesTransientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CategoryTask:
    source_category_id: str
    name: str
    path: str
    url: str
    shard: str
    query: str
    params: dict[str, str]


@dataclass(frozen=True, slots=True)
class CatalogSegment:
    category: CategoryTask
    total: int
    price_min_u: int | None = None
    price_max_u: int | None = None
    capped: bool = False

    @property
    def key(self) -> str:
        price = (
            ""
            if self.price_min_u is None or self.price_max_u is None
            else f"{self.price_min_u}-{self.price_max_u}"
        )
        return f"{self.category.source_category_id}:{self.category.query}:{price}"


class WildberriesClient:
    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self._last_request_at = 0.0
        self._throttle_lock = asyncio.Lock()
        self._headers = {
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Origin": "https://www.wildberries.uz",
            "Referer": "https://www.wildberries.uz/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
            ),
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def fetch_categories(self) -> list[CategoryTask]:
        menu = await self._get_json(self.config.menu_url)
        if not isinstance(menu, list):
            raise RuntimeError("Wildberries menu response must be a list.")
        categories: list[CategoryTask] = []
        self._walk_menu(menu, (), categories)
        if self.config.category_limit is not None:
            return categories[: self.config.category_limit]
        return categories

    async def fetch_catalog_page(
        self,
        category: CategoryTask,
        *,
        page: int,
        price_min_u: int | None = None,
        price_max_u: int | None = None,
    ) -> dict[str, Any]:
        params = self._catalog_params(
            category,
            page=page,
            price_min_u=price_min_u,
            price_max_u=price_max_u,
        )
        url = f"{self.config.catalog_api_base_url}/catalog/{category.shard}/v4/catalog"
        data = await self._get_json(url, params=params)
        return data if isinstance(data, dict) else {}

    async def fetch_search_page(self, query: str, *, page: int) -> dict[str, Any]:
        params = {
            "appType": "1",
            "curr": self.config.currency_param,
            "dest": self.config.destination_ids,
            "locale": self.config.locale,
            "lang": self.config.language,
            "page": str(page),
            "query": query,
            "resultset": "catalog",
            "sort": self.config.sort,
            "spp": str(self.config.spp),
            "limit": str(self.config.page_size),
        }
        data = await self._get_json(self.config.search_url, params=params)
        return data if isinstance(data, dict) else {}

    async def build_segments(
        self,
        category: CategoryTask,
        *,
        allow_price_split: bool = True,
    ) -> list[CatalogSegment]:
        first_page = await self.fetch_catalog_page(category, page=1)
        total = int(first_page.get("total") or 0)
        if (
            not allow_price_split
            or not self.config.price_split_enabled
            or total <= self.config.price_split_total_threshold
        ):
            return [
                CatalogSegment(
                    category=category,
                    total=total,
                    capped=total > self._segment_product_cap,
                )
            ]
        return await self._split_by_price(
            category=category,
            price_min_u=0,
            price_max_u=self.config.price_split_max_u,
            depth=0,
        )

    @property
    def _segment_product_cap(self) -> int:
        return self.config.page_size * self.config.max_pages_per_segment

    async def _split_by_price(
        self,
        *,
        category: CategoryTask,
        price_min_u: int,
        price_max_u: int,
        depth: int,
    ) -> list[CatalogSegment]:
        first_page = await self.fetch_catalog_page(
            category,
            page=1,
            price_min_u=price_min_u,
            price_max_u=price_max_u,
        )
        total = int(first_page.get("total") or 0)
        range_size = price_max_u - price_min_u
        if (
            total <= self.config.price_split_total_threshold
            or depth >= self.config.price_split_max_depth
            or range_size <= self.config.price_split_min_step_u
        ):
            return [
                CatalogSegment(
                    category=category,
                    total=total,
                    price_min_u=price_min_u,
                    price_max_u=price_max_u,
                    capped=total > self._segment_product_cap,
                )
            ]

        midpoint = price_min_u + range_size // 2
        left = await self._split_by_price(
            category=category,
            price_min_u=price_min_u,
            price_max_u=midpoint,
            depth=depth + 1,
        )
        right = await self._split_by_price(
            category=category,
            price_min_u=midpoint + 1,
            price_max_u=price_max_u,
            depth=depth + 1,
        )
        return [*left, *right]

    def _catalog_params(
        self,
        category: CategoryTask,
        *,
        page: int,
        price_min_u: int | None,
        price_max_u: int | None,
    ) -> dict[str, str]:
        params = {
            "appType": "1",
            "curr": self.config.currency_param,
            "dest": self.config.destination_ids,
            "locale": self.config.locale,
            "lang": self.config.language,
            "page": str(page),
            "sort": self.config.sort,
            "spp": str(self.config.spp),
            "limit": str(self.config.page_size),
        }
        params.update(category.params)
        if price_min_u is not None and price_max_u is not None:
            params["priceU"] = f"{price_min_u};{price_max_u}"
        return params

    def _walk_menu(
        self,
        nodes: list[dict[str, Any]],
        path: tuple[str, ...],
        categories: list[CategoryTask],
    ) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "").strip()
            current_path = (*path, name) if name else path
            shard = str(node.get("shard") or "").strip()
            query = str(node.get("query") or "").strip()
            if shard and query and shard not in {"c2c", "blackhole"}:
                params = _parse_query_params(query)
                if params:
                    categories.append(
                        CategoryTask(
                            source_category_id=str(node.get("id") or query),
                            name=name or str(node.get("id") or query),
                            path=" > ".join(item for item in current_path if item),
                            url=_absolute_wb_url(str(node.get("url") or "")),
                            shard=shard,
                            query=query,
                            params=params,
                        )
                    )
            children = node.get("childs")
            if isinstance(children, list):
                self._walk_menu(children, current_path, categories)

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            await self._throttle()
            try:
                return await asyncio.to_thread(self._get_json_sync, url, params)
            except WildberriesForbiddenError:
                raise
            except (
                WildberriesTransientError,
                URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as error:
                last_error = error
                if attempt >= self.config.max_retries:
                    break
                delay = self.config.retry_base_delay_seconds * (2**attempt)
                delay += random.uniform(0, self.config.retry_base_delay_seconds)
                logger.warning(
                    "Wildberries request failed, retrying in %.1fs: %s %s",
                    delay,
                    url,
                    error,
                )
                await asyncio.sleep(delay)
        raise RuntimeError(f"Wildberries request failed for {url}: {last_error}") from last_error

    def _get_json_sync(
        self,
        url: str,
        params: dict[str, str] | None,
    ) -> dict[str, Any] | list[Any]:
        full_url = url
        if params:
            full_url = f"{url}?{urlencode(params)}"
        request = Request(full_url, headers=self._headers)
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 403:
                raise WildberriesForbiddenError(f"WB HTTP 403 for {url}: {body[:300]}") from error
            if error.code in {429, 500, 502, 503, 504}:
                raise WildberriesTransientError(
                    f"WB HTTP {error.code} for {url}: {body[:300]}"
                ) from error
            raise RuntimeError(f"WB HTTP {error.code} for {url}: {body[:300]}") from error

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            now = asyncio.get_running_loop().time()
            wait = self.config.crawl_delay_seconds - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = asyncio.get_running_loop().time()


def _parse_query_params(query: str) -> dict[str, str]:
    return {
        key: value
        for key, value in parse_qsl(query, keep_blank_values=False)
        if key and value
    }


def _absolute_wb_url(path: str) -> str:
    if not path:
        return "https://www.wildberries.uz/"
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"https://www.wildberries.uz{path if path.startswith('/') else '/' + path}"
