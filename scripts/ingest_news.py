import sys
import os
import json
import asyncio
import argparse
from datetime import datetime, timezone
import httpx

sys.path.insert(0, os.path.abspath("."))

from src.storage.database import db_manager
from src.storage.repositories import EntityRepository, DLQRepository
from src.sources.news_sources import (
    HuggingFaceDailyPapersSource,
    TechCrunchAISource,
    MITTechReviewAISource,
    OpenAIBlogSource,
    HackerNewsAISource
)
from src.core.models import RecordType, RawPayload, CanonicalEntity, FreshnessStatus
from src.validators.schema_validator import validator
from src.pipeline.freshness import freshness_validator
from src.crawlers.extractor import html_extractor
from src.core.logging import logger

async def ingest_news(max_per_source: int = 50, concurrency: int = 5):
    logger.info(f"Starting AI News Ingestion (Target Max Per Source: {max_per_source}, Concurrency: {concurrency})...")
    await db_manager.init_db()

    repo = EntityRepository(db_manager)
    dlq = DLQRepository(db_manager)

    adapters = [
        ("HuggingFaceDailyPapers", HuggingFaceDailyPapersSource()),
        ("TechCrunchAI", TechCrunchAISource()),
        ("MITTechReviewAI", MITTechReviewAISource()),
        ("OpenAIBlog", OpenAIBlogSource()),
        ("HackerNewsAI", HackerNewsAISource()),
    ]

    now_utc = datetime.now(timezone.utc)
    total_discovered = 0
    total_saved = 0
    total_stale = 0
    total_unknown = 0
    total_schema_invalid = 0
    total_fetch_failed = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for source_name, adapter in adapters:
            logger.info(f"--- Processing Source: {source_name} ---")
            try:
                urls = await adapter.discover_urls(max_records=max_per_source)
            except Exception as e:
                logger.error(f"Error discovering URLs for {source_name}: {e}")
                urls = []

            logger.info(f"Discovered {len(urls)} URLs for {source_name}")
            total_discovered += len(urls)

            source_saved = 0
            source_stale = 0
            source_unknown = 0

            semaphore = asyncio.Semaphore(concurrency)

            async def process_news_url(url: str):
                nonlocal source_saved, source_stale, source_unknown, total_saved, total_stale, total_unknown, total_schema_invalid, total_fetch_failed
                async with semaphore:
                    fetch_status = 200
                    raw_html = ""
                    try:
                        res = await client.get(url)
                        fetch_status = res.status_code
                        if res.status_code == 200:
                            raw_html = res.text
                        else:
                            total_fetch_failed += 1
                            logger.warning(f"Fetch failed for news URL {url} with status {res.status_code}")
                    except Exception as e:
                        total_fetch_failed += 1
                        logger.warning(f"Error fetching news URL {url}: {e}")
                        fetch_status = 500

                    payload = RawPayload(
                        source_name=source_name,
                        url=url,
                        raw_content=raw_html,
                        content_type="text/html",
                        http_status=fetch_status,
                        fetched_at=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    )

                    try:
                        parsed_dict = adapter.parse_raw_payload(payload)
                    except Exception as e:
                        logger.error(f"Error parsing raw payload for {url}: {e}")
                        return

                    pub_date = parsed_dict.get("content", {}).get("published_date")
                    f_res = freshness_validator.evaluate_freshness(pub_date, reference_now=now_utc)

                    if f_res.status == FreshnessStatus.STALE:
                        source_stale += 1
                        total_stale += 1
                        logger.info(f"Rejected STALE news article ({f_res.age_hours:.1f}h old): {url}")
                        return
                    elif f_res.status == FreshnessStatus.UNKNOWN:
                        source_unknown += 1
                        total_unknown += 1
                        logger.info(f"Rejected UNKNOWN_DATE news article: {url}")
                        return

                    # Schema validation
                    is_valid, validation_errors = validator.validate(parsed_dict, RecordType.NEWS)
                    if not is_valid:
                        total_schema_invalid += 1
                        logger.warning(f"Schema validation failed for news {url}: {validation_errors}")
                        return

                    entity = CanonicalEntity(**parsed_dict)
                    success = await repo.save_canonical_entity(entity)
                    if success:
                        source_saved += 1
                        total_saved += 1
                        logger.info(f"Successfully saved 24h FRESH news [{source_saved}]: {entity.content.get('title')}")

            tasks = [process_news_url(url) for url in urls]
            await asyncio.gather(*tasks)
            logger.info(f"Completed {source_name}: Saved={source_saved}, Stale={source_stale}, Unknown={source_unknown}")

    logger.info(f"AI News Ingestion Complete!")
    logger.info(f"Summary: Total Discovered={total_discovered}, Fresh Saved={total_saved}, Stale Rejected={total_stale}, Unknown Rejected={total_unknown}, Schema Invalid={total_schema_invalid}, Fetch Failures={total_fetch_failed}")
    return total_saved

def main():
    parser = argparse.ArgumentParser(description="AI News Ingestion Runner")
    parser.add_argument("--slice", action="store_true", help="Run vertical slice (1-10 articles per source)")
    parser.add_argument("--bulk", action="store_true", help="Run bulk ingestion across news sources")
    parser.add_argument("--limit", type=int, default=50, help="Custom per-source record limit")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrency level")

    args = parser.parse_args()

    max_per_source = 50
    if args.slice:
        max_per_source = 5
    elif args.limit:
        max_per_source = args.limit
    elif args.bulk:
        max_per_source = 50

    asyncio.run(ingest_news(max_per_source=max_per_source, concurrency=args.concurrency))

if __name__ == "__main__":
    main()
