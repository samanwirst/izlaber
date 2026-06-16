from asyncio import TimeoutError
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout


class UzumSearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class UzumProduct:
    title: str
    url: str
    price: str | None = None
    old_price: str | None = None
    rating: float | None = None
    feedback_quantity: int | None = None
    image_url: str | None = None


class UzumSearchService:
    def __init__(self, graphql_url: str, timeout: float = 15.0) -> None:
        self.graphql_url = graphql_url
        self.timeout = timeout

    async def search(self, text: str, limit: int = 3) -> list[UzumProduct]:
        query = text.strip()
        if not query:
            return []

        payload = {
            "operationName": "getMakeSearch",
            "variables": {
                "queryInput": {
                    "text": query,
                    "showAdultContent": "FALSE",
                    "filters": [],
                    "sort": "BY_RELEVANCE_DESC",
                    "pagination": {
                        "offset": 0,
                        "limit": limit,
                    },
                }
            },
            "query": _MAKE_SEARCH_QUERY,
        }

        headers = {
            "Accept": "application/json",
            "Accept-Language": "ru-RU",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        timeout = ClientTimeout(total=self.timeout)
        try:
            async with ClientSession(timeout=timeout, headers=headers) as session:
                async with session.post(self.graphql_url, json=payload) as response:
                    if response.status >= 400:
                        body = await response.text()
                        msg = f"Uzum search returned HTTP {response.status}: {body[:200]}"
                        raise UzumSearchError(msg)
                    data = await response.json(content_type=None)
        except (ClientError, TimeoutError) as exc:
            msg = f"Cannot connect to Uzum search: {exc}"
            raise UzumSearchError(msg) from exc

        if errors := data.get("errors"):
            msg = f"Uzum search returned GraphQL errors: {errors}"
            raise UzumSearchError(msg)

        items = data.get("data", {}).get("makeSearch", {}).get("items", [])
        return [product for item in items if (product := _parse_product(item)) is not None][:limit]


def render_products(products: list[UzumProduct], query: str) -> str:
    if not products:
        return f"По запросу <b>{escape(query)}</b> ничего не найдено."

    count = len(products)
    noun = "карточку" if count == 1 else "карточки"
    lines = [f"Нашел {count} {noun} по запросу <b>{escape(query)}</b>:"]
    for index, product in enumerate(products, start=1):
        details = []
        if product.price:
            details.append(product.price)
        if product.rating is not None:
            details.append(f"rating {product.rating:g}")
        if product.feedback_quantity is not None:
            details.append(f"{product.feedback_quantity} отзывов")

        suffix = f" - {escape(', '.join(details))}" if details else ""
        lines.append(f'{index}. <a href="{escape(product.url)}">{escape(product.title)}</a>{suffix}')

    return "\n\n".join(lines)


def render_search_unavailable(query: str) -> str:
    search_url = f"https://uzum.uz/ru/search?query={quote(query.strip())}"
    return (
        "Не получилось получить карточки через API Uzum: публичный endpoint сейчас недоступен.\n\n"
        f'Открыть поиск вручную: <a href="{escape(search_url)}">{escape(query)}</a>'
    )


def _parse_product(item: dict) -> UzumProduct | None:
    card = item.get("catalogCard") or {}
    title = card.get("title")
    product_id = card.get("productId") or card.get("id")
    if not title or not product_id:
        return None

    photos = card.get("photos") or []
    image_url = None
    if photos:
        link = photos[0].get("link") or {}
        image_url = link.get("high") or link.get("low")

    return UzumProduct(
        title=title,
        url=_build_product_url(title=title, product_id=str(product_id)),
        price=_format_price(card.get("minSellPrice")),
        old_price=_format_price(card.get("minFullPrice")),
        rating=card.get("rating"),
        feedback_quantity=card.get("feedbackQuantity"),
        image_url=image_url,
    )


def _build_product_url(title: str, product_id: str) -> str:
    slug = _slugify(title) or "product"
    return f"https://uzum.uz/ru/product/{slug}-{quote(product_id)}"


def _slugify(value: str) -> str:
    result = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            result.append(char)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True

    return "".join(result).strip("-")


def _format_price(value: int | float | str | None) -> str | None:
    if value is None:
        return None

    try:
        amount = Decimal(str(value)) / Decimal(100)
    except Exception:
        return None

    normalized = int(amount) if amount == amount.to_integral_value() else amount
    return f"{normalized:,}".replace(",", " ") + " сум"


_MAKE_SEARCH_QUERY = """
query getMakeSearch($queryInput: MakeSearchQueryInput!) {
  makeSearch(query: $queryInput) {
    items {
      catalogCard {
        id
        productId
        title
        minSellPrice
        minFullPrice
        rating
        feedbackQuantity
        photos {
          link(trans: PRODUCT_540) {
            high
            low
          }
        }
      }
    }
    total
  }
}
"""
