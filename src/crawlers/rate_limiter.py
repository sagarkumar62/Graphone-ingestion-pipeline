import asyncio
import time
import random
from urllib.parse import urlparse
from src.core.config import settings
from src.core.logging import logger

class SourceRateLimiter:
    """
    Source-aware rate limiter and HTTP 429 Retry-After handler.
    Controls domain-level request rates and handles backoff with full jitter.
    """

    def __init__(self, requests_per_second: float = settings.RATE_LIMIT_PER_SECOND):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / max(0.1, requests_per_second)
        self._last_request_time: dict[str, float] = {}
        self._domain_cooldowns: dict[str, float] = {}

    def _get_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower() or "default"

    async def acquire(self, url: str) -> None:
        """
        Blocks until the domain rate limit interval and any active 429 cooldowns expire.
        """
        domain = self._get_domain(url)
        now = time.time()

        # Check if domain is in 429 cooldown
        cooldown_until = self._domain_cooldowns.get(domain, 0)
        if now < cooldown_until:
            wait_cooldown = cooldown_until - now
            logger.info(f"Domain '{domain}' in 429 cooldown. Waiting {wait_cooldown:.2f}s...")
            await asyncio.sleep(wait_cooldown)
            now = time.time()

        # Check domain inter-request delay
        last_time = self._last_request_time.get(domain, 0)
        elapsed = now - last_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            await asyncio.sleep(wait_time)

        self._last_request_time[domain] = time.time()

    def handle_429(self, url: str, retry_after_header: str | None = None) -> float:
        """
        Handles 429 Too Many Requests response by calculating cooldown delay.
        Parses Retry-After header if present, otherwise applies full jitter backoff.
        """
        domain = self._get_domain(url)
        cooldown_seconds = 10.0

        if retry_after_header:
            try:
                cooldown_seconds = float(retry_after_header)
            except ValueError:
                cooldown_seconds = 10.0

        if cooldown_seconds <= 0:
            cooldown_seconds = random.uniform(5.0, 15.0)

        self._domain_cooldowns[domain] = time.time() + cooldown_seconds
        logger.warning(f"HTTP 429 Rate Limit hit on domain '{domain}'. Applied Retry-After cooldown of {cooldown_seconds:.2f}s.")
        return cooldown_seconds

rate_limiter = SourceRateLimiter()
