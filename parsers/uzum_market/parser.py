from parsers.uzum_market.browser import UzumBrowserClient
from parsers.uzum_market.normalizer import normalize_product, products_from_html


class UzumProductParser:
    def __init__(self, client: UzumBrowserClient) -> None:
        self.client = client

    async def parse_product_url(self, url: str) -> dict:
        html = await self.client.fetch_product_html(url)
        products = products_from_html(html, url)
        if products:
            return products[0]

        return normalize_product(
            {
                "title": url.rsplit("/", 1)[-1].replace("-", " "),
                "availability": "unknown",
                "raw_data": {"source": "fallback_title_only"},
            },
            url,
        )
