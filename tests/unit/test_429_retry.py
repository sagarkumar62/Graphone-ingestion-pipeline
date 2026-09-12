import pytest
import time
from src.llm.retry import retry_with_backoff
from src.core.exceptions import RateLimitException

@pytest.mark.asyncio
async def test_429_retry_bounded_attempts():
    attempts = 0

    async def mock_rate_limited_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RateLimitException("429 Rate Limit", provider_name="MockProvider")
        return "SUCCESS"

    start = time.time()
    res = await retry_with_backoff(
        mock_rate_limited_call,
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
        retryable_exceptions=(RateLimitException,)
    )

    assert res == "SUCCESS"
    assert attempts == 3
    assert (time.time() - start) >= 0.1
