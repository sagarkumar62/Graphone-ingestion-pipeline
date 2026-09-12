from src.crawlers.base import BaseCrawler
from src.crawlers.async_crawler import async_crawler_engine
from src.core.models import RawPayload

class AsyncHTTPCrawler(BaseCrawler):
    """
    Lightweight async HTTP crawler delegating to AsyncCrawlerEngine.
    Enforces zero-fabrication rules, rate limiting, and status classification.
    """

    async def fetch(self, url: str, source_name: str) -> RawPayload:
        return await async_crawler_engine.fetch(url, source_name)

    async def fetch_with_retry(self, url: str, source_name: str) -> RawPayload:
        return await async_crawler_engine.fetch_with_retry(url, source_name)
