import aiosqlite
import os
from contextlib import asynccontextmanager
from src.core.config import settings
from src.core.logging import logger

class DatabaseManager:
    """
    Async Database Manager supporting SQLite for local runs and PostgreSQL compatibility.
    Handles table initialization, connections, and transactional persistence.
    """
    
    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or settings.DATABASE_URL
        self._db_path = self._extract_sqlite_path(self.db_url)
        
    def _extract_sqlite_path(self, url: str) -> str:
        if "sqlite" in url:
            path = url.split("///")[-1]
            return path
        return "pipeline.db"

    @asynccontextmanager
    async def get_connection(self):
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init_db(self) -> None:
        """Initializes canonical relational tables and deduplication indexes."""
        os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        
        async with self.get_connection() as conn:
            # Startups Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS startups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT UNIQUE NOT NULL,
                    entity_name TEXT NOT NULL,
                    employee_count INTEGER,
                    funding_total_usd REAL,
                    data_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                );
            """)
            
            # Products Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT UNIQUE NOT NULL,
                    product_name TEXT NOT NULL,
                    startup_name TEXT NOT NULL,
                    pricing_model TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                );
            """)
            
            # Research Papers Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS research_papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    paper_url TEXT NOT NULL,
                    github_url TEXT,
                    github_stars INTEGER,
                    published_date TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                );
            """)
            
            # Jobs Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT UNIQUE NOT NULL,
                    company TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    is_remote INTEGER NOT NULL,
                    role_family TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                );
            """)
            
            # News Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL
                );
            """)
            
            # Canonical Entities Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS canonical_entities (
                    canonical_entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    domains_json TEXT NOT NULL,
                    external_ids_json TEXT NOT NULL,
                    source_urls_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_entities_type_norm_name
                ON canonical_entities (entity_type, normalized_name);
            """)

            # Entity Mapping Audit Log Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mapping_id TEXT UNIQUE NOT NULL,
                    schema_version TEXT NOT NULL,
                    source_record_id TEXT,
                    entity_type TEXT NOT NULL,
                    raw_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    canonical_value TEXT NOT NULL,
                    resolved_canonical_entity_id TEXT,
                    decision TEXT NOT NULL DEFAULT 'NO_MATCH',
                    match_method TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    timestamp TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    resolver_version TEXT NOT NULL
                );
            """)

            # Auto-migration for pre-existing SQLite databases
            for alter_cmd in [
                "ALTER TABLE entity_mappings ADD COLUMN source_record_id TEXT;",
                "ALTER TABLE entity_mappings ADD COLUMN resolved_canonical_entity_id TEXT;",
                "ALTER TABLE entity_mappings ADD COLUMN decision TEXT NOT NULL DEFAULT 'NO_MATCH';",
                "ALTER TABLE entity_mappings ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '{}';",
                "ALTER TABLE research_papers ADD COLUMN arxiv_id TEXT;",
                "ALTER TABLE research_papers ADD COLUMN normalized_title TEXT;",
                "ALTER TABLE research_papers ADD COLUMN primary_category TEXT;",
                "ALTER TABLE research_papers ADD COLUMN abstract TEXT;",
                "ALTER TABLE research_papers ADD COLUMN content_hash TEXT;",
                "ALTER TABLE research_papers ADD COLUMN enrichment_status TEXT DEFAULT 'PENDING';",
                "ALTER TABLE research_papers ADD COLUMN enrichment_updated_at TEXT;"
            ]:
                try:
                    await conn.execute(alter_cmd)
                except Exception:
                    pass

            # Deduplication Fingerprint Store
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS deduplication_store (
                    url_hash TEXT PRIMARY KEY,
                    canonical_url TEXT NOT NULL,
                    simhash INTEGER,
                    created_at TEXT NOT NULL
                );
            """)
            
            # Dead Letter Queue (DLQ) Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dlq_id TEXT UNIQUE NOT NULL,
                    source_url TEXT NOT NULL,
                    error_category TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    failed_component TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    enqueued_at TEXT NOT NULL
                );
            """)
            
            await conn.commit()
            logger.info("Database schemas initialized successfully.", extra={"db_path": self._db_path})

db_manager = DatabaseManager()
