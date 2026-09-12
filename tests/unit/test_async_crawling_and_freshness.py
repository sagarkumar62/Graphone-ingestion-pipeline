import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.models import (
    RecordType,
    RawPayload,
    FreshnessStatus,
    FreshnessReason,
    CrawlerStrategy
)
from src.core.exceptions import (
    CrawlerTimeoutException,
    CrawlerBlockedException,
    CrawlerAntiBotException,
    CrawlerRateLimitException,
    CrawlerException
)
from src.crawlers.async_crawler import AsyncCrawlerEngine
from src.crawlers.rate_limiter import SourceRateLimiter
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator
from src.pipeline.metrics import metrics_collector
from src.sources.registry import registry
from src.sources.news_sources import HuggingFaceDailyPapersSource, TechCrunchAISource
from src.sources.job_sources import AIJobsNetSource, YCWorkAtAStartupSource
from src.storage.raw_store import raw_store
from src.storage.checkpoint import checkpoint_engine, CheckpointState
from src.pipeline.async_pipeline import AsyncPipelineProcessor

@pytest.mark.asyncio
async def test_bounded_concurrency_semaphore():
    crawler = AsyncCrawlerEngine(global_concurrency=2, per_source_concurrency=1)
    assert crawler.global_semaphore._value == 2

@pytest.mark.asyncio
async def test_source_rate_limiter_429_cooldown():
    limiter = SourceRateLimiter(requests_per_second=10.0)
    cooldown = limiter.handle_429("https://example.com/test", retry_after_header="5")
    assert cooldown == 5.0

@pytest.mark.asyncio
async def test_anti_bot_classification_403():
    crawler = AsyncCrawlerEngine()
    mock_res = MagicMock()
    mock_res.status_code = 403
    mock_res.text = "<html><body>Cloudflare Access Denied</body></html>"

    with patch("httpx.AsyncClient.get", return_value=mock_res):
        with pytest.raises(CrawlerAntiBotException):
            await crawler.fetch("https://protected-site.com", "ProtectedSource")

@pytest.mark.asyncio
async def test_4xx_permanent_failure_no_retry():
    crawler = AsyncCrawlerEngine(max_retries=3)
    mock_res = MagicMock()
    mock_res.status_code = 404
    mock_res.text = "Not Found"

    with patch("httpx.AsyncClient.get", return_value=mock_res):
        with pytest.raises(CrawlerException):
            await crawler.fetch_with_retry("https://example.com/404", "TestSource")

@pytest.mark.asyncio
async def test_5xx_retry_backoff():
    crawler = AsyncCrawlerEngine(max_retries=2)
    mock_res_500 = MagicMock()
    mock_res_500.status_code = 500
    mock_res_500.text = "Internal Server Error"

    with patch("httpx.AsyncClient.get", return_value=mock_res_500):
        with pytest.raises(CrawlerException):
            await crawler.fetch_with_retry("https://example.com/500", "TestSource")

def test_freshness_engine_24h_window():
    now = datetime.now(timezone.utc)
    fresh_date = (now - timedelta(hours=5)).isoformat()
    stale_date = (now - timedelta(hours=30)).isoformat()

    res_fresh = freshness_validator.evaluate_freshness(fresh_date, reference_now=now)
    assert res_fresh.status == FreshnessStatus.FRESH
    assert res_fresh.age_hours == 5.0

    res_stale = freshness_validator.evaluate_freshness(stale_date, reference_now=now)
    assert res_stale.status == FreshnessStatus.STALE
    assert res_stale.age_hours == 30.0

def test_relative_date_parsing():
    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    dt_min = freshness_validator.parse_relative_date("30 minutes ago", now)
    assert dt_min == datetime(2026, 9, 10, 11, 30, 0, tzinfo=timezone.utc)

    dt_hr = freshness_validator.parse_relative_date("2 hours ago", now)
    assert dt_hr == datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    dt_yst = freshness_validator.parse_relative_date("Yesterday", now)
    assert dt_yst == datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)

