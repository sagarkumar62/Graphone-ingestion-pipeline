import sqlite3
import json
import os
from datetime import datetime

def is_test_record(source_url: str, company_name: str) -> bool:
    if not source_url:
        return True
    test_keywords = ["test-job-", "test_id=", "test_raw_", "test_checkpoint_", "sample_job_"]
    return any(kw in source_url or kw in (company_name or "") for kw in test_keywords)

def run_audit(db_path: str = "pipeline.db"):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs")
    all_rows = cursor.fetchall()

    prod_rows = [r for r in all_rows if not is_test_record(r["source_url"], r["company"])]
    test_rows = [r for r in all_rows if is_test_record(r["source_url"], r["company"])]

    total_prod = len(prod_rows)
    total_test = len(test_rows)

    # 1. Identity & Provenance quality
    source_urls = [r["source_url"] for r in prod_rows]
    unique_urls = set(source_urls)
    duplicate_url_count = len(source_urls) - len(unique_urls)
    missing_urls = sum(1 for r in prod_rows if not r["source_url"])
    invalid_url_formats = sum(1 for r in prod_rows if r["source_url"] and not r["source_url"].startswith("http"))

    # 2. Metadata completeness
    missing_companies = sum(1 for r in prod_rows if not r["company"] or r["company"].strip() == "")
    missing_dates = sum(1 for r in prod_rows if not r["published_date"] or r["published_date"].strip() == "")

    remote_count = sum(1 for r in prod_rows if r["is_remote"])
    onsite_count = total_prod - remote_count

    role_family_breakdown = {}
    titles_cnt = 0
    locations_cnt = 0
    descriptions_cnt = 0

    for r in prod_rows:
        rfamily = r["role_family"] or "Engineering"
        role_family_breakdown[rfamily] = role_family_breakdown.get(rfamily, 0) + 1

        try:
            data = json.loads(r["data_json"])
            content = data.get("content", {})
            if content.get("jobTitle"):
                titles_cnt += 1
            if content.get("location"):
                locations_cnt += 1
            if content.get("descriptionSnippet"):
                descriptions_cnt += 1
        except Exception:
            pass

    # 3. Source Breakdown
    source_breakdown = {}
    for r in prod_rows:
        sname = r["source_name"] or "Unknown"
        source_breakdown[sname] = source_breakdown.get(sname, 0) + 1

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "identity_quality": {
            "total_job_rows": len(all_rows),
            "total_production_records": total_prod,
            "test_legacy_records_excluded": total_test,
            "unique_source_urls": len(unique_urls),
            "duplicate_source_urls": duplicate_url_count,
            "missing_source_urls": missing_urls,
            "invalid_source_url_formats": invalid_url_formats
        },
        "metadata_completeness": {
            "missing_company_name": missing_companies,
            "missing_published_date": missing_dates,
            "remote_job_count": remote_count,
            "onsite_job_count": onsite_count,
            "role_family_breakdown": role_family_breakdown,
            "job_titles_populated": titles_cnt,
            "locations_populated": locations_cnt,
            "descriptions_populated": descriptions_cnt
        },
        "source_breakdown": source_breakdown
    }

    os.makedirs("data/reports", exist_ok=True)
    report_path = "data/reports/jobs_quality_audit.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Jobs Quality Audit Completed successfully!")
    print(f"Total Database Rows: {len(all_rows)}")
    print(f"Production Records Audited: {total_prod}")
    print(f"Test Records Excluded: {total_test}")
    print(f"Unique URLs: {len(unique_urls)}")
    print(f"Duplicate URLs: {duplicate_url_count}")

    conn.close()
    return report

if __name__ == "__main__":
    run_audit()
