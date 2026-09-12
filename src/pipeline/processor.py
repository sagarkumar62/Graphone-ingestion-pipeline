import uuid
from typing import Any
from src.core.models import RecordType, CanonicalEntity, PipelineStatusCode
from src.core.exceptions import PipelineException
from src.crawlers.http import AsyncHTTPCrawler
from src.crawlers.playwright import PlaywrightAsyncCrawler
from src.pipeline.freshness import freshness_validator
from src.pipeline.deduplication import deduplicator
from src.llm.orchestrator import orchestrator
from src.resolver.matcher import resolver
from src.resolver.audit import audit_logger
from src.enrichment.github import github_enricher
from src.storage.repositories import EntityRepository, DLQRepository
from src.core.logging import logger

class PipelineProcessor:
    """
    End-to-End Vertical Slice Pipeline Processor.
    Orchestrates: Source -> Crawler -> Raw Payload -> Freshness/Dedup -> LLM Extraction -> Schema Validation -> Entity Resolution -> Enrichment -> Storage / DLQ.
    Returns explicit PipelineStatusCode for precise CLI and audit monitoring.
    """

    def __init__(
        self,
        entity_repo: EntityRepository | None = None,
        dlq_repo: DLQRepository | None = None
    ):
        self.entity_repo = entity_repo or EntityRepository()
        self.dlq_repo = dlq_repo or DLQRepository()
        self.http_crawler = AsyncHTTPCrawler()
        self.playwright_crawler = PlaywrightAsyncCrawler()

    async def process_record(
        self,
        source_url: str,
        source_name: str,
        record_type: RecordType,
        use_browser: bool = False
    ) -> tuple[PipelineStatusCode, CanonicalEntity | None, dict[str, Any]]:
        """
        Processes a single record end-to-end through the ingestion slice.
        Returns (status_code, canonical_entity, execution_metadata).
        """
        meta: dict[str, Any] = {
            "source_url": source_url,
            "source_name": source_name,
            "record_type": record_type.value,
            "provider_used": None,
            "content_bytes": 0,
            "github_enrichment": "NOT_APPLICABLE"
        }

        logger.info(f"--- Starting Vertical Slice Ingestion for {record_type.value} ---", extra={"url": source_url})

        # Step 1: Deduplication Check
        is_dup, url_hash = await deduplicator.is_duplicate_url(source_url)
        if is_dup:
            logger.info(f"URL fingerprint {url_hash[:8]} already processed. Skipping duplicate.")
            return PipelineStatusCode.DUPLICATE_ALREADY_PROCESSED, None, meta

        # Step 2: Live Crawler Fetch
        try:
            crawler = self.playwright_crawler if use_browser else self.http_crawler
            raw_payload = await crawler.fetch_with_retry(source_url, source_name)
            meta["content_bytes"] = len(raw_payload.raw_content.encode("utf-8"))
            meta["http_status"] = raw_payload.http_status
        except Exception as e:
            dlq_id = f"dlq_{uuid.uuid4()}"
            await self.dlq_repo.save_dlq(
                dlq_id=dlq_id,
                source_url=source_url,
                category="FETCH_FAILED",
                message=str(e),
                component="CrawlerLayer",
                payload={"source_name": source_name, "record_type": record_type.value},
                attempts=3
            )
            return PipelineStatusCode.FETCH_FAILED, None, meta

        # Step 3: Freshness Filter (for News & Jobs)
        if record_type in {RecordType.NEWS, RecordType.JOB}:
            from src.sources.registry import registry
            adapter = registry.get(source_name)
            pub_date_candidate = adapter.extract_published_at(raw_payload) if adapter else None
            freshness_res = freshness_validator.evaluate_freshness(pub_date_candidate)
            if freshness_res.status != FreshnessStatus.FRESH:
                return PipelineStatusCode.FRESHNESS_REJECTED, None, meta

        # Step 4: Multi-Tier LLM / DOM Extraction & JSON Schema Validation
        try:
            if source_name == "ArXiv":
                from src.sources.arxiv import ArXivSourceAdapter
                adapter = ArXivSourceAdapter()
                raw_dict = adapter.parse_raw_payload(raw_payload)
                canonical_entity = CanonicalEntity(**raw_dict)
                provider_used = "arXivHTMLParser"
            else:
                canonical_entity, provider_used = await orchestrator.extract_canonical_entity(
                    raw_text=raw_payload.raw_content,
                    record_type=record_type,
                    source_name=source_name,
                    source_url=source_url
                )
            meta["provider_used"] = provider_used
        except Exception as e:
            dlq_id = f"dlq_{uuid.uuid4()}"
            await self.dlq_repo.save_dlq(
                dlq_id=dlq_id,
                source_url=source_url,
                category="EXTRACTION_OR_VALIDATION_FAILED",
                message=str(e),
                component="LLMOrchestrator",
                payload={"raw_content_preview": raw_payload.raw_content[:200]},
                attempts=3
            )
            return PipelineStatusCode.EXTRACTION_FAILED, None, meta

        # Step 5: Deterministic Entity Resolution & Audit Logging
        raw_entity_name = ""
        if record_type == RecordType.STARTUP:
            raw_entity_name = canonical_entity.content.get("entityName", "")
        elif record_type == RecordType.PRODUCT:
            raw_entity_name = canonical_entity.content.get("startupName", "")
        elif record_type == RecordType.JOB:
            raw_entity_name = canonical_entity.content.get("company", "")
        elif record_type == RecordType.RESEARCH_PAPER:
            raw_entity_name = canonical_entity.content.get("title", "")

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
                
                # Assign canonical value
                if record_type == RecordType.STARTUP:
                    canonical_entity.content["entityName"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.PRODUCT:
                    canonical_entity.content["startupName"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.JOB:
                    canonical_entity.content["company"] = resolution.canonical_value
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id
                elif record_type == RecordType.RESEARCH_PAPER:
                    canonical_entity.content["canonical_entity_id"] = resolution.canonical_entity_id

                meta["entity_resolved"] = f"{raw_entity_name} -> {resolution.canonical_value} ({resolution.decision} / {resolution.match_method})"
            except Exception as e:
                logger.warning(f"Entity resolution failed: {e}")

        # Step 6: GitHub Enrichment (for Research Papers)
        if record_type == RecordType.RESEARCH_PAPER:
            gh_url = canonical_entity.content.get("github_url") or github_enricher.extract_github_url(raw_payload.raw_content)
            if gh_url:
                canonical_entity.content["github_url"] = gh_url
                stars = await github_enricher.fetch_repo_stars(gh_url)
                canonical_entity.content["github_stars"] = stars
                meta["github_enrichment"] = f"FOUND ({gh_url}, {stars} stars)"
            else:
                canonical_entity.content["github_url"] = None
                canonical_entity.content["github_stars"] = None
                meta["github_enrichment"] = "NOT_FOUND (github_url=null)"

        # Step 7: Persistent Storage
        try:
            await self.entity_repo.save_canonical_entity(canonical_entity)
            await deduplicator.claim_url(source_url, raw_payload.raw_content)
        except Exception as e:
            return PipelineStatusCode.STORAGE_FAILED, canonical_entity, meta

        logger.info(f"--- Successfully stored new record for {record_type.value} ---", extra={"url": source_url})
        return PipelineStatusCode.NEW_RECORD_STORED, canonical_entity, meta

processor = PipelineProcessor()
