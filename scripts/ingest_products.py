import sys
import os
import json
import asyncio
import argparse
import httpx
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))

from src.storage.database import db_manager
from src.storage.repositories import EntityRepository
from src.sources.product_sources import GitHubRepositoriesProductSource
from src.core.models import RecordType, RawPayload, CanonicalEntity
from src.validators.schema_validator import validator
from src.core.logging import logger

async def ingest_products(limit: int = 1050, concurrency: int = 10):
    logger.info(f"Starting Products Bulk Ingestion (Target Limit: {limit}, Concurrency: {concurrency})...")
    await db_manager.init_db()

    repo = EntityRepository(db_manager)
    adapter = GitHubRepositoriesProductSource()

    discovered_urls = await adapter.discover_urls(max_records=limit)
    logger.info(f"Discovered {len(discovered_urls)} product URLs for processing.")

    saved_count = 0
    skipped_count = 0
    errors_count = 0

    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)

    async with httpx.AsyncClient(limits=limits, timeout=12.0) as client:
        async def process_url(url: str):
            nonlocal saved_count, skipped_count, errors_count
            async with semaphore:
                try:
                    raw_data = await adapter.fetch_repo_data(url, client=client)
                    if not raw_data:
                        skipped_count += 1
                        return

                    raw_payload = RawPayload(
                        source_name=adapter.source_name,
                        url=url,
                        raw_content=json.dumps(raw_data),
                        content_type="application/json",
                        fetched_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    )

                    canonical_dict = adapter.parse_raw_payload(raw_payload)

                    # Schema validation
                    is_valid, validation_errors = validator.validate(canonical_dict, RecordType.PRODUCT)
                    if not is_valid:
                        logger.warning(f"Schema validation failed for product {url}: {validation_errors}")
                        skipped_count += 1
                        return

                    # Parse as Pydantic model
                    entity = CanonicalEntity(**canonical_dict)

                    # Repository Save (UPSERT)
                    success = await repo.save_canonical_entity(entity)
                    if success:
                        saved_count += 1
                        if saved_count % 100 == 0 or saved_count == limit or saved_count <= 10:
                            logger.info(f"Ingested [{saved_count}/{limit}] products total (Latest: {entity.content.get('productName')})")
                    else:
                        skipped_count += 1

                except Exception as e:
                    errors_count += 1
                    logger.error(f"Error processing product {url}: {e}")

        # Process in batch chunks
        chunk_size = 50
        for i in range(0, len(discovered_urls), chunk_size):
            chunk = discovered_urls[i:i + chunk_size]
            tasks = [process_url(url) for url in chunk]
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.1)

    logger.info(f"Products Bulk Ingestion Complete. Total Saved: {saved_count}, Skipped: {skipped_count}, Errors: {errors_count}")
    return saved_count

def main():
    parser = argparse.ArgumentParser(description="Products Bulk Ingestion Runner")
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

    asyncio.run(ingest_products(limit=limit, concurrency=args.concurrency))

if __name__ == "__main__":
    main()
