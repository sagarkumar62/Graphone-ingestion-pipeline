import sqlite3
import csv
import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus

def is_test_record(source_url: str) -> bool:
    if not source_url:
        return True
    test_keywords = ["test-paper-", "test-job-", "test_id=", "test_raw_", "test_checkpoint_", "paper/98456"]
    return any(kw in source_url for kw in test_keywords)

def export_all_tabs(output_dir="data/exports"):
    os.makedirs(output_dir, exist_ok=True)
    con = sqlite3.connect("pipeline.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Startups
    startups_file = os.path.join(output_dir, "startups.csv")
    with open(startups_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SchemaVersion", "SourceName", "SourceURL", "StartupName", "EmployeeCount", "FundingTotalUSD", "CollectedAt"])
        rows = cur.execute("SELECT id, schema_version, source_name, source_url, entity_name, employee_count, funding_total_usd, collected_at FROM startups").fetchall()
        for r in rows:
            writer.writerow(list(r))
    print(f"Exported Startups: {len(rows)} rows -> {startups_file}")

    # 2. Products
    products_file = os.path.join(output_dir, "products.csv")
    with open(products_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SchemaVersion", "SourceName", "SourceURL", "ProductName", "StartupName", "PricingModel", "CollectedAt"])
        rows = cur.execute("SELECT id, schema_version, source_name, source_url, product_name, startup_name, pricing_model, collected_at FROM products").fetchall()
        for r in rows:
            writer.writerow(list(r))
    print(f"Exported Products: {len(rows)} rows -> {products_file}")

    # 3. Research Papers (Production Only, excluding test fixtures)
    all_papers = cur.execute("SELECT * FROM research_papers").fetchall()
    prod_papers = [r for r in all_papers if not is_test_record(r["source_url"])]

    # 3a. CSV Export
    papers_csv = os.path.join(output_dir, "research_papers.csv")
    with open(papers_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "ArXivID", "SchemaVersion", "SourceName", "SourceURL", "Title", "NormalizedTitle", "Authors", "PaperURL", "GitHubURL", "GitHubStars", "PrimaryCategory", "Abstract", "ContentHash", "EnrichmentStatus", "PublishedDate", "CollectedAt"])
        for r in prod_papers:
            authors_str = ""
            try:
                authors = json.loads(r["authors_json"])
                authors_str = "; ".join(authors) if isinstance(authors, list) else str(authors)
            except Exception:
                pass
            writer.writerow([
                r["id"],
                r["arxiv_id"] or "",
                r["schema_version"],
                r["source_name"],
                r["source_url"],
                r["title"],
                r["normalized_title"] or "",
                authors_str,
                r["paper_url"],
                r["github_url"] or "",
                r["github_stars"] if r["github_stars"] is not None else "",
                r["primary_category"] or "cs.AI",
                (r["abstract"] or "").replace("\n", " "),
                r["content_hash"] or "",
                r["enrichment_status"] or "PENDING",
                r["published_date"],
                r["collected_at"]
            ])
    print(f"Exported Production Research Papers CSV: {len(prod_papers)} rows -> {papers_csv}")

    # 3b. JSON & JSONL Export
    json_records = []
    for r in prod_papers:
        authors = []
        try:
            authors = json.loads(r["authors_json"])
        except Exception:
            pass

        rec_dict = {
            "id": r["id"],
            "arxiv_id": r["arxiv_id"],
            "source_name": r["source_name"],
            "source_url": r["source_url"],
            "title": r["title"],
            "normalized_title": r["normalized_title"],
            "authors": authors,
            "paper_url": r["paper_url"],
            "github_url": r["github_url"],
            "github_stars": r["github_stars"],
            "primary_category": r["primary_category"],
            "abstract": r["abstract"],
            "content_hash": r["content_hash"],
            "enrichment_status": r["enrichment_status"],
            "published_date": r["published_date"],
            "collected_at": r["collected_at"]
        }
        json_records.append(rec_dict)

    # JSON export with top-level metadata
    papers_json = os.path.join(output_dir, "research_papers.json")
    json_payload = {
        "metadata": {
            "generated_at": now_iso,
            "record_count": len(json_records),
            "schema_version": "1.0",
            "source_coverage": ["arXiv"]
        },
        "records": json_records
    }
    with open(papers_json, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)
    print(f"Exported Production Research Papers JSON: {len(json_records)} records -> {papers_json}")

    # JSONL export
    papers_jsonl = os.path.join(output_dir, "research_papers.jsonl")
    with open(papers_jsonl, "w", encoding="utf-8") as f:
        for rec in json_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Exported Production Research Papers JSONL: {len(json_records)} records -> {papers_jsonl}")

    # 4. Jobs (Production Fresh Only - posted within last 24h)
    now_utc = datetime.now(timezone.utc)
    jobs_file = os.path.join(output_dir, "jobs.csv")
    all_jobs = cur.execute("SELECT id, schema_version, source_name, source_url, company, published_date, is_remote, role_family, collected_at FROM jobs").fetchall()
    
    fresh_jobs = []
    for r in all_jobs:
        if is_test_record(r["source_url"]):
            continue
        res = freshness_validator.evaluate_freshness(r["published_date"], reference_now=now_utc)
        if res.status == FreshnessStatus.FRESH:
            fresh_jobs.append(r)

    with open(jobs_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SchemaVersion", "SourceName", "SourceURL", "Company", "PublishedDate", "IsRemote", "RoleFamily", "CollectedAt"])
        for r in fresh_jobs:
            writer.writerow(list(r))
    print(f"Exported 24-Hour Fresh Jobs: {len(fresh_jobs)} rows -> {jobs_file}")

    # 5. News (Production Fresh Only - published within last 24h)
    news_file = os.path.join(output_dir, "news.csv")
    all_news = cur.execute("SELECT id, schema_version, source_name, source_url, title, summary, published_date, collected_at FROM news").fetchall()

    fresh_news = []
    for r in all_news:
        if is_test_record(r["source_url"]):
            continue
        res = freshness_validator.evaluate_freshness(r["published_date"], reference_now=now_utc)
        if res.status == FreshnessStatus.FRESH:
            fresh_news.append(r)

    with open(news_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SchemaVersion", "SourceName", "SourceURL", "Title", "Summary", "PublishedDate", "CollectedAt"])
        for r in fresh_news:
            writer.writerow(list(r))
    print(f"Exported 24-Hour Fresh News: {len(fresh_news)} rows -> {news_file}")

    # 6. Entity Mapping Log
    mappings_file = os.path.join(output_dir, "entity_mappings.csv")
    with open(mappings_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "MappingID", "EntityType", "RawValue", "NormalizedValue", "CanonicalValue", "Decision", "MatchMethod", "Confidence", "SourceURL", "Timestamp"])
        rows = cur.execute("SELECT id, mapping_id, entity_type, raw_value, normalized_value, canonical_value, decision, match_method, confidence, source_url, timestamp FROM entity_mappings").fetchall()
        for r in rows:
            writer.writerow(list(r))
    print(f"Exported Entity Mappings: {len(rows)} rows -> {mappings_file}")

def export_startups_only(output_dir="data/exports"):
    os.makedirs(output_dir, exist_ok=True)
    con = sqlite3.connect("pipeline.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    startups_file = os.path.join(output_dir, "startups.csv")
    with open(startups_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "SchemaVersion", "SourceName", "SourceURL", "StartupName", "EmployeeCount", "FundingTotalUSD", "CollectedAt"])
        rows = cur.execute("SELECT id, schema_version, source_name, source_url, entity_name, employee_count, funding_total_usd, collected_at FROM startups").fetchall()
        for r in rows:
            writer.writerow(list(r))
    print(f"Exported Startups Only: {len(rows)} rows -> {startups_file}")
    con.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export Sheets Data")
    parser.add_argument("--startups-only", action="store_true", help="Export startups.csv only")
    args = parser.parse_args()

    if args.startups_only:
        export_startups_only()
    else:
        export_all_tabs()
