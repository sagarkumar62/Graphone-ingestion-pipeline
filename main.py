import asyncio
import json
import os
import sys
from src.core.config import settings
from src.storage.database import db_manager
from src.pipeline.batch_processor import batch_processor
from src.storage.repositories import EntityRepository
from src.core.logging import logger

async def run_bulk_ingestion_demo():
    """
    Executes Phase 2A Production Bulk Ingestion Foundation Demonstration.
    Demonstrates configurable MAX_RECORDS execution (e.g. 10 records vs 100 records)
    with source adapters, rate limiting, raw payload staging, checkpointing,
    and failure isolation.
    """
    max_records = settings.MAX_RECORDS
    start_offset = settings.START_OFFSET
    
    print("=" * 80)
    print("GRAPHONE / FRONTIERATLAS")
    print(f"PHASE 2A BULK EXTRACTION FOUNDATION (MAX_RECORDS={max_records}, START_OFFSET={start_offset})")
    print("=" * 80)

    # Initialize Database Schemas
    await db_manager.init_db()
    repo = EntityRepository()

    # Query initial database row count
    initial_rows = len(await repo.get_all_records("research_papers"))
    print(f"\n[+] Database State BEFORE Bulk Run (Table 'research_papers'): {initial_rows} rows")

    # Run Bulk Ingestion for ArXiv source
    print(f"\n[+] Starting Bulk Processing for ArXiv Source (Configured MAX_RECORDS={max_records}, OFFSET={start_offset})...\n")
    metrics = await batch_processor.process_source_bulk("arxiv", max_records=max_records, start_offset=start_offset)

    # Query database state after run
    final_rows = len(await repo.get_all_records("research_papers"))
    newly_stored = final_rows - initial_rows

    # Print Summary Report
    print("\n" + "=" * 80)
    print("PHASE 2A BULK INGESTION SUMMARY REPORT")
    print("=" * 80)
    print(f"Source Adapter:       ArXiv (cs.AI Bulk Query)")
    print(f"MAX_RECORDS Config:   {max_records}")
    print(f"START_OFFSET Config:  {start_offset}")
    print(f"Crawl Concurrency:    {settings.CRAWL_CONCURRENCY} workers")
    print(f"Elapsed Time:         {metrics.to_dict()['elapsed_seconds']} seconds")
    print(f"Throughput:           {metrics.to_dict()['throughput_records_per_sec']} records/sec")
    print("-" * 80)
    print(f"Discovered:           {metrics.discovered}")
    print(f"Fetched:              {metrics.fetched}")
    print(f"Processed:            {metrics.processed}")
    print(f"Stored (New):         {metrics.stored}")
    print(f"Duplicates (Skipped): {metrics.duplicates}")
    print(f"Rejected (Validation):{metrics.rejected_validation}")
    print(f"Failed (DLQ):         {metrics.failed}")
    print("-" * 80)
    print(f"DB Rows Before:       {initial_rows}")
    print(f"DB Rows After:        {final_rows} (+{newly_stored} newly stored)")
    print("=" * 80)

    # Sample Persisted Record
    records = await repo.get_all_records("research_papers")
    if records:
        print("\n[+] Sample Persisted Canonical Research Paper Record in Database:")
        sample = records[-1]
        print(json.dumps(sample, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(run_bulk_ingestion_demo())
