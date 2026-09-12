import pytest
from src.pipeline.batch_processor import BatchProcessor
from src.storage.database import db_manager
from src.storage.repositories import EntityRepository

@pytest.mark.asyncio
async def test_10_record_bulk_batch():
    await db_manager.init_db()
    processor = BatchProcessor(concurrency=3)
    
    metrics = await processor.process_source_bulk("arxiv", max_records=10)
    assert metrics.discovered == 10
    assert (metrics.stored + metrics.duplicates + metrics.failed) == 10

@pytest.mark.asyncio
async def test_duplicate_reexecution_deduplication():
    await db_manager.init_db()
    processor = BatchProcessor(concurrency=3)
    
    # First Run
    m1 = await processor.process_source_bulk("arxiv", max_records=5, start_offset=100)
    
    # Second Run on exact same offset -> Duplicates detected
    m2 = await processor.process_source_bulk("arxiv", max_records=5, start_offset=100)
    assert m2.duplicates == 5
    assert m2.stored == 0
