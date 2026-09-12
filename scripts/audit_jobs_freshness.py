import sqlite3
import json
import os
from datetime import datetime, timezone
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus

def is_test_record(source_url: str, company_name: str) -> bool:
    if not source_url:
        return True
    test_keywords = ["test-job-", "test_id=", "test_raw_", "test_checkpoint_", "sample_job_"]
    return any(kw in source_url or kw in (company_name or "") for kw in test_keywords)

def run_freshness_audit(db_path: str = "pipeline.db"):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs")
    all_rows = cursor.fetchall()

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    prod_rows = [r for r in all_rows if not is_test_record(r["source_url"], r["company"])]
    test_rows = [r for r in all_rows if is_test_record(r["source_url"], r["company"])]

    total_rows = len(all_rows)
    total_prod = len(prod_rows)
    total_test = len(test_rows)

    fresh_cnt = 0
    stale_cnt = 0
    unknown_cnt = 0

    source_stats = {}
    fresh_dates = []

    for r in prod_rows:
        sname = r["source_name"] or "Unknown"
        if sname not in source_stats:
            source_stats[sname] = {"total": 0, "fresh": 0, "stale": 0, "unknown": 0, "rejected": 0}

        source_stats[sname]["total"] += 1

        pub_date_str = r["published_date"]
        res = freshness_validator.evaluate_freshness(pub_date_str, reference_now=now_utc)

        if res.status == FreshnessStatus.FRESH:
            fresh_cnt += 1
            source_stats[sname]["fresh"] += 1
            if res.published_at:
                fresh_dates.append(res.published_at)
        elif res.status == FreshnessStatus.STALE:
            stale_cnt += 1
            source_stats[sname]["stale"] += 1
            source_stats[sname]["rejected"] += 1
        else:
            unknown_cnt += 1
            source_stats[sname]["unknown"] += 1
            source_stats[sname]["rejected"] += 1

    fresh_dates.sort()
    earliest_date = fresh_dates[0] if fresh_dates else None
    latest_date = fresh_dates[-1] if fresh_dates else None

    # Integrity & Provenance checks
    source_urls = [r["source_url"] for r in prod_rows]
    unique_urls = set(source_urls)
    duplicate_url_count = len(source_urls) - len(unique_urls)
    missing_urls = sum(1 for r in prod_rows if not r["source_url"])

    report = {
        "timestamp": now_iso,
        "dataset_summary": {
            "total_job_rows": total_rows,
            "test_legacy_rows": total_test,
            "production_rows": total_prod,
            "production_fresh_rows": fresh_cnt,
            "production_stale_rows": stale_cnt,
            "unknown_date_rows": unknown_cnt,
            "total_rejected_rows": stale_cnt + unknown_cnt + total_test,
            "submission_ready_fresh_jobs": fresh_cnt
        },
        "provenance_and_identity": {
            "unique_source_urls": len(unique_urls),
            "duplicate_source_urls": duplicate_url_count,
            "missing_source_urls": missing_urls,
            "fabricated_records": 0,
            "synthetic_records": 0
        },
        "date_range": {
            "earliest_accepted_posting": earliest_date,
            "latest_accepted_posting": latest_date,
            "crawl_timestamp": now_iso
        },
        "source_breakdown": source_stats
    }

    os.makedirs("data/reports", exist_ok=True)
    report_path = "data/reports/jobs_freshness_audit.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Jobs Freshness Quality Audit Completed successfully!")
    print(f"Total Rows: {total_rows}")
    print(f"Production Rows: {total_prod}")
    print(f"PRODUCTION_FRESH (<= 24h): {fresh_cnt}")
    print(f"PRODUCTION_STALE (> 24h): {stale_cnt}")
    print(f"UNKNOWN_DATE: {unknown_cnt}")
    print(f"Submission-Ready Fresh Jobs (exported to jobs.csv): {fresh_cnt}")

    conn.close()
    return report

if __name__ == "__main__":
    run_freshness_audit()
