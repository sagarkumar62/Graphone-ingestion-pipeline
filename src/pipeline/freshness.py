import re
from datetime import datetime, timedelta, timezone
from src.core.models import FreshnessStatus, FreshnessReason, FreshnessResult
from src.utils.time import parse_date_string, get_utc_now, format_iso8601
from src.core.logging import logger

class FreshnessValidator:
    """
    Dedicated Freshness Engine for 24-hour News & Jobs validation.
    Evaluates:
    - Absolute ISO/RFC timestamps
    - JSON-LD structured dates
    - Meta tag publication dates
    - Relative date expressions ("2 hours ago", "30 minutes ago", "Yesterday", "Just now")
    - Never invents publication dates when missing (marks as UNKNOWN)
    """

    def __init__(self, window_hours: float = 24.0):
        self.window_hours = window_hours

    def parse_relative_date(self, relative_str: str, now: datetime) -> datetime | None:
        """Parses relative date strings into absolute UTC datetime."""
        clean = relative_str.strip().lower()

        if clean in ("just now", "now", "today"):
            return now

        if clean == "yesterday":
            return now - timedelta(days=1)

        match = re.match(r"^(\d+)\s*(minute|min|hour|hr|day|d)s?\s*ago$", clean)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("min"):
                return now - timedelta(minutes=num)
            elif unit.startswith("h") or unit == "hr":
                return now - timedelta(hours=num)
            elif unit.startswith("d"):
                return now - timedelta(days=num)

        return None

    def evaluate_freshness(
        self,
        date_val: str | datetime | None,
        reason: FreshnessReason = FreshnessReason.UNKNOWN,
        reference_now: datetime | None = None
    ) -> FreshnessResult:
        """
        Evaluates publication timestamp against 24-hour freshness window.
        Returns auditable FreshnessResult.
        """
        now = reference_now or get_utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if not date_val:
            return FreshnessResult(
                status=FreshnessStatus.UNKNOWN,
                reason=FreshnessReason.UNKNOWN,
                published_at=None,
                age_hours=None,
                raw_date_string=None
            )

        raw_str = str(date_val)
        pub_dt: datetime | None = None
        detected_reason = reason

        if isinstance(date_val, datetime):
            pub_dt = date_val
        else:
            # Check relative date first
            rel_dt = self.parse_relative_date(raw_str, now)
            if rel_dt:
                pub_dt = rel_dt
                detected_reason = FreshnessReason.RELATIVE_DATE
            else:
                pub_dt = parse_date_string(raw_str)

        if not pub_dt:
            return FreshnessResult(
                status=FreshnessStatus.UNKNOWN,
                reason=FreshnessReason.UNKNOWN,
                published_at=None,
                age_hours=None,
                raw_date_string=raw_str
            )

        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)

        raw_age = (now - pub_dt).total_seconds() / 3600.0
        age_hours = round(raw_age, 2)
        iso_str = format_iso8601(pub_dt)

        if 0.0 <= age_hours <= self.window_hours:
            status = FreshnessStatus.FRESH
        elif age_hours < 0.0:
            # Future timestamp edge case (e.g. clock drift)
            status = FreshnessStatus.FRESH if abs(age_hours) <= 1.0 else FreshnessStatus.UNKNOWN
        else:
            status = FreshnessStatus.STALE

        return FreshnessResult(
            status=status,
            reason=detected_reason if detected_reason != FreshnessReason.UNKNOWN else FreshnessReason.METADATA,
            published_at=iso_str,
            age_hours=age_hours,
            raw_date_string=raw_str
        )

    def is_fresh(self, published_date_str: str | datetime | None, reference_now: datetime | None = None) -> tuple[bool, str]:
        """
        Backwards-compatible tuple signature: returns (is_fresh: bool, ISO-date: str).
        """
        res = self.evaluate_freshness(published_date_str, reference_now=reference_now)
        if res.status == FreshnessStatus.FRESH:
            return True, res.published_at or format_iso8601()
        elif res.status == FreshnessStatus.STALE:
            return False, res.published_at or format_iso8601()
        else:
            # For unknown dates, return (False, "") or reject as unknown to prevent stale records
            return False, res.published_at or ""

freshness_validator = FreshnessValidator()
