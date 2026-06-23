import asyncio
import contextlib
import json
import logging
import re
import shutil
import socket
import subprocess
import unicodedata
from math import ceil
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import aiohttp

from parsers.uzum_market.config import ParserConfig
from parsers.uzum_market.normalizer import extract_product_id, normalize_product

logger = logging.getLogger(__name__)

BASE_URL = "https://uzum.uz"
HOMEPAGE_URL = "https://uzum.uz/ru"
ROOT_CATEGORIES_URL = "https://api.uzum.uz/api/main/root-categories"
GRAPHQL_URL = "https://graphql.uzum.uz/"
GRAPHQL_PAGE_SIZE = 100
GRAPHQL_MAX_PAGE = 99
GRAPHQL_MAX_OFFSET_ITEMS = GRAPHQL_PAGE_SIZE * GRAPHQL_MAX_PAGE
PRICE_FILTER_ID = "0"
GRAPHQL_HEADER_ALLOWLIST = {
    "accept",
    "accept-language",
    "apollographql-client-name",
    "apollographql-client-version",
    "authorization",
    "city-id",
    "city-latitude",
    "city-longitude",
    "content-type",
    "latitude",
    "longitude",
    "origin",
    "referer",
    "user-agent",
    "x-iid",
}


class BrowserBlockedError(RuntimeError):
    pass


PROFILE_FILES = (
    "Cookies",
    "Cookies-journal",
    "Local Storage",
    "Session Storage",
    "Storage",
    "Web Data",
    "Web Data-journal",
)


