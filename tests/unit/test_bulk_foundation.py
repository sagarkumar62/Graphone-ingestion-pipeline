import pytest
import asyncio
from src.core.config import settings
from src.crawlers.rate_limiter import SourceRateLimiter
from src.storage.raw_store import raw_store
from src.storage.checkpoint import checkpoint_engine, CheckpointState
from src.storage.database import db_manager
from src.pipeline.batch_processor import batch_processor, BatchProcessor
from src.sources.arxiv import ArXivSourceAdapter

@pytest.mark.asyncio
async def test_arxiv_discovery_pagination():
    adapter = ArXivSourceAdapter()
    urls_10 = await adapter.discover_urls(max_records=10, start_offset=0)
    assert len(urls_10) == 10
    assert all("arxiv.org" in url for url in urls_10)

@pytest.mark.asyncio
async def test_429_retry_after_parsing():
    limiter = SourceRateLimiter()
    delay = limiter.handle_429("https://arxiv.org/abs/123", retry_after_header="5")
    assert delay == 5.0

@pytest.mark.asyncio
async def test_raw_payload_staging_and_hashing():
    await db_manager.init_db()
    content = "<html><body>Test raw payload</body></html>"
    url = "https://arxiv.org/abs/test_raw_123"
    
    hash_val, file_path = await raw_store.save_raw_payload(url, "ArXiv", content)
    assert hash_val is not None
    assert len(hash_val) == 64
    assert await raw_store.is_content_unchanged(url, hash_val)

@pytest.mark.asyncio
async def test_checkpoint_state_tracking():
    await db_manager.init_db()
    url = "https://arxiv.org/abs/test_checkpoint_123"
    
    await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.DISCOVERED)
    assert await checkpoint_engine.get_state(url) == CheckpointState.DISCOVERED
    
    await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.STORED)
    assert await checkpoint_engine.get_state(url) == CheckpointState.STORED

@pytest.mark.asyncio
async def test_failure_isolation_batch_continues():
    await db_manager.init_db()
    processor = BatchProcessor(concurrency=2)
    
    # Run bulk processing on 5 records where some may fail
    metrics = await processor.process_source_bulk("arxiv", max_records=5)
    assert metrics.discovered == 5
    assert (metrics.stored + metrics.duplicates + metrics.failed) == 5

@pytest.mark.asyncio
async def test_changed_content_reprocessing():
    import uuid
    await db_manager.init_db()
    url = f"https://arxiv.org/abs/test_changed_content_{uuid.uuid4()}"
    content_v1 = "<html><body>Version 1 Content</body></html>"
    content_v2 = "<html><body>Version 2 Content Updated</body></html>"

    # Save V1 content and mark STORED
    hash_v1, _ = await raw_store.save_raw_payload(url, "ArXiv", content_v1)
    await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.STORED)

    assert await raw_store.is_content_unchanged(url, hash_v1) is True

    # Compute hash of V2 content (changed)
    hash_v2 = raw_store.compute_content_hash(content_v2)
    assert hash_v1 != hash_v2
    # Verify V2 is NOT treated as duplicate (content changed)
    assert await raw_store.is_content_unchanged(url, hash_v2) is False

    # Save V2 payload
    await raw_store.save_raw_payload(url, "ArXiv", content_v2)
    assert await raw_store.is_content_unchanged(url, hash_v2) is True

@pytest.mark.asyncio
async def test_checkpoint_resume_semantics():
    import uuid
    await db_manager.init_db()
    run_id = str(uuid.uuid4())[:8]
    
    # 6 STORED, 2 FAILED, 2 PROCESSING
    for i in range(1, 7):
        url = f"https://arxiv.org/abs/test_resume_{run_id}_{i}"
        await raw_store.save_raw_payload(url, "ArXiv", f"Content {i}")
        await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.STORED)
        
    for i in range(7, 9):
        url = f"https://arxiv.org/abs/test_resume_{run_id}_{i}"
        await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.FAILED, error="429 Rate Limit")
        
    for i in range(9, 11):
        url = f"https://arxiv.org/abs/test_resume_{run_id}_{i}"
        await checkpoint_engine.update_state(url, "ArXiv", "RESEARCH_PAPER", CheckpointState.PROCESSING)

    # Verify state lookup for resume decisions
    for i in range(1, 7):
        assert await checkpoint_engine.get_state(f"https://arxiv.org/abs/test_resume_{run_id}_{i}") == CheckpointState.STORED
    for i in range(7, 9):
        assert await checkpoint_engine.get_state(f"https://arxiv.org/abs/test_resume_{run_id}_{i}") == CheckpointState.FAILED
    for i in range(9, 11):
        assert await checkpoint_engine.get_state(f"https://arxiv.org/abs/test_resume_{run_id}_{i}") == CheckpointState.PROCESSING

