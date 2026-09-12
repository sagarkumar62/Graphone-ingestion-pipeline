import json
from src.storage.database import db_manager, DatabaseManager
from src.core.models import CanonicalEntity, EntityMappingRecord, RecordType
from src.core.logging import logger

class EntityRepository:
    """Repository for persisting canonical entity records."""

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db

    async def save_canonical_entity(self, entity: CanonicalEntity) -> bool:
        """
        Saves a validated canonical entity to its respective database table.
        Uses INSERT OR REPLACE (UPSERT) semantics to guarantee idempotency.
        """
        data = entity.dict()
        record_type = entity.recordType
        source_url = entity.source.url
        source_name = entity.source.name
        collected_at = entity.collectedAt
        data_json = json.dumps(data)

        async with self.db.get_connection() as conn:
            if record_type == RecordType.STARTUP:
                await conn.execute("""
                    INSERT INTO startups (schema_version, source_name, source_url, entity_name, employee_count, funding_total_usd, data_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_url) DO UPDATE SET
                        entity_name=excluded.entity_name,
                        employee_count=excluded.employee_count,
                        data_json=excluded.data_json,
                        collected_at=excluded.collected_at;
                """, (
                    entity.schemaVersion, source_name, source_url,
                    entity.content.get("entityName", ""),
                    entity.content.get("data", {}).get("employeeCount"),
                    entity.content.get("data", {}).get("fundingTotalUsd"),
                    data_json, collected_at
                ))

            elif record_type == RecordType.PRODUCT:
                await conn.execute("""
                    INSERT INTO products (schema_version, source_name, source_url, product_name, startup_name, pricing_model, data_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_url) DO UPDATE SET
                        product_name=excluded.product_name,
                        startup_name=excluded.startup_name,
                        pricing_model=excluded.pricing_model,
                        data_json=excluded.data_json,
                        collected_at=excluded.collected_at;
                """, (
                    entity.schemaVersion, source_name, source_url,
                    entity.content.get("productName", ""),
                    entity.content.get("startupName", ""),
                    entity.content.get("pricingModel", "UNKNOWN"),
                    data_json, collected_at
                ))

            elif record_type == RecordType.RESEARCH_PAPER:
                await conn.execute("""
                    INSERT INTO research_papers (schema_version, source_name, source_url, title, authors_json, paper_url, github_url, github_stars, published_date, abstract, arxiv_id, normalized_title, primary_category, data_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_url) DO UPDATE SET
                        title=excluded.title,
                        github_stars=excluded.github_stars,
                        abstract=excluded.abstract,
                        arxiv_id=excluded.arxiv_id,
                        normalized_title=excluded.normalized_title,
                        primary_category=excluded.primary_category,
                        data_json=excluded.data_json,
                        collected_at=excluded.collected_at;
                """, (
                    entity.schemaVersion, source_name, source_url,
                    entity.content.get("title", ""),
                    json.dumps(entity.content.get("authors", [])),
                    entity.content.get("paper_url", source_url),
                    entity.content.get("github_url"),
                    entity.content.get("github_stars"),
                    entity.content.get("published_date", ""),
                    entity.content.get("abstract"),
                    entity.content.get("arxiv_id"),
                    entity.content.get("normalized_title"),
                    entity.content.get("primaryCategory"),
                    data_json, collected_at
                ))

            elif record_type == RecordType.JOB:
                await conn.execute("""
                    INSERT INTO jobs (schema_version, source_name, source_url, company, published_date, is_remote, role_family, data_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_url) DO UPDATE SET
                        company=excluded.company,
                        published_date=excluded.published_date,
                        data_json=excluded.data_json,
                        collected_at=excluded.collected_at;
                """, (
                    entity.schemaVersion, source_name, source_url,
                    entity.content.get("company", ""),
                    entity.content.get("date", ""),
                    1 if entity.content.get("is_remote") else 0,
                    entity.content.get("role_family", "Engineering"),
                    data_json, collected_at
                ))

            elif record_type == RecordType.NEWS:
                await conn.execute("""
                    INSERT INTO news (schema_version, source_name, source_url, title, summary, published_date, data_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_url) DO UPDATE SET
                        title=excluded.title,
                        summary=excluded.summary,
                        published_date=excluded.published_date,
                        data_json=excluded.data_json,
                        collected_at=excluded.collected_at;
                """, (
                    entity.schemaVersion, source_name, source_url,
                    entity.content.get("title", ""),
                    entity.content.get("summary", ""),
                    entity.content.get("published_date", ""),
                    data_json, collected_at
                ))

            await conn.commit()
            logger.info("Canonical entity saved.", extra={"record_type": record_type.value, "url": source_url})
            return True

    async def get_all_records(self, table_name: str) -> list[dict]:
        """Retrieves all rows from a specified table for export/audit."""
        allowed_tables = {"startups", "products", "research_papers", "jobs", "news", "canonical_entities", "entity_mappings", "dlq_records"}
        if table_name not in allowed_tables:
            raise ValueError(f"Invalid table name: {table_name}")
            
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(f"SELECT * FROM {table_name}")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

