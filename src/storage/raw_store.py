import os
import hashlib
from datetime import datetime, timezone
from src.core.config import settings
from src.storage.database import db_manager, DatabaseManager
from src.utils.time import format_iso8601
from src.core.logging import logger

class RawPayloadStore:
    """
    Raw Payload Staging & Storage.
    Persists raw fetched HTML/XML payloads to disk and registers metadata in database.
    Supports content-hash idempotency (detecting SAME URL + CHANGED CONTENT).
    """

    def __init__(self, raw_dir: str | None = None, db: DatabaseManager = db_manager):
        self.raw_dir = raw_dir or settings.RAW_STORAGE_DIR
        self.db = db

    def compute_content_hash(self, content: str) -> str:
        """Computes SHA256 hex hash of raw content bytes."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def init_raw_table(self) -> None:
        """Initializes raw_payloads metadata table."""
        async with self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_payloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    http_status INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    content_length INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    raw_file_path TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    fetched_at TEXT NOT NULL
                );
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_url ON raw_payloads(source_url);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_hash ON raw_payloads(content_hash);")
            await conn.commit()

    async def is_content_unchanged(self, source_url: str, content_hash: str) -> bool:
        """
        Checks if the exact (source_url, content_hash) combination has already been staged and processed.
        Returns True if SAME URL + SAME CONTENT_HASH.
        """
        await self.init_raw_table()
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM raw_payloads WHERE source_url = ? AND content_hash = ?",
                (source_url, content_hash)
            )
            row = await cursor.fetchone()
            return row is not None

    async def get_latest_content_hash(self, source_url: str) -> str | None:
        """Retrieves the most recent content_hash staged for a source_url."""
        await self.init_raw_table()
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT content_hash FROM raw_payloads WHERE source_url = ? ORDER BY id DESC LIMIT 1",
                (source_url,)
            )
            row = await cursor.fetchone()
            if row:
                return row["content_hash"]
        return None

    async def save_raw_payload(
        self,
        source_url: str,
        source_name: str,
        content: str,
        content_type: str = "text/html",
        http_status: int = 200,
        attempt_count: int = 1
    ) -> tuple[str, str]:
        """
        Saves raw payload text to disk under data/raw/YYYY-MM-DD/{hash}.txt and records metadata in database.
        Returns (content_hash, file_path).
        """
        await self.init_raw_table()
        
        content_hash = self.compute_content_hash(content)
        content_length = len(content.encode("utf-8"))
        now = datetime.now(timezone.utc)
        date_folder = now.strftime("%Y-%m-%d")
        
        target_dir = os.path.join(self.raw_dir, date_folder)
        os.makedirs(target_dir, exist_ok=True)

        ext = ".xml" if "xml" in content_type.lower() else ".html"
        file_name = f"{content_hash[:16]}{ext}"
        file_path = os.path.join(target_dir, file_name)

        # Write to disk
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        fetched_at = format_iso8601(now)

        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO raw_payloads (
                    source_url, source_name, http_status, content_hash,
                    content_length, content_type, raw_file_path, attempt_count, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                source_url, source_name, http_status, content_hash,
                content_length, content_type, file_path, attempt_count, fetched_at
            ))
            await conn.commit()

        logger.info(f"Raw payload staged ({content_length} bytes) to {file_path}", extra={"url": source_url, "hash": content_hash[:8]})
        return content_hash, file_path

raw_store = RawPayloadStore()
