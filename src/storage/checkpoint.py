from enum import Enum
from src.storage.database import db_manager, DatabaseManager
from src.utils.time import format_iso8601
from src.core.logging import logger

class CheckpointState(str, Enum):
    DISCOVERED = "DISCOVERED"
    FETCHING = "FETCHING"
    FETCHED = "FETCHED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    STORED = "STORED"
    FAILED = "FAILED"
    DLQ = "DLQ"

class CheckpointEngine:
    """
    Checkpoint & State Persistence Engine.
    Tracks record lifecycle state across restarts to enable resume functionality.
    """

    def __init__(self, db: DatabaseManager = db_manager):
        self.db = db

    async def init_checkpoint_table(self) -> None:
        """Initializes checkpoints table."""
        async with self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    source_url TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempt_count INTEGER DEFAULT 1,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                );
            """)
            await conn.commit()

    async def update_state(
        self,
        source_url: str,
        source_name: str,
        record_type: str,
        state: CheckpointState,
        error: str | None = None
    ) -> None:
        """Updates or registers current processing state for a URL."""
        await self.init_checkpoint_table()
        now_iso = format_iso8601()

        async with self.db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO checkpoints (source_url, source_name, record_type, state, attempt_count, last_error, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    state = excluded.state,
                    attempt_count = checkpoints.attempt_count + 1,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at;
            """, (source_url, source_name, record_type, state.value, error, now_iso))
            await conn.commit()

    async def get_state(self, source_url: str) -> CheckpointState | None:
        """Returns the last recorded processing state for a URL."""
        await self.init_checkpoint_table()
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT state FROM checkpoints WHERE source_url = ?",
                (source_url,)
            )
            row = await cursor.fetchone()
            if row:
                return CheckpointState(row["state"])
        return None

    async def get_completed_urls(self) -> set[str]:
        """Returns all URLs that reached STORED state."""
        await self.init_checkpoint_table()
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT source_url FROM checkpoints WHERE state = ?",
                (CheckpointState.STORED.value,)
            )
            rows = await cursor.fetchall()
            return {row["source_url"] for row in rows}

checkpoint_engine = CheckpointEngine()
