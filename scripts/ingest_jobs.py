import sys
import os
import json
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))

from src.storage.database import db_manager
from src.storage.repositories import EntityRepository
from src.sources.job_sources import (
    ArbeitnowJobSource,
    HNWhoIsHiringJobSource,
    RemoteOKAISource,
    JobicyAISource,
    WeWorkRemotelyAISource
)
from src.core.models import RecordType, RawPayload, CanonicalEntity
from src.validators.schema_validator import validator
from src.core.logging import logger

async def ingest_jobs(limit: int = 1050, concurrency: int = 10):
    logger.info(f"Starting Jobs Bulk Ingestion (Target Limit: {limit}, Concurrency: {concurrency})...")
    await db_manager.init_db()

    repo = EntityRepository(db_manager)

    adapters = [
        ArbeitnowJobSource(),
        HNWhoIsHiringJobSource(),
        RemoteOKAISource(),
        JobicyAISource(),
        WeWorkRemotelyAISource()
    ]

    url_to_adapter = {}
    discovered_urls = []

    target_per_adapter = limit if limit <= 50 else max(600, limit // 2)
    for adapter in adapters:
        try:
            urls = await adapter.discover_urls(max_records=target_per_adapter)
            for u in urls:
                if u not in url_to_adapter:
                    url_to_adapter[u] = adapter
                    discovered_urls.append(u)
            if len(discovered_urls) >= limit + 100:
                break
        except Exception as e:
            logger.warning(f"Error discovering URLs from {adapter.source_name}: {e}")

    discovered_urls = discovered_urls[:limit]
    logger.info(f"Discovered {len(discovered_urls)} unique job URLs for processing.")

    saved_count = 0
    skipped_count = 0
    errors_count = 0

    semaphore = asyncio.Semaphore(concurrency)

    async def process_url(url: str):
        nonlocal saved_count, skipped_count, errors_count
        async with semaphore:
            try:
                adapter = url_to_adapter[url]
                raw_payload = RawPayload(
                    source_name=adapter.source_name,
                    url=url,
                    raw_content="{}",
                    content_type="application/json",
                    fetched_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                )

                canonical_dict = adapter.parse_raw_payload(raw_payload)

                # Schema validation
                is_valid, validation_errors = validator.validate(canonical_dict, RecordType.JOB)
                if not is_valid:
                    logger.warning(f"Schema validation failed for job {url}: {validation_errors}")
                    skipped_count += 1
                    return

                # Parse as Pydantic model
                entity = CanonicalEntity(**canonical_dict)

                # Repository Save (UPSERT)
                success = await repo.save_canonical_entity(entity)
                if success:
                    saved_count += 1
                    if saved_count % 100 == 0 or saved_count == limit or saved_count <= 10:
                        logger.info(f"Ingested [{saved_count}/{limit}] jobs total (Latest: {entity.content.get('jobTitle')} at {entity.content.get('company')})")
                else:
                    skipped_count += 1

            except Exception as e:
                errors_count += 1
                logger.error(f"Error processing job {url}: {e}")

    chunk_size = 50
    for i in range(0, len(discovered_urls), chunk_size):
        chunk = discovered_urls[i:i + chunk_size]
        tasks = [process_url(url) for url in chunk]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.05)

    logger.info(f"Jobs Bulk Ingestion Complete. Total Saved: {saved_count}, Skipped: {skipped_count}, Errors: {errors_count}")
    return saved_count

def main():
    parser = argparse.ArgumentParser(description="Jobs Bulk Ingestion Runner")
    parser.add_argument("--slice", action="store_true", help="Run 10-record vertical slice")
    parser.add_argument("--bulk", action="store_true", help="Run bulk ingestion target >= 1050 records")
    parser.add_argument("--limit", type=int, default=None, help="Custom record limit")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrency level")

    args = parser.parse_args()

    limit = 1050
    if args.bulk:
        limit = 1050
    elif args.limit:
        limit = args.limit
    elif args.slice:
        limit = 10

    asyncio.run(ingest_jobs(limit=limit, concurrency=args.concurrency))

if __name__ == "__main__":
    main()
