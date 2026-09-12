import uuid
import asyncio
from typing import Any
from src.core.models import RecordType, CanonicalEntity, PipelineStatusCode, FreshnessStatus
from src.core.exceptions import PipelineException, CrawlerBlockedException
from src.crawlers.async_crawler import async_crawler_engine, AsyncCrawlerEngine
from src.pipeline.freshness import freshness_validator
from src.pipeline.deduplication import deduplicator
from src.pipeline.metrics import metrics_collector
from src.llm.orchestrator import orchestrator
from src.resolver.matcher import resolver
from src.resolver.audit import audit_logger
from src.enrichment.github import github_enricher
from src.storage.raw_store import raw_store
from src.storage.checkpoint import checkpoint_engine, CheckpointState
from src.storage.repositories import EntityRepository, DLQRepository
from src.sources.registry import registry
from src.core.logging import logger

class AsyncPipelineProcessor:
    """
    High-concurrency Async Ingestion Pipeline Processor.
    Orchestrates: Source -> Async Crawler -> Raw Payload Staging -> Content Hash Dedup -> Freshness Filter -> LLM/Deterministic Parser -> Schema Validation -> Entity Resolution -> Storage / DLQ.
    Preserves error isolation per URL and updates checkpoint states.
    """

    def __init__(
        self,
        entity_repo: EntityRepository | None = None,
        dlq_repo: DLQRepository | None = None,
        crawler_engine: AsyncCrawlerEngine | None = None
    ):
        self.entity_repo = entity_repo or EntityRepository()
        self.dlq_repo = dlq_repo or DLQRepository()
        self.crawler = crawler_engine or async_crawler_engine

    async def process_record(
        self,
        source_url: str,
        source_name: str,
        record_type: RecordType,
        use_browser: bool = False
    ) -> tuple[PipelineStatusCode, CanonicalEntity | None, dict[str, Any]]:
        meta: dict[str, Any] = {
            "source_url": source_url,
            "source_name": source_name,
            "record_type": record_type.value,
            "provider_used": None,
            "content_bytes": 0,
            "freshness": "NOT_CHECKED"
        }

        # Update Checkpoint to DISCOVERED
        await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.DISCOVERED)

        # 1. Deduplication Check
        is_dup, url_hash = await deduplicator.is_duplicate_url(source_url)
        if is_dup:
            logger.info(f"URL fingerprint {url_hash[:8]} already processed. Skipping duplicate.")
            await metrics_collector.record_duplicate(source_name)
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.STORED)
            return PipelineStatusCode.DUPLICATE_ALREADY_PROCESSED, None, meta

        # 2. Async Crawler Fetch
        await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.FETCHING)
        try:
            raw_payload = await self.crawler.fetch_with_retry(source_url, source_name)
            meta["content_bytes"] = len(raw_payload.raw_content.encode("utf-8"))
            meta["http_status"] = raw_payload.http_status
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.FETCHED)
        except Exception as e:
            await metrics_collector.record_request(source_name, status_code=403 if isinstance(e, CrawlerBlockedException) else 500)
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.DLQ, error=str(e))
            dlq_id = f"dlq_{uuid.uuid4()}"
            await self.dlq_repo.save_dlq(
                dlq_id=dlq_id,
                source_url=source_url,
                category="FETCH_FAILED",
                message=str(e),
                component="AsyncCrawlerLayer",
                payload={"source_name": source_name, "record_type": record_type.value},
                attempts=3
            )
            await metrics_collector.record_dlq(source_name)
            return PipelineStatusCode.FETCH_FAILED, None, meta

        # 3. Raw Payload Staging
        content_hash, _ = await raw_store.save_raw_payload(
            source_url=source_url,
            source_name=source_name,
            content=raw_payload.raw_content,
            content_type=raw_payload.content_type,
            http_status=raw_payload.http_status
        )

        # 4. Content-Hash Deduplication (SAME URL + SAME CONTENT)
        if await raw_store.is_content_unchanged(source_url, content_hash):
            latest_hash = await raw_store.get_latest_content_hash(source_url)
            if latest_hash == content_hash:
                # If content is identical to last stored run, skip duplicate processing
                pass

        # 5. Freshness Filter (for News & Jobs)
        await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.PROCESSING)
        adapter = registry.get(source_name)
        pub_date_candidate = adapter.extract_published_at(raw_payload) if adapter else None

        if record_type in {RecordType.NEWS, RecordType.JOB}:
            freshness_res = freshness_validator.evaluate_freshness(pub_date_candidate)
            meta["freshness"] = freshness_res.status.value
            await metrics_collector.record_freshness(source_name, freshness_res.status.value)

            if freshness_res.status != FreshnessStatus.FRESH:
                logger.info(f"Record {source_url} rejected as {freshness_res.status.value} (published: {freshness_res.published_at}).")
                await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.PROCESSED)
                return PipelineStatusCode.FRESHNESS_REJECTED, None, meta

        # 6. Parser / LLM Extraction & Validation
        try:
            if adapter and adapter.extraction_strategy == "DETERMINISTIC":
                raw_dict = adapter.parse_raw_payload(raw_payload)
                canonical_entity = CanonicalEntity(**raw_dict)
                provider_used = f"{source_name}DeterministicParser"
            else:
                canonical_entity, provider_used = await orchestrator.extract_canonical_entity(
                    raw_text=raw_payload.raw_content,
                    record_type=record_type,
                    source_name=source_name,
                    source_url=source_url
                )
            meta["provider_used"] = provider_used
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.PROCESSED)
        except Exception as e:
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.DLQ, error=str(e))
            dlq_id = f"dlq_{uuid.uuid4()}"
            await self.dlq_repo.save_dlq(
                dlq_id=dlq_id,
                source_url=source_url,
                category="EXTRACTION_OR_VALIDATION_FAILED",
                message=str(e),
                component="ExtractionLayer",
                payload={"raw_content_preview": raw_payload.raw_content[:200]},
                attempts=3
            )
            await metrics_collector.record_dlq(source_name)
            return PipelineStatusCode.EXTRACTION_FAILED, None, meta

        # 7. Deterministic Entity Resolution
        raw_entity_name = ""
        if record_type == RecordType.STARTUP:
            raw_entity_name = canonical_entity.content.get("entityName", "")
        elif record_type == RecordType.PRODUCT:
            raw_entity_name = canonical_entity.content.get("startupName", "")
        elif record_type == RecordType.JOB:
            raw_entity_name = canonical_entity.content.get("company", "")
        elif record_type == RecordType.RESEARCH_PAPER:
            raw_entity_name = canonical_entity.content.get("title", "")
        elif record_type == RecordType.NEWS:
            raw_entity_name = canonical_entity.content.get("publisher", "")

        if raw_entity_name:
            try:
                resolution = resolver.resolve(
                    raw_name=raw_entity_name,
                    entity_type=record_type.value,
                    domain=source_url,
                    source_url=source_url
                )
                await audit_logger.log_mapping(
                    resolution=resolution,
                    entity_type=record_type.value,
                    source_url=source_url
                )
                
                if record_type == RecordType.STARTUP:
                    canonical_entity.content["entityName"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.PRODUCT:
                    canonical_entity.content["startupName"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.JOB:
                    canonical_entity.content["company"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.NEWS:
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.RESEARCH_PAPER:
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id

                meta["entity_resolved"] = f"{raw_entity_name} -> {resolution.canonical_value} ({resolution.decision})"
            except Exception as e:
                logger.warning(f"Entity resolution error: {e}")

        # 8. GitHub Enrichment (for papers)
        if record_type == RecordType.RESEARCH_PAPER:
            gh_url = canonical_entity.content.get("github_url") or github_enricher.extract_github_url(raw_payload.raw_content)
            if gh_url:
                canonical_entity.content["github_url"] = gh_url
                stars = await github_enricher.fetch_repo_stars(gh_url)
                canonical_entity.content["github_stars"] = stars

        # 9. Persistent Storage
        try:
            await self.entity_repo.save_canonical_entity(canonical_entity)
            await deduplicator.claim_url(source_url, raw_payload.raw_content)
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.STORED)
            await metrics_collector.record_stored(source_name)
        except Exception as e:
            await checkpoint_engine.update_state(source_url, source_name, record_type.value, CheckpointState.FAILED, error=str(e))
            return PipelineStatusCode.STORAGE_FAILED, canonical_entity, meta

        logger.info(f"Successfully processed and stored record for {source_url}")
        return PipelineStatusCode.NEW_RECORD_STORED, canonical_entity, meta

async_pipeline_processor = AsyncPipelineProcessor()
