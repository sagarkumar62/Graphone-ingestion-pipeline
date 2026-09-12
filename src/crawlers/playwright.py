from src.crawlers.base import BaseCrawler
from src.crawlers.http import AsyncHTTPCrawler
from src.core.models import RawPayload
from src.core.exceptions import CrawlerException, CrawlerTimeoutException, CrawlerBlockedException
from src.utils.time import format_iso8601
from src.core.logging import logger

class PlaywrightAsyncCrawler(BaseCrawler):
    """
    Headless browser crawler using Playwright Async for single-page applications (SPAs).
    Falls back gracefully to AsyncHTTPCrawler if Playwright binaries are unavailable.
    """

    async def fetch(self, url: str, source_name: str) -> RawPayload:
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.get_random_user_agent(),
                    viewport={"width": 1920, "height": 1080}
                )
                page = await context.new_page()
                
                logger.info("Playwright navigating to page...", extra={"url": url})
                response = await page.goto(url, wait_until="networkidle", timeout=int(self.timeout_seconds * 1000))
                
                if response and (response.status == 403 or response.status == 429):
                    await browser.close()
                    raise CrawlerBlockedException(f"Playwright received HTTP {response.status} for {url}")
                    
                content = await page.content()
                status = response.status if response else 200
                await browser.close()

                return RawPayload(
                    url=url,
                    source_name=source_name,
                    raw_content=content,
                    content_type="text/html",
                    fetched_at=format_iso8601(),
                    http_status=status
                )
        except Exception as e:
            logger.warning(f"Playwright browser execution failed ({e}). Falling back to AsyncHTTPCrawler...", extra={"url": url})
            fallback_crawler = AsyncHTTPCrawler(timeout_seconds=self.timeout_seconds, max_retries=1)
            return await fallback_crawler.fetch(url, source_name)