class CanonicalEntityRepository:
    """Repository for managing canonical entity master database records."""

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db

    async def save_canonical_entity_record(self, record) -> bool:
        """
        Saves or updates a CanonicalEntityRecord using atomic UPSERT semantics.
        Prevents race conditions and duplicate entity creation.
        """
        from src.core.models import CanonicalEntityRecord
        rec: CanonicalEntityRecord = record
        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO canonical_entities (
                    canonical_entity_id, entity_type, canonical_name, normalized_name,
                    aliases_json, domains_json, external_ids_json, source_urls_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_entity_id) DO UPDATE SET
                    canonical_name=excluded.canonical_name,
                    normalized_name=excluded.normalized_name,
                    aliases_json=excluded.aliases_json,
                    domains_json=excluded.domains_json,
                    external_ids_json=excluded.external_ids_json,
                    source_urls_json=excluded.source_urls_json,
                    updated_at=excluded.updated_at;
            """, (
                rec.canonical_entity_id,
                rec.entity_type,
                rec.canonical_name,
                rec.normalized_name,
                json.dumps(rec.aliases),
                json.dumps(rec.domains),
                json.dumps(rec.external_ids),
                json.dumps(rec.source_urls),
                rec.created_at,
                rec.updated_at
            ))
            await conn.commit()
            return True

    async def get_all_canonical_entities(self) -> list[dict]:
        async with self.db.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM canonical_entities")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

class MappingAuditRepository:
    """Repository for logging entity resolution mappings."""

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db

    async def save_mapping_log(self, record: EntityMappingRecord) -> bool:
        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO entity_mappings (
                    mapping_id, schema_version, source_record_id, entity_type, raw_value, normalized_value,
                    canonical_value, resolved_canonical_entity_id, decision, match_method, confidence,
                    evidence_json, timestamp, source_url, resolver_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mapping_id) DO NOTHING;
            """, (
                record.mappingId, record.schemaVersion, record.sourceRecordId, record.entityType,
                record.rawValue, record.normalizedValue, record.canonicalValue,
                record.resolvedCanonicalEntityId, record.decision, record.matchMethod,
                record.confidence, json.dumps(record.evidence), record.timestamp,
                record.sourceUrl, record.resolverVersion
            ))
            await conn.commit()
            return True

class DLQRepository:
    """Repository for Dead-Letter Queue persistence."""

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db

    async def save_dlq(self, dlq_id: str, source_url: str, category: str, message: str, component: str, payload: dict, attempts: int) -> bool:
        from src.utils.time import format_iso8601
        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO dlq_records (
                    dlq_id, source_url, error_category, error_message, failed_component, payload_json, attempts, enqueued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                dlq_id, source_url, category, message, component,
                json.dumps(payload), attempts, format_iso8601()
            ))
            await conn.commit()
            logger.warning("Record enqueued to DLQ.", extra={"dlq_id": dlq_id, "category": category, "url": source_url})
            return True
