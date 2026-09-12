import asyncio
import random
from src.core.exceptions import (
    RateLimitException, LLMAuthException, LLMBadRequestException, LLMNotFoundException
)
from src.core.logging import logger

async def retry_with_backoff(
    coro_func,
    max_retries: int = 3,
    base_delay: float = 1.5,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Executes an async function with Full Jitter Exponential Backoff retries and Retry-After inspection.
    Non-retryable exceptions (LLMAuthException, LLMBadRequestException, LLMNotFoundException) fail immediately.
    """
    non_retryable = (LLMAuthException, LLMBadRequestException, LLMNotFoundException)
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await coro_func()
        except non_retryable as nr_err:
            logger.error(f"Non-retryable LLM exception caught: {nr_err}")
            raise nr_err
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                if isinstance(e, RateLimitException) and getattr(e, "retry_after", None):
                    # Honor Retry-After subject to max_delay
                    delay = min(max_delay, float(e.retry_after))
                    logger.warning(f"RateLimit 429 with Retry-After header: waiting {delay:.2f}s (attempt {attempt + 1}/{max_retries})...")
                else:
                    # Full Jitter Exponential Backoff formula: min(max_delay, base_delay * 2^attempt) * uniform(0.5, 1.0)
                    exp_delay = min(max_delay, base_delay * (2 ** attempt))
                    delay = exp_delay * random.uniform(0.5, 1.0)
                    logger.warning(f"Operation failed ({e}). Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(delay)
            else:
                logger.warning(f"Retry exhaustion after {max_retries} attempts on operation: {e}")
                break

    raise last_exception
