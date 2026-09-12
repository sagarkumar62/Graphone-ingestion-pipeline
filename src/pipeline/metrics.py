import time
import asyncio
from typing import Any
from pydantic import BaseModel, Field

class SourceMetrics(BaseModel):
    discovered: int = 0
    started: int = 0
    succeeded: int = 0
    failed: int = 0
    retries: int = 0
    status_429: int = 0
    status_5xx: int = 0
    status_403_antibot: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    unknown_freshness_count: int = 0
    duplicates: int = 0
    stored: int = 0
    dlq: int = 0
    total_latency_sec: float = 0.0

class CrawlMetricsCollector:
    """
    Source-aware structured metrics collector for observability.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self.start_time: float = time.time()
        self.end_time: float | None = None
        self.by_source: dict[str, SourceMetrics] = {}

    def _get_source_metrics(self, source_name: str) -> SourceMetrics:
        key = source_name.lower()
        if key not in self.by_source:
            self.by_source[key] = SourceMetrics()
        return self.by_source[key]

    async def record_discovered(self, source_name: str, count: int = 1) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            m.discovered += count

    async def record_request(self, source_name: str, status_code: int, latency_sec: float = 0.0, is_retry: bool = False, is_antibot: bool = False) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            m.started += 1
            m.total_latency_sec += latency_sec

            if is_retry:
                m.retries += 1

            if is_antibot or status_code == 403:
                m.status_403_antibot += 1
                m.failed += 1
            elif status_code == 429:
                m.status_429 += 1
            elif status_code >= 500:
                m.status_5xx += 1
                m.failed += 1
            elif status_code >= 200 and status_code < 300:
                m.succeeded += 1
            elif status_code >= 400:
                m.failed += 1

    async def record_freshness(self, source_name: str, freshness_status: str) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            if freshness_status == "FRESH":
                m.fresh_count += 1
            elif freshness_status == "STALE":
                m.stale_count += 1
            else:
                m.unknown_freshness_count += 1

    async def record_duplicate(self, source_name: str) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            m.duplicates += 1

    async def record_stored(self, source_name: str) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            m.stored += 1

    async def record_dlq(self, source_name: str) -> None:
        async with self._lock:
            m = self._get_source_metrics(source_name)
            m.dlq += 1

    def get_summary(self) -> dict[str, Any]:
        duration = (self.end_time or time.time()) - self.start_time
        total_discovered = sum(m.discovered for m in self.by_source.values())
        total_stored = sum(m.stored for m in self.by_source.values())
        total_duplicates = sum(m.duplicates for m in self.by_source.values())
        total_failed = sum(m.failed for m in self.by_source.values())
        total_dlq = sum(m.dlq for m in self.by_source.values())
        total_succeeded = sum(m.succeeded for m in self.by_source.values())

        records_per_sec = total_stored / max(0.001, duration)

        return {
            "duration_seconds": round(duration, 2),
            "total_discovered": total_discovered,
            "total_succeeded": total_succeeded,
            "total_stored": total_stored,
            "total_duplicates": total_duplicates,
            "total_failed": total_failed,
            "total_dlq": total_dlq,
            "throughput_records_per_sec": round(records_per_sec, 2),
            "by_source": {k: v.model_dump() for k, v in self.by_source.items()}
        }

metrics_collector = CrawlMetricsCollector()
