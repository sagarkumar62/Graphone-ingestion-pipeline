import uuid
import pytest
from datetime import datetime, timedelta, timezone
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus, FreshnessReason
from src.utils.time import format_iso8601, parse_date_string

def test_freshness_window_exact_boundary():
    now = datetime.now(timezone.utc)

    # 1 hour ago -> FRESH
    dt_1h = now - timedelta(hours=1)
    res_1h = freshness_validator.evaluate_freshness(format_iso8601(dt_1h), reference_now=now)
    assert res_1h.status == FreshnessStatus.FRESH
    assert res_1h.age_hours == 1.0

    # Exactly 24 hours ago -> FRESH
    dt_24h = now - timedelta(hours=24)
    res_24h = freshness_validator.evaluate_freshness(format_iso8601(dt_24h), reference_now=now)
    assert res_24h.status == FreshnessStatus.FRESH
    assert res_24h.age_hours == 24.0

    # 25 hours ago -> STALE
    dt_25h = now - timedelta(hours=25)
    res_25h = freshness_validator.evaluate_freshness(format_iso8601(dt_25h), reference_now=now)
    assert res_25h.status == FreshnessStatus.STALE
    assert res_25h.age_hours == 25.0

def test_freshness_missing_and_invalid_date():
    now = datetime.now(timezone.utc)

    # None date -> UNKNOWN / REJECTED
    res_none = freshness_validator.evaluate_freshness(None, reference_now=now)
    assert res_none.status == FreshnessStatus.UNKNOWN
    assert res_none.published_at is None

    # Invalid string -> UNKNOWN / REJECTED
    res_invalid = freshness_validator.evaluate_freshness("invalid-date-string", reference_now=now)
    assert res_invalid.status == FreshnessStatus.UNKNOWN

def test_relative_date_normalization():
    now = datetime.now(timezone.utc)

    # "3 hours ago"
    res_3h = freshness_validator.evaluate_freshness("3 hours ago", reference_now=now)
    assert res_3h.status == FreshnessStatus.FRESH
    assert abs(res_3h.age_hours - 3.0) < 0.1

    # "just now"
    res_now = freshness_validator.evaluate_freshness("just now", reference_now=now)
    assert res_now.status == FreshnessStatus.FRESH
    assert abs(res_now.age_hours) < 0.01

def test_timezone_normalization():
    now = datetime.now(timezone.utc)
    tz_plus2 = timezone(timedelta(hours=2))

    # 2 hours ago represented in +02:00 timezone
    dt_2h_ago_plus2 = (now - timedelta(hours=2)).astimezone(tz_plus2)
    dt_str = dt_2h_ago_plus2.isoformat()

    res = freshness_validator.evaluate_freshness(dt_str, reference_now=now)
    assert res.status == FreshnessStatus.FRESH
    assert abs(res.age_hours - 2.0) < 0.1

@pytest.mark.asyncio
async def test_job_deduplication_isolation():
    from src.pipeline.deduplication import deduplicator
    uid = str(uuid.uuid4())
    url1 = f"https://www.arbeitnow.com/jobs/view/unique-job-{uid}-1"
    url2 = f"https://www.arbeitnow.com/jobs/view/unique-job-{uid}-2"

    # First claim -> not duplicate
    is_dup1, _ = await deduplicator.is_duplicate_url(url1)
    assert not is_dup1
    await deduplicator.claim_url(url1, "job content 111")

    # Second claim same URL -> duplicate
    is_dup1_again, _ = await deduplicator.is_duplicate_url(url1)
    assert is_dup1_again

    # Distinct URL -> not duplicate
    is_dup2, _ = await deduplicator.is_duplicate_url(url2)
    assert not is_dup2
