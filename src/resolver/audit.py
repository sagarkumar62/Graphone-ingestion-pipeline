import uuid
from src.resolver.matcher import ResolutionResult
from src.core.models import EntityMappingRecord, RecordType
from src.utils.time import format_iso8601
from src.storage.repositories import MappingAuditRepository, db_manager

class EntityMappingAuditLogger:
    """
    Emits and persists structured audit log records for entity resolution operations.
    """

    def __init__(self, repository: MappingAuditRepository | None = None):
        self.repository = repository or MappingAuditRepository(db=db_manager)

    async def log_mapping(
        self,
        resolution: ResolutionResult,
        entity_type: str,
        source_url: str,
        source_record_id: str | None = None
    ) -> EntityMappingRecord:
        mapping_record = EntityMappingRecord(
            schemaVersion="1.0",
            recordType=RecordType.ENTITY_MAPPING,
            mappingId=f"map_{uuid.uuid4()}",
            sourceRecordId=source_record_id,
            entityType=entity_type,
            rawValue=resolution.raw_value,
            normalizedValue=resolution.normalized_value,
            canonicalValue=resolution.canonical_value,
            resolvedCanonicalEntityId=resolution.canonical_entity_id,
            decision=resolution.decision,
            matchMethod=resolution.match_method,
            confidence=resolution.confidence,
            evidence=resolution.evidence,
            timestamp=format_iso8601(),
            sourceUrl=source_url,
            resolverVersion="1.0.0"
        )

        await self.repository.save_mapping_log(mapping_record)
        return mapping_record

audit_logger = EntityMappingAuditLogger()