class CdpPage:
    def __init__(self, websocket: aiohttp.ClientWebSocketResponse) -> None:
        self.websocket = websocket
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._events: asyncio.Queue[dict] = asyncio.Queue()
        self._reader_task = asyncio.create_task(self._reader())

    async def start(self) -> None:
        await self.command("Page.enable")
        await self.command("Runtime.enable")

    async def close(self) -> None:
        self._reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._reader_task
        await self.websocket.close()

    async def navigate(self, url: str) -> None:
        await self.command("Page.navigate", {"url": url})
        await self.wait_for_ready_state()

    async def wait_for_ready_state(self, timeout_ms: int = 45_000) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while True:
            state = await self.evaluate("document.readyState")
            if state in {"interactive", "complete"}:
                return
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("Timed out waiting for document.readyState.")
            await asyncio.sleep(0.25)

    async def content(self) -> str:
        return await self.evaluate("document.documentElement.outerHTML") or ""

    async def title(self) -> str:
        return await self.evaluate("document.title") or ""

    async def url(self) -> str:
        return await self.evaluate("window.location.href") or ""

    async def text_content(self) -> str:
        return await self.evaluate("document.body ? document.body.innerText : ''") or ""

    async def evaluate(self, expression: str):
        result = await self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        payload = result.get("result", {})
        if "value" in payload:
            return payload["value"]
        return None

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        await asyncio.sleep(timeout_ms / 1000)

    async def command(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        message_id = self._id
        future = asyncio.get_running_loop().create_future()
        self._pending[message_id] = future
        await self.websocket.send_str(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        return await future

    async def _reader(self) -> None:
        try:
            async for message in self.websocket:
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                payload = json.loads(message.data)
                if "id" in payload:
                    future = self._pending.pop(payload["id"], None)
                    if future is None:
                        continue
                    if "error" in payload:
                        future.set_exception(RuntimeError(payload["error"]))
                    else:
                        future.set_result(payload.get("result", {}))
                    continue
                await self._events.put(payload)
        except asyncio.CancelledError:
            raise
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("CDP websocket closed."))
            self._pending.clear()


class UzumBrowserClient:
    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self._profile_dir: Path | None = None
        self._chrome_process: subprocess.Popen | None = None
        self._session: aiohttp.ClientSession | None = None
        self._page: CdpPage | None = None
        self._debug_port: int | None = None
        self._graphql_search_query: str | None = None
        self._graphql_headers: dict[str, str] | None = None

    async def __aenter__(self):
        self._profile_dir = self._prepare_profile_dir()
        self._debug_port = self._find_free_port()
        self._chrome_process = self._launch_chrome(self._profile_dir, self._debug_port)
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
        )
        page_ws_url = await self._wait_for_debug_target(self._debug_port)
        websocket = await self._session.ws_connect(page_ws_url, max_msg_size=0)
        self._page = CdpPage(websocket)
        await self._page.start()
        return self

    async def __aexit__(self, *_exc):
        if self._page:
            await self._page.close()
        if self._session:
            await self._session.close()
        if self._chrome_process:
            self._chrome_process.terminate()
            try:
                self._chrome_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._chrome_process.kill()
                self._chrome_process.wait(timeout=5)

    async def fetch_product_html(self, url: str) -> str:
        page = await self._navigate(url)
        await page.wait_for_timeout(1_500)
        return await page.content()

    async def collect_listing_links(self, url: str) -> tuple[list[str], list[str]]:
        page = await self._navigate(url)
        await self._auto_scroll(page)
        payload = await page.evaluate(
            """Array.from(document.querySelectorAll('a[href]'))
                .map((anchor) => anchor.href)
                .filter(Boolean)"""
        )
        urls = [self._canonicalize_url(value) for value in payload if isinstance(value, str)]
        category_urls = self._filter_paths(urls, "/category/")
        product_urls = self._filter_paths(urls, "/product/")
        return category_urls, product_urls

    async def collect_root_category_urls(self) -> list[str]:
        page = await self._navigate("https://uzum.uz/ru/category/vse-kategorii-1")
        await page.command("Network.enable")
        await self._discard_events()
        await page.navigate("https://uzum.uz/ru/category/vse-kategorii-1")
        await page.wait_for_ready_state()
        await page.wait_for_timeout(5_000)
        categories = await self._read_root_categories_payload(page)
        return self._category_urls_from_tree(categories)

    async def collect_listing_products(self, url: str) -> list[dict]:
        graphql_products = await self._collect_listing_products_graphql(url)
        if graphql_products is not None:
            return graphql_products

        page = await self._navigate(url)
        await self._auto_scroll(page)
        payload = await page.evaluate(
            """
            (() => {
                const categoryName = (document.querySelector('h1')?.innerText || '').trim();
                return Array.from(
                  document.querySelectorAll('a[href*="/product/"]')
                ).map((anchor) => {
                  const title = (
                    anchor.querySelector('.product-card__title')?.innerText || ''
                  ).trim();
                  const currentPrice = (
                    anchor.querySelector('.card-price__lowest')?.innerText || ''
                  ).trim();
                  const oldPrice = (
                    anchor.querySelector(
                      '.regular-price.card-price--strikethrough'
                    )?.innerText || ''
                  ).trim();
                  const installment = (
                    anchor.querySelector('.card-price__installment')?.innerText || ''
                  ).trim();
                  const rating = (
                    anchor.querySelector(
                      '.reviews__text.rating, .reviews__rating .rating__el'
                    )?.innerText || ''
                  ).trim();
                  const reviews = (
                    anchor.querySelector('.reviews__text.feedback')?.innerText || ''
                  ).trim();
                  const reviewsCount = Number(
                    (reviews.match(/\\d+/g) || []).join('')
                  ) || null;
                  const imageUrls = Array.from(anchor.querySelectorAll('img'))
                    .map((img) => img.currentSrc || img.src || '')
                    .filter(Boolean);
                  return {
                    href: anchor.href,
                    title,
                    current_price: currentPrice,
                    old_price: oldPrice,
                    installment,
                    rating,
                    reviews_count: reviewsCount,
                    image_urls: imageUrls,
                    availability: /завтра|сегодня|доставка/i.test(
                      anchor.innerText || ''
                    ) ? 'available' : 'unknown',
                    category: {
                      name: categoryName,
                      path_text: categoryName,
                      url: window.location.href,
                    },
                    raw_data: {
                      text: anchor.innerText || '',
                      className: anchor.className || '',
                    },
                  };
                });
            })()
            """
        )
        products: list[dict] = []
        seen_product_ids: set[str] = set()
        for raw in payload:
            canonical_url = self._canonicalize_url(raw.get("href", ""))
            product_id = extract_product_id(canonical_url)
            if not product_id or product_id in seen_product_ids:
                continue
            seen_product_ids.add(product_id)
            normalized = normalize_product(
                {
                    "title": raw.get("title"),
                    "current_price": raw.get("current_price"),
                    "old_price": raw.get("old_price"),
                    "rating": raw.get("rating"),
                    "reviews_count": raw.get("reviews_count"),
                    "image_urls": raw.get("image_urls") or [],
                    "availability": raw.get("availability"),
                    "category": raw.get("category"),
                    "category_path_text": (raw.get("category") or {}).get("path_text"),
                    "raw_data": {
                        **(raw.get("raw_data") or {}),
                        "installment": raw.get("installment"),
                        "source": "category_listing_card",
                    },
                },
                canonical_url,
            )
            products.append(normalized)
        return products

    async def collect_search_products(self, text: str, *, limit: int | None) -> list[dict]:
        query = " ".join(text.split())
        if not query:
            return []

        source_url = self._search_url(query)
        products: list[dict] = []
        seen_product_ids: set[str] = set()
        offset = 0
        total: int | None = None

        while limit is None or len(products) < limit:
            page_limit = GRAPHQL_PAGE_SIZE
            if limit is not None:
                page_limit = min(page_limit, limit - len(products))
            if page_limit <= 0:
                break

            search_data = await self._fetch_graphql_search(
                source_url,
                text=query,
                filters=[],
                offset=offset,
                limit=page_limit,
            )
            if search_data is None:
                break

            total = int(search_data.get("total") or 0)
            items = search_data.get("items") or []
            if not items:
                break

            category = search_data.get("category") or {}
            for item in items:
                card = (item or {}).get("catalogCard") or {}
                product_id = card.get("productId") or card.get("id")
                if not product_id or str(product_id) in seen_product_ids:
                    continue
                seen_product_ids.add(str(product_id))
                product = self._normalize_graphql_card(card, category, source_url)
                product["raw_data"] = {
                    **(product.get("raw_data") or {}),
                    "search_query": query,
                }
                products.append(product)
                if limit is not None and len(products) >= limit:
                    break

            offset += page_limit
            if total is not None and offset >= min(total, GRAPHQL_MAX_OFFSET_ITEMS):
                break

        return products

    async def collect_category_page_urls(self, url: str) -> list[str]:
        category_id = self._category_id_from_url(url)
        if category_id:
            segments = await self._build_graphql_segments(url, category_id)
            if segments:
                page_urls: list[str] = []
                for filters, total in segments:
                    page_count = max(1, ceil(total / GRAPHQL_PAGE_SIZE))
                    for page_number in range(1, page_count + 1):
                        page_urls.append(self._category_page_url(url, page_number, filters))
                return page_urls

        page = await self._navigate(url)
        await self._auto_scroll(page)
        payload = await page.evaluate(
            """
            (() => {
                const urls = new Set([window.location.href]);
                Array.from(
                  document.querySelectorAll('a[href*="currentPage="]')
                ).forEach((anchor) => {
                  if (anchor.href) urls.add(anchor.href);
                });
                return Array.from(urls);
            })()
            """
        )
        page_urls = [self._absolute_url(value) for value in payload if isinstance(value, str)]
        return self._sort_category_page_urls(page_urls)

    async def _collect_listing_products_graphql(self, url: str) -> list[dict] | None:
        category_id = self._category_id_from_url(url)
        if not category_id:
            return None

        filters = self._filters_from_url(url)
        page_number = self._page_number_from_url(url)
        offset = (page_number - 1) * GRAPHQL_PAGE_SIZE
        search_data = await self._fetch_graphql_search(
            url,
            category_id=category_id,
            filters=filters,
            offset=offset,
            limit=GRAPHQL_PAGE_SIZE,
        )
        if search_data is None:
            return None

        category = search_data.get("category") or {}
        products: list[dict] = []
        seen_product_ids: set[str] = set()
        for item in search_data.get("items") or []:
            card = (item or {}).get("catalogCard") or {}
            product_id = card.get("productId") or card.get("id")
            if not product_id or str(product_id) in seen_product_ids:
                continue
            seen_product_ids.add(str(product_id))
            products.append(self._normalize_graphql_card(card, category, url))
        return products

    async def _navigate(self, url: str) -> CdpPage:
        if self._page is None:
            raise RuntimeError("Browser page is not initialized.")

        await self._page.navigate(url)
        await self._page.wait_for_timeout(1_000)
        if await self._is_captcha_page():
            if self.config.browser_headless:
                raise BrowserBlockedError(
                    "Uzum showed SmartCaptcha in headless mode. "
                    "Re-run with `UZUM_BROWSER_HEADLESS=false`."
                )
            logger.warning(
                "Captcha page detected for %s, waiting for manual solve in the visible browser.",
                url,
            )
            await self._wait_for_captcha_resolution(url)
        return self._page

    async def _auto_scroll(self, page: CdpPage) -> None:
        stable_rounds = 0
        previous_height = -1
        for _ in range(self.config.browser_scroll_max_rounds):
            height = await page.evaluate("document.body ? document.body.scrollHeight : 0")
            if height == previous_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
                previous_height = height
            if stable_rounds >= 3:
                break
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(self.config.browser_scroll_pause_ms)
        await page.evaluate("window.scrollTo(0, 0)")

    async def _is_captcha_page(self) -> bool:
        if self._page is None:
            return False
        url = (await self._page.url()).lower()
        title = (await self._page.title()).lower()
        body = (await self._page.text_content()).lower()
        return (
            "showcaptcha" in url
            or "smartcaptcha" in url
            or "robot emasmisiz" in title
            or "smartcaptcha" in body
        )

    async def _wait_for_captcha_resolution(self, original_url: str) -> None:
        if self._page is None:
            raise RuntimeError("Browser page is not initialized.")

        deadline = (
            asyncio.get_running_loop().time()
            + self.config.browser_interactive_captcha_timeout_seconds
        )
        while True:
            if asyncio.get_running_loop().time() > deadline:
                raise BrowserBlockedError(
                    "Captcha was not solved within "
                    f"{self.config.browser_interactive_captcha_timeout_seconds}s."
                )
            if not await self._is_captcha_page():
                current_url = await self._page.url()
                if current_url != original_url:
                    await self._page.navigate(original_url)
                    await self._page.wait_for_timeout(1_000)
                if not await self._is_captcha_page():
                    return
            await asyncio.sleep(1)

    async def _wait_for_debug_target(self, port: int) -> str:
        if self._session is None:
            raise RuntimeError("HTTP session is not initialized.")

        deadline = asyncio.get_running_loop().time() + 30
        last_error: Exception | None = None
        while True:
            if self._chrome_process and self._chrome_process.poll() is not None:
                raise RuntimeError(
                    f"Chrome exited early with code {self._chrome_process.returncode}."
                ) from last_error
            try:
                async with self._session.get(f"http://127.0.0.1:{port}/json/list") as response:
                    targets = await response.json()
                for target in targets:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
            except Exception as error:
                last_error = error
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("Timed out waiting for Chrome DevTools target.") from last_error
            await asyncio.sleep(0.25)

    async def _fetch_graphql_search(
        self,
        source_url: str,
        *,
        category_id: str | None = None,
        text: str | None = None,
        filters: list[dict] | None = None,
        offset: int,
        limit: int,
    ) -> dict | None:
        if not category_id and not text:
            raise ValueError("GraphQL search requires category_id or text.")

        await self._ensure_graphql_search(source_url)
        if not self._session or not self._graphql_headers or not self._graphql_search_query:
            return None

        query_input = {
            "showAdultContent": "TRUE",
            "filters": filters or [],
            "sort": "BY_RELEVANCE_DESC",
            "pagination": {"offset": offset, "limit": limit},
            "correctQuery": False,
            "getFastCategories": True,
            "fastCategoriesLimit": 11,
            "fastCategoriesLevelOffset": 1,
            "getPromotionItems": True,
            "getFastFacets": True,
            "fastFacetsLimit": 10,
        }
        if category_id:
            query_input["categoryId"] = category_id
        if text:
            query_input["text"] = text

        payload = {
            "operationName": "MakeSearch_ItemsAndFilters",
            "variables": {
                "queryInput": query_input
            },
            "query": self._graphql_search_query,
        }
        last_error: RuntimeError | None = None
        for attempt in range(1, self.config.max_retries + 1):
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=self._graphql_headers,
            ) as response:
                body = await response.text()
                if response.status >= 400:
                    last_error = RuntimeError(f"Uzum GraphQL {response.status}: {body[:500]}")
                    if response.status == 401:
                        self._graphql_search_query = None
                        self._graphql_headers = None
                        await self._ensure_graphql_search(source_url)
                        if self._graphql_search_query and self._graphql_headers:
                            payload["query"] = self._graphql_search_query
                else:
                    data = json.loads(body)
                    errors = data.get("errors") or []
                    if not errors:
                        return (data.get("data") or {}).get("makeSearch")
                    last_error = RuntimeError(f"Uzum GraphQL errors: {errors[:2]}")
                    if not self._is_retryable_graphql_error(errors):
                        raise last_error
            if attempt < self.config.max_retries:
                await asyncio.sleep(min(2**attempt, 10))
        if last_error:
            raise last_error
        return None

    async def _build_graphql_segments(
        self,
        source_url: str,
        category_id: str,
    ) -> list[tuple[list[dict], int]]:
        root_data = await self._fetch_graphql_search(
            source_url,
            category_id=category_id,
            filters=[],
            offset=0,
            limit=0,
        )
        if root_data is None:
            return []

        total = root_data.get("total") or 0
        if total <= GRAPHQL_MAX_OFFSET_ITEMS:
            return [([], total)]

        price_range = self._price_range_from_facets(root_data.get("facets") or [])
        if price_range is None:
            logger.warning(
                "Category %s has total=%s but no price facet for segmentation; "
                "only first %s products are addressable through search offset.",
                category_id,
                total,
                GRAPHQL_MAX_OFFSET_ITEMS,
            )
            return [([], GRAPHQL_MAX_OFFSET_ITEMS)]

        segments: list[tuple[list[dict], int]] = []
        await self._split_price_segment(
            source_url,
            category_id,
            min_price=price_range[0],
            max_price=price_range[1],
            segments=segments,
        )
        return segments

    async def _split_price_segment(
        self,
        source_url: str,
        category_id: str,
        *,
        min_price: int,
        max_price: int,
        segments: list[tuple[list[dict], int]],
    ) -> None:
        filters = [self._price_filter(min_price, max_price)]
        data = await self._fetch_graphql_search(
            source_url,
            category_id=category_id,
            filters=filters,
            offset=0,
            limit=0,
        )
        total = (data or {}).get("total") or 0
        if total == 0:
            return
        if total <= GRAPHQL_MAX_OFFSET_ITEMS or min_price >= max_price:
            if total > GRAPHQL_MAX_OFFSET_ITEMS:
                logger.warning(
                    "Price segment still exceeds GraphQL offset limit: category=%s "
                    "range=%s..%s total=%s.",
                    category_id,
                    min_price,
                    max_price,
                    total,
                )
                total = GRAPHQL_MAX_OFFSET_ITEMS
            segments.append((filters, total))
            return

        middle = (min_price + max_price) // 2
        await self._split_price_segment(
            source_url,
            category_id,
            min_price=min_price,
            max_price=middle,
            segments=segments,
        )
        await self._split_price_segment(
            source_url,
            category_id,
            min_price=middle + 1,
            max_price=max_price,
            segments=segments,
        )

    async def _ensure_graphql_search(self, source_url: str) -> None:
        if self._graphql_search_query and self._graphql_headers:
            return
        if self._page is None:
            raise RuntimeError("Browser page is not initialized.")

        page = self._page
        await page.command("Network.enable")
        await self._discard_events()
        await self._navigate(source_url)
        await page.wait_for_timeout(5_000)

        while not page._events.empty():
            event = await page._events.get()
            if event.get("method") != "Network.requestWillBeSent":
                continue
            request = event.get("params", {}).get("request", {})
            post_data = request.get("postData")
            if not post_data or "MakeSearch_ItemsAndFilters" not in post_data:
                continue
            payload = json.loads(post_data)
            if payload.get("operationName") != "MakeSearch_ItemsAndFilters":
                continue
            self._graphql_search_query = payload["query"]
            headers = {
                key.lower(): value
                for key, value in (request.get("headers") or {}).items()
                if key.lower() in GRAPHQL_HEADER_ALLOWLIST
            }
            headers["content-type"] = "application/json"
            self._graphql_headers = headers
            return

        raise RuntimeError("Could not capture Uzum MakeSearch GraphQL request.")

    async def _discard_events(self) -> None:
        if self._page is None:
            return
        while not self._page._events.empty():
            await self._page._events.get()

    async def _read_root_categories_payload(self, page: CdpPage) -> list[dict]:
        request_urls: dict[str, str] = {}
        candidate_ids: list[str] = []

        while not page._events.empty():
            event = await page._events.get()
            method = event.get("method")
            params = event.get("params", {})
            request_id = params.get("requestId")

            if method == "Network.requestWillBeSent" and request_id:
                request_urls[request_id] = params.get("request", {}).get("url", "")
                continue

            if method != "Network.loadingFinished" or not request_id:
                continue

            request_url = request_urls.get(request_id, "")
            if ROOT_CATEGORIES_URL not in request_url:
                continue
            candidate_ids.append(request_id)

        for request_id in reversed(candidate_ids):
            try:
                body = await page.command("Network.getResponseBody", {"requestId": request_id})
            except RuntimeError:
                continue
            payload = json.loads(body.get("body") or "{}")
            categories = payload.get("payload")
            if isinstance(categories, list) and categories:
                return categories
        return []

    def _category_urls_from_tree(self, categories: list[dict]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()

        def visit(node: dict) -> None:
            category_id = node.get("id")
            if not isinstance(category_id, int):
                return

            children = [child for child in node.get("children") or [] if isinstance(child, dict)]
            if children:
                for child in children:
                    visit(child)
                return

            title = str(node.get("seoHeader") or node.get("seoMetaTag") or node.get("title") or "")
            slug = self._slugify_category_title(title)
            if slug:
                url = f"{BASE_URL}/ru/category/{slug}-{category_id}"
            else:
                url = f"{BASE_URL}/ru/category/-{category_id}"
            if url not in seen:
                seen.add(url)
                urls.append(url)

        for category in categories:
            if isinstance(category, dict):
                visit(category)
        return urls

    def _normalize_graphql_card(self, card: dict, category: dict, category_url: str) -> dict:
        product_id = str(card.get("productId") or card.get("id") or "")
        slug = self._slugify_category_title(str(card.get("title") or "product"))
        canonical_url = f"{BASE_URL}/ru/product/{slug}-{product_id}"
        price_block = (card.get("buyingOptions") or {}).get("priceBlock") or {}
        final_price = price_block.get("finalPrice") or {}
        full_price = price_block.get("fullPrice") or {}
        sell_price = price_block.get("sellPrice") or {}
        delivery_options = (card.get("buyingOptions") or {}).get("deliveryOptions") or {}
        image_urls = [
            ((photo.get("link") or {}).get("high") or (photo.get("link") or {}).get("low"))
            for photo in card.get("photos") or []
            if isinstance(photo, dict)
        ]
        category_title = category.get("title") or category.get("title_ru")
        category_payload = None
        if category.get("id") or category_title:
            category_payload = {
                "source_category_id": category.get("id"),
                "name": category_title,
                "path_text": category_title,
                "url": category_url,
                "raw_data": category,
            }
        raw = {
            "source_product_id": product_id,
            "title": card.get("title"),
            "current_price": final_price.get("amount") or sell_price.get("amount"),
            "old_price": full_price.get("amount"),
            "rating": card.get("rating"),
            "reviews_count": card.get("feedbackQuantity"),
            "cover_image_url": next((url for url in image_urls if url), None),
            "image_urls": [url for url in image_urls if url],
            "availability": "available" if delivery_options else "unknown",
            "category": category_payload,
            "category_path_text": category_title,
            "raw_data": {
                "source": "graphql_make_search",
                "catalog_card": card,
            },
        }
        return normalize_product(raw, canonical_url)

    @staticmethod
    def _is_retryable_graphql_error(errors: list[dict]) -> bool:
        retryable_markers = (
            "REQUEST_TIMEOUT",
            "SUBREQUEST_HTTP_ERROR",
            "Service Unavailable",
            "Request timed out",
        )
        payload = json.dumps(errors, ensure_ascii=False)
        return any(marker in payload for marker in retryable_markers)

    @staticmethod
    def _price_range_from_facets(facets: list[dict]) -> tuple[int, int] | None:
        for facet in facets:
            filter_data = facet.get("filter") or {}
            range_data = facet.get("range") or {}
            if str(filter_data.get("id")) != PRICE_FILTER_ID or not range_data:
                continue
            min_price = int(float(range_data.get("min") or 0))
            max_price = int(float(range_data.get("max") or 0))
            if max_price >= min_price:
                return min_price, max_price
        return None

    @staticmethod
    def _price_filter(min_price: int, max_price: int) -> dict:
        return {
            "filterType": "RANGE",
            "id": PRICE_FILTER_ID,
            "range": {"min": min_price, "max": max_price},
            "list": None,
        }

    @staticmethod
    def _slugify_category_title(value: str) -> str:
        transliteration = str.maketrans(
            {
                "а": "a",
                "б": "b",
                "в": "v",
                "г": "g",
                "д": "d",
                "е": "e",
                "ё": "e",
                "ж": "zh",
                "з": "z",
                "и": "i",
                "й": "j",
                "к": "k",
                "л": "l",
                "м": "m",
                "н": "n",
                "о": "o",
                "п": "p",
                "р": "r",
                "с": "s",
                "т": "t",
                "у": "u",
                "ф": "f",
                "х": "h",
                "ц": "c",
                "ч": "ch",
                "ш": "sh",
                "щ": "sch",
                "ъ": "",
                "ы": "y",
                "ь": "",
                "э": "e",
                "ю": "yu",
                "я": "ya",
            }
        )
        normalized = unicodedata.normalize("NFKD", value.strip().lower()).translate(transliteration)
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
        return re.sub(r"-{2,}", "-", slug)

    def _launch_chrome(self, profile_dir: Path, port: int) -> subprocess.Popen:
        command = [
            self.config.browser_executable_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            f"--profile-directory={self.config.browser_profile_name}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "about:blank",
        ]
        if self.config.browser_headless:
            command.append("--headless=new")
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _prepare_profile_dir(self) -> Path:
        source = self.config.browser_profile_source
        if not source.exists():
            raise RuntimeError(f"Chrome profile source does not exist: {source}")

        runtime_dir = self.config.browser_runtime_profile_dir
        runtime_dir.mkdir(parents=True, exist_ok=True)
        local_state_path = source / "Local State"
        runtime_local_state = runtime_dir / "Local State"
        if local_state_path.exists() and not runtime_local_state.exists():
            shutil.copy2(local_state_path, runtime_local_state)

        source_profile = source / self.config.browser_profile_name
        if not source_profile.exists():
            raise RuntimeError(f"Chrome profile does not exist: {source_profile}")

        target_profile = runtime_dir / self.config.browser_profile_name
        target_profile.mkdir(parents=True, exist_ok=True)
        for name in PROFILE_FILES:
            source_path = source_profile / name
            if not source_path.exists():
                continue
            target_path = target_profile / name
            if target_path.exists():
                continue
            if source_path.is_dir():
                shutil.copytree(source_path, target_path)
            else:
                shutil.copy2(source_path, target_path)
        return runtime_dir

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            return sock.getsockname()[1]

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        absolute = urljoin(BASE_URL, url)
        parsed = urlparse(absolute)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def _absolute_url(url: str) -> str:
        return urljoin(BASE_URL, url)

    @staticmethod
    def _filter_paths(urls: list[str], path_fragment: str) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            parsed = urlparse(url)
            if parsed.netloc != "uzum.uz" or path_fragment not in parsed.path:
                continue
            if url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    @staticmethod
    def _sort_category_page_urls(urls: list[str]) -> list[str]:
        def key(url: str) -> tuple[str, int]:
            parsed = urlparse(url)
            page_match = next(
                (
                    int(part.split("=", 1)[1])
                    for part in parsed.query.split("&")
                    if part.startswith("currentPage=") and part.split("=", 1)[1].isdigit()
                ),
                1,
            )
            return (f"{parsed.scheme}://{parsed.netloc}{parsed.path}", page_match)

        seen: set[str] = set()
        ordered: list[str] = []
        for url in sorted(urls, key=key):
            if url in seen:
                continue
            seen.add(url)
            ordered.append(url)
        return ordered

    @staticmethod
    def _category_id_from_url(url: str) -> str | None:
        match = re.search(r"-(\d+)(?:[/?#]|$)", urlparse(url).path)
        return match.group(1) if match else None

    @staticmethod
    def _page_number_from_url(url: str) -> int:
        parsed = urlparse(url)
        value = (parse_qs(parsed.query).get("currentPage") or ["1"])[0]
        return int(value) if value.isdigit() and int(value) > 0 else 1

    @staticmethod
    def _category_page_url(
        url: str,
        page_number: int,
        filters: list[dict] | None = None,
    ) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if page_number <= 1:
            query.pop("currentPage", None)
        else:
            query["currentPage"] = [str(page_number)]
        if filters:
            query["filters"] = [UzumBrowserClient._filters_to_query_value(filters)]
        else:
            query.pop("filters", None)
        return urlunparse(
            parsed._replace(
                query=urlencode(query, doseq=True),
                fragment="",
            )
        )

    @staticmethod
    def _search_url(query: str) -> str:
        return f"{BASE_URL}/ru/search?{urlencode({'query': query})}"

    @staticmethod
    def _filters_to_query_value(filters: list[dict]) -> str:
        parts: list[str] = []
        for filter_data in filters:
            if filter_data.get("filterType") == "RANGE":
                range_data = filter_data.get("range") or {}
                parts.append(
                    "filter=RV-"
                    f"{filter_data['id']}:{range_data['min']}~{range_data['max']}"
                )
            elif filter_data.get("filterType") == "LIST":
                values = ((filter_data.get("list") or {}).get("values") or [])
                parts.append(f"filter=MC-{filter_data['id']}:{','.join(values)}")
        return "&".join(parts)

    @staticmethod
    def _filters_from_url(url: str) -> list[dict]:
        raw_filters = (parse_qs(urlparse(url).query).get("filters") or [""])[0]
        filters: list[dict] = []
        for raw_filter in raw_filters.split("&"):
            if not raw_filter.startswith("filter="):
                continue
            value = raw_filter.split("=", 1)[1]
            if value.startswith("RV-"):
                filter_id, bounds = value[3:].split(":", 1)
                min_price, max_price = bounds.split("~", 1)
                filters.append(
                    {
                        "filterType": "RANGE",
                        "id": filter_id,
                        "range": {
                            "min": int(float(min_price)),
                            "max": int(float(max_price)),
                        },
                        "list": None,
                    }
                )
            elif value.startswith("MC-"):
                filter_id, raw_values = value[3:].split(":", 1)
                filters.append(
                    {
                        "filterType": "LIST",
                        "id": filter_id,
                        "range": None,
                        "list": {"values": [item for item in raw_values.split(",") if item]},
                    }
                )
        return filters
