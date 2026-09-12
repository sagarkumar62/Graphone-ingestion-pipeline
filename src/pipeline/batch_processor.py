import asyncio
import time
from typing import Any
from src.core.config import settings
from src.core.models import RecordType, PipelineStatusCode
from src.sources.registry import registry as source_registry
from src.crawlers.rate_limiter import rate_limiter
from src.storage.raw_store import raw_store
from src.storage.checkpoint import checkpoint_engine, CheckpointState
from src.pipeline.processor import processor
from src.core.logging import logger

class BatchMetrics:
    """Tracks observability metrics for bulk ingestion execution."""

    def __init__(self):
        self.start_time = time.time()
        self.discovered = 0
        self.fetched = 0
        self.processed = 0
        self.stored = 0
        self.duplicates = 0
        self.rejected_freshness = 0
        self.rejected_validation = 0
        self.failed = 0
        self.retry_count = 0
        self.rate_limit_429_count = 0

    def to_dict(self) -> dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            "elapsed_seconds": round(elapsed, 2),
            "throughput_records_per_sec": round(self.stored / elapsed, 2) if elapsed > 0 else 0.0,
            "discovered": self.discovered,
            "fetched": self.fetched,
            "processed": self.processed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "rejected_freshness": self.rejected_freshness,
            "rejected_validation": self.rejected_validation,
            "failed": self.failed,
            "rate_limit_429_count": self.rate_limit_429_count
        }

class BatchProcessor:
    """
    Production Bulk Batch Processor.
    Executes source discovery, bounded worker pools, rate-limited fetching, raw payload staging,
    checkpointing, deterministic/LLM extraction, schema validation, entity resolution, enrichment, and storage.
    Enforces failure isolation: one bad record failure never stops the batch.
    """

    def __init__(self, concurrency: int = settings.CRAWL_CONCURRENCY):
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

    async def process_source_bulk(
        self,
        source_name: str,
        max_records: int = settings.MAX_RECORDS,
        start_offset: int = settings.START_OFFSET
    ) -> BatchMetrics:
        adapter = source_registry.get(source_name)
        if not adapter:
            raise ValueError(f"Source adapter '{source_name}' is not registered.")

        metrics = BatchMetrics()
        logger.info(f"Starting bulk extraction for source '{source_name}' (max_records={max_records}, offset={start_offset}, concurrency={self.concurrency})")

        # Step 1: Discover candidate URLs from source adapter
        urls = await adapter.discover_urls(max_records=max_records, start_offset=start_offset)
        metrics.discovered = len(urls)

        if not urls:
            logger.warning(f"No URLs discovered for source '{source_name}'")
            return metrics

        # Queue for discovery and worker pool
        work_queue: asyncio.Queue[str] = asyncio.Queue()
        for url in urls:
            await work_queue.put(url)

        async def worker_task():
            while not work_queue.empty():
                try:
                    url = work_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                async with self.semaphore:
                    await self._process_single_bulk_item(url, adapter, metrics)
                work_queue.task_done()

        # Run worker tasks bounded by concurrency
        workers = [asyncio.create_task(worker_task()) for _ in range(min(self.concurrency, len(urls)))]
        await asyncio.gather(*workers)

        logger.info(f"Completed bulk extraction for '{source_name}'", extra=metrics.to_dict())
        return metrics

    async def _process_single_bulk_item(self, url: str, adapter: Any, metrics: BatchMetrics) -> None:
        source_name = adapter.source_name
        record_type = adapter.record_type

        try:
            current_state = await checkpoint_engine.get_state(url)
            latest_hash = await raw_store.get_latest_content_hash(url)

            # CASE A Check (Pre-fetch optimization): If URL was previously STORED and we have raw payload staged
            # and force refetch is not requested, it is known to be a stored duplicate (CASE A).
            if current_state == CheckpointState.STORED and latest_hash is not None and not getattr(settings, "FORCE_REFETCH", False):
                logger.info(f"Checkpoint state for {url} is STORED and content hash ({latest_hash[:8]}) exists. Skipping duplicate (CASE A).")
                metrics.duplicates += 1
                return

            # CASE C, D, E or CASE B: Proceed to register DISCOVERED and acquire rate limit
            await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.DISCOVERED)

            # Step A: Rate Limit Acquire
            await rate_limiter.acquire(url)
            await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.FETCHING)

            # Step B: Live Fetch via Crawler
            raw_payload = await processor.http_crawler.fetch_with_retry(url, source_name)
            metrics.fetched += 1
            await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.FETCHED)

            # Compute content hash
            content_hash = raw_store.compute_content_hash(raw_payload.raw_content)

            # Check if SAME URL + SAME CONTENT_HASH (CASE A after fetch) vs CHANGED CONTENT_HASH (CASE B)
            is_unchanged = await raw_store.is_content_unchanged(url, content_hash)
            
            # Step C: Save Raw Payload
            await raw_store.save_raw_payload(
                source_url=url,
                source_name=source_name,
                content=raw_payload.raw_content,
                content_type=raw_payload.content_type,
                http_status=raw_payload.http_status
            )

            # If SAME URL + SAME CONTENT_HASH and already STORED -> CASE A Duplicate!
            if is_unchanged and current_state == CheckpointState.STORED:
                metrics.duplicates += 1
                logger.info(f"SAME URL + SAME CONTENT_HASH ({content_hash[:8]}) previously STORED. Skipping processing (CASE A).")
                return

            # If CHANGED CONTENT_HASH (CASE B):
            if current_state == CheckpointState.STORED and not is_unchanged:
                logger.info(f"SAME URL {url} with CHANGED CONTENT_HASH ({content_hash[:8]}). Reprocessing updated record (CASE B).")

            # Step D: Process record through extraction, resolution, enrichment, and storage
            await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.PROCESSING)
            
            status, entity, meta = await processor.process_record(
                source_url=url,
                source_name=source_name,
                record_type=record_type,
                use_browser=False
            )

            metrics.processed += 1

            if status == PipelineStatusCode.NEW_RECORD_STORED:
                metrics.stored += 1
                await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.STORED)
            elif status == PipelineStatusCode.DUPLICATE_ALREADY_PROCESSED:
                metrics.duplicates += 1
                await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.STORED)
            elif status == PipelineStatusCode.FRESHNESS_REJECTED:
                metrics.rejected_freshness += 1
                await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.FAILED, error="FRESHNESS_REJECTED")
            elif status in {PipelineStatusCode.VALIDATION_FAILED, PipelineStatusCode.EXTRACTION_FAILED}:
                metrics.rejected_validation += 1
                await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.DLQ, error=status.value)
            else:
                metrics.failed += 1
                await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.FAILED, error=status.value)

        except Exception as e:
            # Failure Isolation: Catches unhandled errors per record so the batch continues!
            metrics.failed += 1
            logger.error(f"Failure isolation caught record error on {url}: {e}")
            await checkpoint_engine.update_state(url, source_name, record_type.value, CheckpointState.DLQ, error=str(e))

batch_processor = BatchProcessor()
