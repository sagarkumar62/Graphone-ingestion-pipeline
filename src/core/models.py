from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from src.utils.time import format_iso8601

class RecordType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"
    ENTITY_MAPPING = "ENTITY_MAPPING"

class PipelineStatusCode(str, Enum):
    NEW_RECORD_STORED = "NEW_RECORD_STORED"
    DUPLICATE_ALREADY_PROCESSED = "DUPLICATE_ALREADY_PROCESSED"
    FETCH_FAILED = "FETCH_FAILED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    FRESHNESS_REJECTED = "FRESHNESS_REJECTED"
    ENTITY_RESOLUTION_FAILED = "ENTITY_RESOLUTION_FAILED"
    ENRICHMENT_FAILED = "ENRICHMENT_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"
    UNKNOWN = "UNKNOWN"

class ResolutionDecision(str, Enum):
    EXACT_EXTERNAL_ID_MATCH = "EXACT_EXTERNAL_ID_MATCH"
    DOMAIN_MATCH = "DOMAIN_MATCH"
    EXACT_NAME_MATCH = "EXACT_NAME_MATCH"
    ALIAS_MATCH = "ALIAS_MATCH"
    COMPOSITE_MATCH = "COMPOSITE_MATCH"
    CREATE_NEW_CANONICAL = "CREATE_NEW_CANONICAL"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"

class FreshnessReason(str, Enum):
    METADATA = "METADATA"
    JSON_LD = "JSON_LD"
    VISIBLE_TEXT = "VISIBLE_TEXT"
    RELATIVE_DATE = "RELATIVE_DATE"
    UNKNOWN = "UNKNOWN"

class CrawlerStrategy(str, Enum):
    HTTP_HTML = "HTTP_HTML"
    BROWSER_RENDERED = "BROWSER_RENDERED"
    BLOCKED = "BLOCKED"

class FreshnessResult(BaseModel):
    status: FreshnessStatus
    reason: FreshnessReason
    published_at: str | None = None
    age_hours: float | None = None
    raw_date_string: str | None = None


class CanonicalEntityRecord(BaseModel):
    canonical_entity_id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=format_iso8601)
    updated_at: str = Field(default_factory=format_iso8601)

class SourceProvenance(BaseModel):
    name: str
    url: str

class RawPayload(BaseModel):
    url: str
    source_name: str
    raw_content: str
    content_type: str = "text/html"
    fetched_at: str = Field(default_factory=format_iso8601)
    http_status: int = 200

class CanonicalEntity(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType
    source: SourceProvenance
    content: dict[str, Any]
    collectedAt: str = Field(default_factory=format_iso8601)

class EntityMappingRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: RecordType = RecordType.ENTITY_MAPPING
    mappingId: str
    sourceRecordId: str | None = None
    entityType: str
    rawValue: str
    normalizedValue: str
    canonicalValue: str
    resolvedCanonicalEntityId: str | None = None
    decision: str = ResolutionDecision.NO_MATCH.value
    matchMethod: str
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=format_iso8601)
    sourceUrl: str
    resolverVersion: str = "1.0.0"
