from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout


class ServerAPIError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProductDTO:
    id: int
    title: str
    canonical_url: str
    cover_image_url: str | None
    current_price: str | None
    old_price: str | None
    currency: str
    rating: str | None
    reviews_count: int | None
    category_path_text: str | None


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
        rows = data.get("results", data if isinstance(data, list) else [])
        return [_parse_product(row) for row in rows[:limit]]

    async def get_product(self, product_id: int) -> ProductDTO:
        return _parse_product(await self._get(f"/v1/products/{product_id}/"))

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


def render_products(products: list[ProductDTO], query: str) -> str:
    if not products:
        return f"В каталоге пока нет товаров по запросу <b>{escape(query)}</b>."

    noun = "товар" if len(products) == 1 else "товара"
    lines = [f"Нашел {len(products)} {noun} по запросу <b>{escape(query)}</b>:"]
    for index, product in enumerate(products, start=1):
        details = []
        if product.current_price:
            details.append(_format_price(product.current_price, product.currency))
        if product.rating:
            details.append(f"rating {product.rating}")
        if product.reviews_count is not None:
            details.append(f"{product.reviews_count} отзывов")
        suffix = f" - {escape(', '.join(details))}" if details else ""
        lines.append(
            f'{index}. <a href="{escape(product.canonical_url)}">'
            f"{escape(product.title)}</a>{suffix}"
        )
    return "\n\n".join(lines)


def render_product_card(product: ProductDTO, index: int) -> str:
    lines = [
        f'<b>{index}. <a href="{escape(product.canonical_url)}">{escape(product.title)}</a></b>'
    ]
    if product.current_price:
        price = escape(_format_price(product.current_price, product.currency))
        lines.append(f"Цена: <b>{price}</b>")
    if product.old_price:
        lines.append(f"Старая цена: {escape(_format_price(product.old_price, product.currency))}")
    details = []
    if product.rating:
        details.append(f"рейтинг {product.rating}")
    if product.reviews_count is not None:
        details.append(f"{product.reviews_count} отзывов")
    if details:
        lines.append(escape(", ".join(details)))
    if product.category_path_text:
        lines.append(f"Категория: {escape(product.category_path_text)}")
    return "\n".join(lines)


def _parse_product(row: dict[str, Any]) -> ProductDTO:
    return ProductDTO(
        id=row["id"],
        title=row["title"],
        canonical_url=row["canonical_url"],
        cover_image_url=row.get("cover_image_url"),
        current_price=row.get("current_price"),
        old_price=row.get("old_price"),
        currency=row.get("currency") or "UZS",
        rating=row.get("rating"),
        reviews_count=row.get("reviews_count"),
        category_path_text=row.get("category_path_text"),
    )


def _format_price(value: str, currency: str) -> str:
    amount = Decimal(str(value))
    normalized = int(amount) if amount == amount.to_integral_value() else amount
    suffix = "сум" if currency == "UZS" else currency
    return f"{normalized:,}".replace(",", " ") + f" {suffix}"
