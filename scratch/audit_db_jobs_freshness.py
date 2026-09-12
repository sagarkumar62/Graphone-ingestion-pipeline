import sqlite3
import json
from datetime import datetime, timezone
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus

def audit_existing_db_jobs():
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs")
    rows = cursor.fetchall()

    now = datetime.now(timezone.utc)
    print(f"Auditing {len(rows)} database jobs relative to current UTC time: {now.isoformat()}")

    fresh_cnt = 0
    stale_cnt = 0
    unknown_cnt = 0
    test_cnt = 0

    fresh_by_source = {}
    total_by_source = {}

    for r in rows:
        sname = r["source_name"] or "Unknown"
        total_by_source[sname] = total_by_source.get(sname, 0) + 1

        source_url = r["source_url"] or ""
        company = r["company"] or ""

        # Test check
        if "test-job-" in source_url or "sample_job_" in source_url:
            test_cnt += 1
            continue

        pub_date_str = r["published_date"]
        res = freshness_validator.evaluate_freshness(pub_date_str, reference_now=now)

        if res.status == FreshnessStatus.FRESH:
            fresh_cnt += 1
            fresh_by_source[sname] = fresh_by_source.get(sname, 0) + 1
        elif res.status == FreshnessStatus.STALE:
            stale_cnt += 1
        else:
            unknown_cnt += 1

    print("\n--- AUDIT RESULTS ---")
    print(f"Total Rows: {len(rows)}")
    print(f"Test/Legacy Rows: {test_cnt}")
    print(f"Production Rows: {len(rows) - test_cnt}")
    print(f"  PRODUCTION_FRESH (<= 24h): {fresh_cnt}")
    print(f"  PRODUCTION_STALE (> 24h): {stale_cnt}")
    print(f"  UNKNOWN_DATE: {unknown_cnt}")
    print("\nTotal by Source:")
    for s, c in total_by_source.items():
        print(f"  {s}: {c} total ({fresh_by_source.get(s, 0)} fresh)")

if __name__ == "__main__":
    audit_existing_db_jobs()
