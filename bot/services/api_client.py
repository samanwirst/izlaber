from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Any
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout

from bot.locales import format_message, product_label, product_noun, review_text


class ServerAPIError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProductDTO:
    id: int
    title: str
    canonical_url: str
    cover_image_url: str | None
    brand: str | None
    current_price: str | None
    old_price: str | None
    currency: str
    rating: str | None
    reviews_count: int | None
    category_path_text: str | None
    source_product_id: str | None = None
    tracking_url: str | None = None


class ServerAPIClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session: ClientSession | None = None

    async def __aenter__(self):
        self._session = ClientSession(
            timeout=ClientTimeout(total=self.timeout),
            headers={"X-Internal-API-Key": self.api_key, "Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_exc):
        if self._session:
            await self._session.close()

    async def search_products(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> list[ProductDTO]:
        params = {
            "q": query,
            "marketplace": "uzum",
            "limit": str(limit),
            "offset": str(offset),
        }
        if filters:
            params.update({key: str(value) for key, value in filters.items() if value is not None})
        data = await self._get("/v1/products/", params=params)
        rows = _response_rows(data)
        return [_parse_product(row) for row in rows[:limit]]

    async def visual_search_products(
        self,
        *,
        ahash: str,
        dhash: str,
        max_distance: int,
        limit: int = 5,
    ) -> list[ProductDTO]:
        data = await self._post(
            "/v1/products/visual-search/",
            payload={
                "ahash": ahash,
                "dhash": dhash,
                "marketplace": "uzum",
                "active_only": True,
                "max_distance": max_distance,
                "limit": limit,
            },
        )
        rows = _response_rows(data)
        return [_parse_product(row) for row in rows[:limit]]

    async def index_product_covers(
        self,
        *,
        product_ids: list[int] | None = None,
        source_product_ids: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "marketplace": "uzum",
            "limit": limit,
        }
        if product_ids:
            payload["product_ids"] = product_ids
        if source_product_ids:
            payload["source_product_ids"] = source_product_ids
        data = await self._post("/v1/products/visual-index/", payload=payload)
        return data if isinstance(data, dict) else {}

    async def get_product(self, product_id: int) -> ProductDTO:
        return _parse_product(await self._get(f"/v1/products/{product_id}/"))

    async def load_language_preferences(self) -> dict[int, str]:
        data = await self._get("/v1/user-preferences/languages/")
        rows = data if isinstance(data, list) else []
        preferences: dict[int, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                user_id = int(row["telegram_user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            language_code = str(row.get("language_code") or "").strip()
            if language_code:
                preferences[user_id] = language_code
        return preferences

    async def set_language_preference(self, telegram_user_id: int, language_code: str) -> str:
        data = await self._post(
            f"/v1/user-preferences/languages/{telegram_user_id}/",
            payload={"language_code": language_code},
        )
        if isinstance(data, dict):
            return str(data.get("language_code") or language_code)
        return language_code

    async def load_active_user_consents(self, consent_version: str) -> set[int]:
        data = await self._get(
            "/v1/user-consents/",
            params={"active_only": "true", "version": consent_version},
        )
        rows = data if isinstance(data, list) else []
        user_ids: set[int] = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("has_active_consent"):
                continue
            try:
                user_ids.add(int(row["telegram_user_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return user_ids

    async def set_user_consent(
        self,
        *,
        telegram_user_id: int,
        action: str,
        consent_version: str,
        language_code: str,
    ) -> bool:
        data = await self._post(
            f"/v1/user-consents/{telegram_user_id}/",
            payload={
                "action": action,
                "consent_version": consent_version,
                "language_code": language_code,
            },
        )
        return bool(isinstance(data, dict) and data.get("has_active_consent"))

    async def create_analytics_event(self, payload: dict[str, Any]) -> UUID | None:
        data = await self._post("/v1/analytics/events/", payload=payload)
        if not isinstance(data, dict) or not data.get("event_id"):
            return None
        return UUID(str(data["event_id"]))

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if self._session is None:
            raise RuntimeError("Client session is not started.")
        try:
            async with self._session.get(f"{self.base_url}{path}", params=params) as response:
                body = await response.text()
                if response.status >= 400:
                    raise ServerAPIError(f"Server returned HTTP {response.status}: {body[:200]}")
                return await response.json(content_type=None)
        except ClientError as exc:
            raise ServerAPIError(f"Cannot connect to server API: {exc}") from exc

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if self._session is None:
            raise RuntimeError("Client session is not started.")
        try:
            async with self._session.post(f"{self.base_url}{path}", json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise ServerAPIError(f"Server returned HTTP {response.status}: {body[:200]}")
                return await response.json(content_type=None)
        except ClientError as exc:
            raise ServerAPIError(f"Cannot connect to server API: {exc}") from exc


def render_products(
    products: list[ProductDTO],
    query: str,
    language_code: str | None = None,
) -> str:
    if not products:
        return format_message("guest_no_results", language_code, query=query)

    lines = [
        format_message(
            "guest_results_header",
            language_code,
            query=query,
            count=len(products),
            noun=product_noun(len(products), language_code),
        )
    ]
    for index, product in enumerate(products, start=1):
        details = []
        if product.current_price:
            details.append(_format_price(product.current_price, product.currency, language_code))
        if product.rating:
            details.append(f"{product_label('rating', language_code)} {product.rating}")
        if product.reviews_count is not None:
            details.append(review_text(product.reviews_count, language_code))
        suffix = f" - {escape(', '.join(details))}" if details else ""
        product_url = product.tracking_url or product.canonical_url
        lines.append(
            f'{index}. <a href="{escape(product_url)}">'
            f"{escape(product.title)}</a>{suffix}"
        )
    return "\n\n".join(lines)


def render_product_card(product: ProductDTO, index: int, language_code: str | None = None) -> str:
    product_url = product.tracking_url or product.canonical_url
    lines = [
        f'<b>{index}. <a href="{escape(product_url)}">{escape(product.title)}</a></b>'
    ]
    if product.current_price:
        price = escape(_format_price(product.current_price, product.currency, language_code))
        lines.append(f"{product_label('price', language_code)}: <b>{price}</b>")
    if product.old_price:
        old_price = escape(_format_price(product.old_price, product.currency, language_code))
        lines.append(f"{product_label('old_price', language_code)}: {old_price}")
    details = []
    if product.rating:
        details.append(f"{product_label('rating', language_code)} {product.rating}")
    if product.reviews_count is not None:
        details.append(review_text(product.reviews_count, language_code))
    if details:
        lines.append(escape(", ".join(details)))
    if product.category_path_text:
        category = escape(product.category_path_text)
        lines.append(f"{product_label('category', language_code)}: {category}")
    lines.extend(["", f"<i>{escape(product_label('footer', language_code))}</i>"])
    return "\n".join(lines)


def _parse_product(row: dict[str, Any]) -> ProductDTO:
    return ProductDTO(
        id=row["id"],
        source_product_id=row.get("source_product_id"),
        title=row["title"],
        canonical_url=row["canonical_url"],
        cover_image_url=row.get("cover_image_url"),
        brand=row.get("brand"),
        current_price=row.get("current_price"),
        old_price=row.get("old_price"),
        currency=row.get("currency") or "UZS",
        rating=row.get("rating"),
        reviews_count=row.get("reviews_count"),
        category_path_text=row.get("category_path_text"),
    )


def product_click_url(
    *,
    public_base_url: str,
    product_id: int,
    context_event_id: UUID | None = None,
) -> str:
    if not public_base_url:
        return ""
    base_url = public_base_url.rstrip("/")
    url = f"{base_url}/api/v1/redirect/products/{product_id}/"
    if context_event_id is not None:
        return f"{url}?ctx={context_event_id}"
    return url


def _response_rows(data: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    rows = data.get("results", [])
    return rows if isinstance(rows, list) else []


def _format_price(value: str, currency: str, language_code: str | None = None) -> str:
    amount = Decimal(str(value))
    normalized = int(amount) if amount == amount.to_integral_value() else amount
    suffix = product_label("currency_uzs", language_code) if currency == "UZS" else currency
    return f"{normalized:,}".replace(",", " ") + f" {suffix}"
