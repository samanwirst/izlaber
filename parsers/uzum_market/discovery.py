from collections.abc import AsyncIterator

from parsers.uzum_market.browser import UzumBrowserClient
from parsers.uzum_market.config import ParserConfig


class UzumDiscovery:
    def __init__(
        self,
        client: UzumBrowserClient,
        config: ParserConfig,
        start_urls: list[str] | None = None,
    ) -> None:
        self.client = client
        self.start_urls = start_urls or list(config.discovery_start_urls)

    async def discover(self, limit: int | None = None) -> AsyncIterator[str]:
        seen_categories: set[str] = set()
        root_category_urls = await self.client.collect_root_category_urls()
        category_urls = root_category_urls or self.start_urls

        for category_url in category_urls:
            if category_url in seen_categories:
                continue
            seen_categories.add(category_url)
            yield category_url
            if limit is not None and len(seen_categories) >= limit:
                return