def test_unknown_date_does_not_invent_time():
    res = freshness_validator.evaluate_freshness(None)
    assert res.status == FreshnessStatus.UNKNOWN
    assert res.published_at is None

def test_html_extractor_strips_noise_and_extracts_json_ld():
    raw_html = """
    <html>
        <head>
            <title>Test AI Article Title</title>
            <script type="application/ld+json">
                {"@context": "https://schema.org", "datePublished": "2026-09-10T10:00:00Z"}
            </script>
        </head>
        <body>
            <nav>Menu Items</nav>
            <article>
                <h1>Test AI Article Title</h1>
                <p>This is main article paragraph text describing AI advancements.</p>
            </article>
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    extracted = html_extractor.extract(raw_html, "https://example.com/article")
    assert extracted.title == "Test AI Article Title"
    assert "describing AI advancements" in extracted.main_text
    assert "Menu Items" not in extracted.main_text
    assert len(extracted.json_ld_dates) > 0
    assert extracted.json_ld_dates[0] == "2026-09-10T10:00:00Z"

def test_source_registry_registration():
    sources = registry.list_sources()
    assert "arxiv" in sources
    assert "huggingfacedailypapers" in sources
    assert "techcrunchai" in sources
    assert "mittechreviewai" in sources
    assert "openaiblog" in sources
    assert "hackernewsai" in sources
    assert "aijobsnet" in sources
    assert "ycworkatastartup" in sources
    assert "remoteokai" in sources
    assert "weworkremotelyai" in sources
    assert "cryptojobsai" in sources

@pytest.mark.asyncio
async def test_raw_payload_storage_and_content_hash():
    content = "<html><body><h1>Sample Article Content</h1></body></html>"
    url = "https://example.com/sample_article"

    content_hash, file_path = await raw_store.save_raw_payload(url, "TestSource", content)
    assert len(content_hash) == 64
    assert file_path.endswith(".html")

    is_same = await raw_store.is_content_unchanged(url, content_hash)
    assert is_same is True

@pytest.mark.asyncio
async def test_checkpoint_state_persistence():
    url = "https://example.com/checkpoint_test"
    await checkpoint_engine.update_state(url, "TestSource", "NEWS", CheckpointState.DISCOVERED)
    state = await checkpoint_engine.get_state(url)
    assert state == CheckpointState.DISCOVERED

    await checkpoint_engine.update_state(url, "TestSource", "NEWS", CheckpointState.STORED)
    completed = await checkpoint_engine.get_completed_urls()
    assert url in completed

@pytest.mark.asyncio
async def test_metrics_collector_aggregation():
    await metrics_collector.record_discovered("TechCrunchAI", count=3)
    await metrics_collector.record_stored("TechCrunchAI")
    await metrics_collector.record_freshness("TechCrunchAI", "FRESH")

    summary = metrics_collector.get_summary()
    assert summary["total_discovered"] >= 3
    assert "techcrunchai" in summary["by_source"]
    assert summary["by_source"]["techcrunchai"]["stored"] >= 1


# ============================================================
# Freshness Acceptance Gate Tests (Phase 5.1.1 Item 5)
# Policy: Only FRESH records enter the 24-hour dataset.
#         STALE and UNKNOWN records must be rejected / routed separately.
# ============================================================

class FreshnessAcceptanceGate:
    """
    Simple acceptance gate that enforces 24-hour freshness policy.
    FRESH -> accepted
    STALE -> rejected (do not store in 24h dataset)
    UNKNOWN -> rejected (do not invent date; route to quarantine/review)
    """
    def accept(self, pub_date: str | None, reference_now=None) -> tuple[bool, str]:
        """Returns (accepted: bool, reason: str)."""
        result = freshness_validator.evaluate_freshness(pub_date, reference_now=reference_now)
        if result.status == FreshnessStatus.FRESH:
            return True, "FRESH"
        elif result.status == FreshnessStatus.STALE:
            return False, f"STALE (age={result.age_hours}h)"
        else:
            return False, "UNKNOWN_DATE"


def test_freshness_gate_fresh_record_accepted():
    """A record published 5 hours ago must be accepted."""
    gate = FreshnessAcceptanceGate()
    now = datetime.now(timezone.utc)
    pub_date = (now - timedelta(hours=5)).isoformat()
    accepted, reason = gate.accept(pub_date, reference_now=now)
    assert accepted is True
    assert reason == "FRESH"


def test_freshness_gate_stale_record_rejected():
    """A record published 30 hours ago must be rejected."""
    gate = FreshnessAcceptanceGate()
    now = datetime.now(timezone.utc)
    pub_date = (now - timedelta(hours=30)).isoformat()
    accepted, reason = gate.accept(pub_date, reference_now=now)
    assert accepted is False
    assert "STALE" in reason
    assert "30" in reason


def test_freshness_gate_unknown_date_rejected():
    """A record with no publication date must be rejected from the 24h dataset."""
    gate = FreshnessAcceptanceGate()
    accepted, reason = gate.accept(None)
    assert accepted is False
    assert reason == "UNKNOWN_DATE"


def test_freshness_gate_empty_string_rejected():
    """An empty string date must not be invented; must be rejected."""
    gate = FreshnessAcceptanceGate()
    accepted, reason = gate.accept("")
    assert accepted is False
    assert reason == "UNKNOWN_DATE"


def test_freshness_gate_future_timestamp_handled_safely():
    """
    A timestamp 30 minutes in the future (clock drift) must still be treated as FRESH,
    not rejected. A timestamp 2 hours in future is classified UNKNOWN (too far ahead).
    """
    gate = FreshnessAcceptanceGate()
    now = datetime.now(timezone.utc)
    # 30 minutes ahead: allowed (clock drift tolerance, abs < 1h -> FRESH)
    future_ok = (now + timedelta(minutes=30)).isoformat()
    accepted_ok, reason_ok = gate.accept(future_ok, reference_now=now)
    assert accepted_ok is True, f"Expected FRESH for slight future drift, got {reason_ok}"

    # 2 hours ahead: too far, should be UNKNOWN (not fabricated as FRESH)
    future_too_far = (now + timedelta(hours=2)).isoformat()
    res = freshness_validator.evaluate_freshness(future_too_far, reference_now=now)
    assert res.status == FreshnessStatus.UNKNOWN, f"Expected UNKNOWN for far-future, got {res.status}"


def test_freshness_gate_relative_date_accepted():
    """'2 hours ago' relative date should be parsed to FRESH."""
    gate = FreshnessAcceptanceGate()
    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    accepted, reason = gate.accept("2 hours ago", reference_now=now)
    assert accepted is True
    assert reason == "FRESH"


def test_freshness_gate_stale_relative_rejected():
    """'3 days ago' relative date should be STALE -> rejected."""
    gate = FreshnessAcceptanceGate()
    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    accepted, reason = gate.accept("3 days ago", reference_now=now)
    assert accepted is False
    assert "STALE" in reason


def test_freshness_gate_rss_date_formats():
    """Verify RFC-2822 dates (typical RSS pubDate) are correctly evaluated."""
    gate = FreshnessAcceptanceGate()
    now = datetime(2026, 9, 10, 12, 30, 0, tzinfo=timezone.utc)

    # ~12.5h ago: FRESH
    fresh_rss = "Thu, 10 Sep 2026 00:00:37 +0000"
    accepted, reason = gate.accept(fresh_rss, reference_now=now)
    assert accepted is True, f"Expected FRESH for recent RSS date, got {reason}"

    # ~33h ago: STALE
    stale_rss = "Wed, 09 Sep 2026 03:10:08 +0000"
    accepted2, reason2 = gate.accept(stale_rss, reference_now=now)
    assert accepted2 is False, f"Expected STALE rejection, got {reason2}"
    assert "STALE" in reason2

