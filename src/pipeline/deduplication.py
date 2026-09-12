from src.utils.hashing import hash_url, compute_simhash, hamming_distance
from src.storage.database import db_manager, DatabaseManager
from src.utils.time import format_iso8601
from src.core.logging import logger

class DeduplicationEngine:
    """
    Engine handling URL fingerprinting and SimHash content deduplication.
    """

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db
        self._seen_url_hashes: set[str] = set()

    async def is_duplicate_url(self, raw_url: str) -> tuple[bool, str]:
        """
        Checks if a URL has already been ingested.
        Returns (is_duplicate: bool, url_hash: str).
        """
        url_hash = hash_url(raw_url)

        if url_hash in self._seen_url_hashes:
            return True, url_hash

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT url_hash FROM deduplication_store WHERE url_hash = ?",
                (url_hash,)
            )
            row = await cursor.fetchone()
            if row:
                self._seen_url_hashes.add(url_hash)
                return True, url_hash

        return False, url_hash

    async def claim_url(self, raw_url: str, content_text: str = "") -> str:
        """
        Claims a unique URL in the deduplication store.
        Stores 64-bit simhash as a signed integer or string hex to prevent SQLite integer overflow.
        """
        url_hash = hash_url(raw_url)
        simhash_raw = compute_simhash(content_text) if content_text else None
        # Convert to signed 64-bit integer for SQLite safety
        simhash_val = (simhash_raw if simhash_raw < (1 << 63) else simhash_raw - (1 << 64)) if simhash_raw is not None else None
        now_iso = format_iso8601()

        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO deduplication_store (url_hash, canonical_url, simhash, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url_hash) DO NOTHING;
            """, (url_hash, raw_url, simhash_val, now_iso))
            await conn.commit()

        self._seen_url_hashes.add(url_hash)
        return url_hash

deduplicator = DeduplicationEngine()
