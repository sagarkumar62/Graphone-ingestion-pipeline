from datetime import datetime, timezone, timedelta
import re
from dateutil import parser as dateutil_parser

def get_utc_now() -> datetime:
    """Returns the current aware UTC datetime."""
    return datetime.now(timezone.utc)

def format_iso8601(dt: datetime | None = None) -> str:
    """Formats a datetime object as an ISO-8601 UTC string (e.g. 2026-09-10T14:00:00Z)."""
    if dt is None:
        dt = get_utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_relative_date(text: str, reference_dt: datetime | None = None) -> datetime | None:
    """
    Parses relative date phrases such as '2 hours ago', '30 mins ago', '1 day ago', 'yesterday'.
    """
    if not text:
        return None
    
    if reference_dt is None:
        reference_dt = get_utc_now()
    elif reference_dt.tzinfo is None:
        reference_dt = reference_dt.replace(tzinfo=timezone.utc)

    text_clean = text.lower().strip()
    
    if "yesterday" in text_clean:
        return reference_dt - timedelta(days=1)
    if "today" in text_clean or "just now" in text_clean:
        return reference_dt

    # Pattern for N hours/minutes/days/weeks ago
    match = re.search(r'(\d+)\s+(second|sec|minute|min|hour|hr|day|week)s?\s+ago', text_clean)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit.startswith('sec'):
            return reference_dt - timedelta(seconds=val)
        elif unit.startswith('min'):
            return reference_dt - timedelta(minutes=val)
        elif unit.startswith('hour') or unit.startswith('hr'):
            return reference_dt - timedelta(hours=val)
        elif unit.startswith('day'):
            return reference_dt - timedelta(days=val)
        elif unit.startswith('week'):
            return reference_dt - timedelta(weeks=val)
            
    return None

def parse_date_string(date_str: str | None) -> datetime | None:
    """
    Tries multiple parsing strategies to parse an arbitrary date string into an aware UTC datetime.
    Handles ISO-8601, RFC2822, relative strings ('2 hours ago'), and common date formats.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    
    # Try relative date parsing first
    rel_dt = parse_relative_date(date_str)
    if rel_dt:
        return rel_dt
        
    # Try dateutil parser
    try:
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except (ValueError, TypeError, OverflowError):
        pass

    return None
