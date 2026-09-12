import sqlite3
import json
import os
import csv
import sys

def audit_database():
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = ["startups", "products", "research_papers", "jobs", "news", "entity_mappings", "canonical_entities", "dlq_records"]
    db_counts = {}
    for t in tables:
        db_counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    # Startups audit
    startups = cur.execute("SELECT * FROM startups").fetchall()
    startup_source_names = {}
    for s in startups:
        src = s["source_name"]
        startup_source_names[src] = startup_source_names.get(src, 0) + 1

    # Products audit
    products = cur.execute("SELECT * FROM products").fetchall()
    product_source_names = {}
    for p in products:
        src = p["source_name"]
        product_source_names[src] = product_source_names.get(src, 0) + 1

    # Papers audit
    papers = cur.execute("SELECT * FROM research_papers").fetchall()
    prod_papers = [p for p in papers if not ("test-paper-" in p["source_url"] or "test_" in p["source_url"])]
    unique_paper_urls = len(set(p["source_url"] for p in prod_papers))
    github_urls_count = sum(1 for p in prod_papers if p["github_url"])
    github_stars_count = sum(1 for p in prod_papers if p["github_stars"] is not None)

    # Jobs audit
    jobs = cur.execute("SELECT * FROM jobs").fetchall()
    prod_jobs = [j for j in jobs if not ("test-job-" in j["source_url"] or "test_" in j["source_url"])]

    # News audit
    news = cur.execute("SELECT * FROM news").fetchall()

    # Mappings audit
    mappings = cur.execute("SELECT * FROM entity_mappings").fetchall()

    print("=== DATABASE COUNTS ===")
    for k, v in db_counts.items():
        print(f"  {k}: {v}")

    print("\n=== STARTUPS PROVENANCE ===")
    print("  Sources:", startup_source_names)

    print("\n=== PRODUCTS PROVENANCE ===")
    print("  Sources:", product_source_names)

    print("\n=== RESEARCH PAPERS AUDIT ===")
    print(f"  Total DB rows: {len(papers)}")
    print(f"  Production papers (excluding fixtures): {len(prod_papers)}")
    print(f"  Unique paper source URLs: {unique_paper_urls}")
    print(f"  Papers with GitHub URLs: {github_urls_count}")
    print(f"  Papers with verified GitHub Stars: {github_stars_count}")

    print("\n=== JOBS AUDIT ===")
    print(f"  Total DB rows: {len(jobs)}")
    print(f"  Production jobs (excluding fixtures): {len(prod_jobs)}")

    print("\n=== NEWS AUDIT ===")
    print(f"  Total DB rows: {len(news)}")

    print("\n=== ENTITY MAPPINGS AUDIT ===")
    print(f"  Total DB mapping rows: {len(mappings)}")

def audit_exports():
    export_dir = "data/exports"
    files = {
        "startups": "startups.csv",
        "products": "products.csv",
        "research_papers": "research_papers.csv",
        "jobs": "jobs.csv",
        "news": "news.csv",
        "entity_mappings": "entity_mappings.csv"
    }

    print("\n=== EXPORT CSV ROW COUNTS (excluding header) ===")
    for k, fname in files.items():
        fpath = os.path.join(export_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                lines = list(reader)
                count = max(0, len(lines) - 1)
                print(f"  {fname}: {count} rows")
        else:
            print(f"  {fname}: NOT FOUND")

if __name__ == "__main__":
    audit_database()
    audit_exports()
