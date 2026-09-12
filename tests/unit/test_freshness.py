from datetime import datetime, timedelta, timezone
from src.pipeline.freshness import freshness_validator
from src.utils.time import parse_relative_date

def test_relative_date_parsing():
    now = datetime.now(timezone.utc)
    
    dt_2h = parse_relative_date("2 hours ago", reference_dt=now)
    assert dt_2h is not None
    assert abs((now - dt_2h).total_seconds() - 7200) < 10

    dt_yest = parse_relative_date("yesterday", reference_dt=now)
    assert dt_yest is not None
    assert (now - dt_yest).days == 1

def test_24h_freshness_window():
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=5)
    stale = now - timedelta(hours=48)

    is_fresh_1, _ = freshness_validator.is_fresh(recent.strftime("%Y-%m-%dT%H:%M:%SZ"), reference_now=now)
    assert is_fresh_1

    is_fresh_2, _ = freshness_validator.is_fresh(stale.strftime("%Y-%m-%dT%H:%M:%SZ"), reference_now=now)
    assert not is_fresh_2
