import asyncio
import random
import httpx
from urllib.parse import urlparse

from src.core.config import settings
from src.core.models import RawPayload
from src.core.exceptions import (
    CrawlerException,
    CrawlerTimeoutException,
    CrawlerBlockedException,
    CrawlerAntiBotException,
    CrawlerRateLimitException
)
from src.crawlers.base import BaseCrawler
from src.crawlers.rate_limiter import rate_limiter, SourceRateLimiter
from src.utils.time import format_iso8601
from src.core.logging import logger

class AsyncCrawlerEngine(BaseCrawler):
    """
    High-throughput asynchronous web crawling engine.
    Implements:
    - Bounded global concurrency via asyncio.Semaphore
    - Per-source concurrency pools via asyncio.Semaphore
    - Domain/Source-level rate limiting
    - Full Jitter exponential backoff
    - HTTP 429 Retry-After handling
    - Precise HTTP status & anti-bot classification
    - Zero synthetic fallback payload generation
    """

    def __init__(
        self,
        global_concurrency: int = settings.CRAWL_CONCURRENCY,
        per_source_concurrency: int = settings.PER_SOURCE_CONCURRENCY,
        timeout_seconds: float = settings.CRAWLER_TIMEOUT_SECONDS,
        max_retries: int = settings.MAX_CRAWLER_RETRIES,
        rate_limiter_inst: SourceRateLimiter | None = None
    ):
        super().__init__(timeout_seconds=timeout_seconds, max_retries=max_retries)
        self.global_semaphore = asyncio.Semaphore(global_concurrency)
        self.per_source_concurrency_limit = per_source_concurrency
        self.per_source_semaphores: dict[str, asyncio.Semaphore] = {}
        self.rate_limiter = rate_limiter_inst or rate_limiter

    def _get_source_semaphore(self, source_name: str) -> asyncio.Semaphore:
        clean_name = source_name.lower()
        if clean_name not in self.per_source_semaphores:
            self.per_source_semaphores[clean_name] = asyncio.Semaphore(self.per_source_concurrency_limit)
        return self.per_source_semaphores[clean_name]

    async def fetch(self, url: str, source_name: str) -> RawPayload:
        """
        Executes single HTTP request with concurrency controls, rate limiting, and response classification.
        Does NOT generate synthetic HTML on failure.
        """
        source_sem = self._get_source_semaphore(source_name)

        async with self.global_semaphore:
            async with source_sem:
                await self.rate_limiter.acquire(url)
                
                headers = {
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }

                try:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                        response = await client.get(url, headers=headers)
                        status = response.status_code

                        # Status Code Classification
                        if status == 403:
                            body_lower = response.text.lower()
                            if any(bot_indicator in body_lower for bot_indicator in ["cloudflare", "datadome", "captcha", "just a moment", "cf-ray", "access denied"]):
                                logger.warning(f"Anti-Bot protection detected on {url} (HTTP 403)")
                                raise CrawlerAntiBotException(f"Anti-bot blocked access to {url}")
                            raise CrawlerBlockedException(f"HTTP 403 Access Blocked on {url}")

                        if status == 429:
                            retry_after = response.headers.get("Retry-After")
                            cooldown = self.rate_limiter.handle_429(url, retry_after)
                            raise CrawlerRateLimitException(f"HTTP 429 Rate Limit on {url}", retry_after=cooldown)

                        if status in (408, 500, 502, 503, 504):
                            raise CrawlerTimeoutException(f"HTTP {status} Server/Timeout Error on {url}")

                        if status >= 400:
                            raise CrawlerException(f"HTTP {status} Permanent Client Error on {url}")

                        content_type = response.headers.get("content-type", "text/html")
                        return RawPayload(
                            url=url,
                            source_name=source_name,
                            raw_content=response.text,
                            content_type=content_type,
                            fetched_at=format_iso8601(),
                            http_status=status
                        )
                except httpx.TimeoutException as e:
                    raise CrawlerTimeoutException(f"Network timeout fetching {url}: {e}") from e
                except httpx.NetworkError as e:
                    raise CrawlerTimeoutException(f"Network connection failure fetching {url}: {e}") from e

    async def fetch_with_retry(self, url: str, source_name: str) -> RawPayload:
        """
        Executes request with bounded retries and full-jitter exponential backoff.
        Only retries transient errors (408, 429, 5xx, timeouts, network failures).
        Does NOT retry permanent client errors (400, 401, 404) or Anti-Bot blocks (403).
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return await self.fetch(url, source_name)
            except (CrawlerAntiBotException, CrawlerBlockedException) as e:
                # Anti-bot blocks are non-retryable without proxy/bypass
                logger.error(f"Non-retryable anti-bot failure on {url}: {e}")
                raise e
            except CrawlerRateLimitException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_sec = max(e.retry_after, self.calculate_backoff(attempt))
                    logger.warning(f"HTTP 429 on {url}. Waiting {wait_sec:.2f}s before retry (attempt {attempt + 1}).")
                    await asyncio.sleep(wait_sec)
            except CrawlerTimeoutException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(f"Transient error on {url} ({e}). Retrying in {backoff:.2f}s...")
                    await asyncio.sleep(backoff)
            except CrawlerException as e:
                # Permanent errors (e.g. 404, 400) should fail immediately
                logger.error(f"Permanent crawler failure on {url}: {e}")
                raise e
            except Exception as e:
                logger.error(f"Unexpected error crawling {url}: {e}")
                raise CrawlerException(f"Crawler failed on {url}: {e}") from e

        raise CrawlerException(f"Exhausted all {self.max_retries} retries for {url}: {last_exception}")

async_crawler_engine = AsyncCrawlerEngine()
