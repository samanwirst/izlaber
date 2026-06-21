import asyncio
import logging

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from parsers.uzum_market.config import ParserConfig
from parsers.uzum_market.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class FetchBlockedError(RuntimeError):
    pass


class UzumHTTPClient:
    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self.rate_limiter = RateLimiter(config.crawl_delay_seconds)
        self._session: ClientSession | None = None

    async def __aenter__(self):
        self._session = ClientSession(
            timeout=ClientTimeout(total=self.config.request_timeout),
            headers={
                "User-Agent": "IzlaberBot/0.1 public-catalog-crawler",
                "Accept": "text/html,application/json",
            },
        )
        return self

    async def __aexit__(self, *_exc):
        if self._session:
            await self._session.close()

    async def fetch_text(self, url: str) -> str:
        if self._session is None:
            raise RuntimeError("Client session is not started.")
        for attempt in range(1, self.config.max_retries + 1):
            await self.rate_limiter.wait()
            try:
                async with self._session.get(url) as response:
                    await self._raise_for_block(response, url)
                    if response.status >= 500:
                        raise ClientError(f"Server returned {response.status}")
                    return await response.text()
            except (ClientError, asyncio.TimeoutError) as error:
                if attempt == self.config.max_retries:
                    raise
                delay = 2 ** attempt
                logger.warning("Fetch failed for %s (%s), retrying in %ss", url, error, delay)
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")

    async def _raise_for_block(self, response: ClientResponse, url: str) -> None:
        if response.status in {401, 403, 429}:
            raise FetchBlockedError(f"Back off for {url}: HTTP {response.status}")
        if "x-yandex-captcha" in response.headers:
            raise FetchBlockedError(f"Captcha received for {url}; crawler will not bypass it.")
