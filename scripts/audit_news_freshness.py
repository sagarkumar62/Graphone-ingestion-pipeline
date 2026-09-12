import sqlite3
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus

def is_test_record(source_url: str) -> bool:
    if not source_url:
        return True
    test_keywords = ["test-paper-", "test-job-", "test-news-", "test_id=", "test_raw_", "test_checkpoint_", "example.com"]
    return any(kw in source_url.lower() for kw in test_keywords)

def audit_news_database(db_path: str = "pipeline.db") -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("SELECT * FROM news").fetchall()
    now_utc = datetime.now(timezone.utc)

    total_rows = len(rows)
    prod_rows = 0
    test_rows = 0

    fresh_count = 0
    stale_count = 0
    unknown_date_count = 0
    rejected_count = 0

    unique_source_urls = set()
    unique_article_urls = set()
    dup_article_urls = 0

    missing_titles = 0
    missing_pub_dates = 0
    missing_source_urls = 0
    missing_article_urls = 0
    ai_relevance_failures = 0

    full_text_count = 0
    partial_text_count = 0
    feed_only_count = 0
    article_fetch_failures = 0

    source_counts = {}
    source_fresh = {}
    source_rejected = {}

    published_timestamps = []

    audited_records = []

    for r in rows:
        r_id = r["id"]
        source_name = r["source_name"] or "UNKNOWN_SOURCE"
        source_url = r["source_url"] or ""
        title = r["title"] or ""
        summary = r["summary"] or ""
        pub_date_str = r["published_date"] or ""
        collected_at = r["collected_at"] or ""

        data_json = {}
        try:
            if r["data_json"]:
                data_json = json.loads(r["data_json"])
        except Exception:
            pass

        content_dict = data_json.get("content", {})
        full_text = content_dict.get("full_text", "")
        article_url = content_dict.get("article_url") or source_url

        source_counts[source_name] = source_counts.get(source_name, 0) + 1
        if source_name not in source_fresh:
            source_fresh[source_name] = 0
            source_rejected[source_name] = 0

        # Title check
        if not title.strip():
            missing_titles += 1

        # URL checks
        if not source_url.strip():
            missing_source_urls += 1
        else:
            unique_source_urls.add(source_url)

        if not article_url.strip():
            missing_article_urls += 1
        else:
            if article_url in unique_article_urls:
                dup_article_urls += 1
            else:
                unique_article_urls.add(article_url)

        # Date & Freshness Check
        if not pub_date_str.strip():
            missing_pub_dates += 1

        f_res = freshness_validator.evaluate_freshness(pub_date_str, reference_now=now_utc)

        # Classification
        if is_test_record(source_url):
            classification = "TEST_OR_LEGACY_FIXTURE"
            test_rows += 1
            rejected_count += 1
            source_rejected[source_name] += 1
        elif f_res.status == FreshnessStatus.FRESH:
            classification = "PRODUCTION_FRESH"
            prod_rows += 1
            fresh_count += 1
            source_fresh[source_name] += 1
            if f_res.published_at:
                published_timestamps.append(f_res.published_at)
        elif f_res.status == FreshnessStatus.STALE:
            classification = "PRODUCTION_STALE"
            prod_rows += 1
            stale_count += 1
            rejected_count += 1
            source_rejected[source_name] += 1
        else:
            classification = "UNKNOWN_DATE"
            prod_rows += 1
            unknown_date_count += 1
            rejected_count += 1
            source_rejected[source_name] += 1

        # Text Quality
        if len(full_text) >= 500:
            text_quality = "FULL_TEXT"
            full_text_count += 1
        elif len(full_text) >= 100:
            text_quality = "PARTIAL_TEXT"
            partial_text_count += 1
        elif len(full_text) > 0:
            text_quality = "FEED_ONLY"
            feed_only_count += 1
        else:
            text_quality = "FETCH_FAILURE"
            article_fetch_failures += 1

        audited_records.append({
            "id": r_id,
            "source_name": source_name,
            "source_url": source_url,
            "title": title,
            "published_date": pub_date_str,
            "normalized_published_at": f_res.published_at,
            "age_hours": f_res.age_hours,
            "freshness_status": f_res.status.value,
            "classification": classification,
            "text_quality": text_quality,
            "full_text_length": len(full_text),
            "collected_at": collected_at
        })

    earliest_pub = min(published_timestamps) if published_timestamps else None
    latest_pub = max(published_timestamps) if published_timestamps else None

    report = {
        "audit_timestamp": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_rows": total_rows,
        "production_rows": prod_rows,
        "test_or_legacy_rows": test_rows,
        "fresh_rows": fresh_count,
        "stale_rows": stale_count,
        "unknown_date_rows": unknown_date_count,
        "rejected_rows": rejected_count,
        "unique_source_urls": len(unique_source_urls),
        "unique_article_urls": len(unique_article_urls),
        "duplicate_article_urls": dup_article_urls,
        "missing_titles": missing_titles,
        "missing_publication_dates": missing_pub_dates,
        "missing_source_urls": missing_source_urls,
        "missing_article_urls": missing_article_urls,
        "ai_relevance_failures": ai_relevance_failures,
        "full_text_count": full_text_count,
        "partial_text_count": partial_text_count,
        "feed_only_count": feed_only_count,
        "article_fetch_failures": article_fetch_failures,
        "earliest_accepted_publication_timestamp": earliest_pub,
        "latest_accepted_publication_timestamp": latest_pub,
        "source_counts": source_counts,
        "source_fresh": source_fresh,
        "source_rejected": source_rejected,
        "records": audited_records
    }

    os.makedirs("data/reports", exist_ok=True)
    report_path = "data/reports/news_freshness_audit.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"News Quality Audit Report written to {report_path}")
    print(f"Total Rows: {total_rows} | Fresh (<=24h): {fresh_count} | Stale: {stale_count} | Unknown: {unknown_date_count}")

    return report

if __name__ == "__main__":
    audit_news_database()
