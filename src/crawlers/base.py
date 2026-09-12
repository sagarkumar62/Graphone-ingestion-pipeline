from abc import ABC, abstractmethod
import asyncio
import random
from src.core.models import RawPayload
from src.core.exceptions import CrawlerException, CrawlerTimeoutException, CrawlerBlockedException
from src.core.config import settings
from src.core.logging import logger

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]

class BaseCrawler(ABC):
    """
    Abstract Base Crawler specifying the interface and retry/backoff strategy for web fetchers.
    """
    
    def __init__(self, timeout_seconds: float = settings.CRAWLER_TIMEOUT_SECONDS, max_retries: int = settings.MAX_CRAWLER_RETRIES):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        
    def get_random_user_agent(self) -> str:
        return random.choice(DEFAULT_USER_AGENTS)

    def calculate_backoff(self, attempt: int, base: float = 1.5, max_delay: float = 30.0) -> float:
        """Calculates Full Jitter Exponential Backoff delay."""
        delay = min(max_delay, base * (2 ** attempt))
        return delay * random.uniform(0.5, 1.5)

    @abstractmethod
    async def fetch(self, url: str, source_name: str) -> RawPayload:
        """
        Fetches web page content asynchronously.
        Returns a RawPayload object.
        Raises CrawlerException subclasses on failure.
        """
        pass

    async def fetch_with_retry(self, url: str, source_name: str) -> RawPayload:
        """
        Wraps fetch with bounded retries and exponential backoff.
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching URL (attempt {attempt + 1}/{self.max_retries})", extra={"url": url, "source": source_name})
                return await self.fetch(url, source_name)
            except (CrawlerTimeoutException, CrawlerBlockedException) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(f"Fetch failed ({e}). Retrying in {backoff:.2f}s...", extra={"url": url, "attempt": attempt + 1})
                    await asyncio.sleep(backoff)
            except Exception as e:
                logger.error(f"Unexpected crawler error: {e}", extra={"url": url})
                raise CrawlerException(f"Crawler failed on {url}: {e}") from e

        raise CrawlerException(f"Exhausted all {self.max_retries} retries for {url}: {last_exception}")
