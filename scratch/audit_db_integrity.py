import sqlite3
import json
import os

def audit_db():
    db_path = "pipeline.db"
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1. SQLite integrity check
    cur.execute("PRAGMA integrity_check")
    integrity_res = cur.fetchall()
    integrity_ok = all(r[0] == "ok" for r in integrity_res)

    # 2. Foreign key check
    cur.execute("PRAGMA foreign_key_check")
    fk_res = cur.fetchall()
    fk_ok = len(fk_res) == 0

    # 3. Table list
    tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    # 4. Table counts and detail analysis
    table_counts = {}
    table_details = {}

    for tbl in tables:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = cur.fetchone()[0]
        table_counts[tbl] = cnt

    # Table breakdown for main datasets
    # Startups
    startups_rows = cur.execute("SELECT * FROM startups").fetchall()
    startups_unique_urls = set(r["source_url"] for r in startups_rows)
    startups_missing_urls = sum(1 for r in startups_rows if not r["source_url"])
    startups_invalid_urls = sum(1 for r in startups_rows if r["source_url"] and not r["source_url"].startswith("http"))

    # Products
    products_rows = cur.execute("SELECT * FROM products").fetchall()
    products_unique_urls = set(r["source_url"] for r in products_rows)
    products_missing_urls = sum(1 for r in products_rows if not r["source_url"])
    products_invalid_urls = sum(1 for r in products_rows if r["source_url"] and not r["source_url"].startswith("http"))

    # Research Papers
    papers_rows = cur.execute("SELECT * FROM research_papers").fetchall()
    papers_test_fixtures = [r for r in papers_rows if r["source_url"] and "test-paper-" in r["source_url"]]
    papers_prod_rows = [r for r in papers_rows if not (r["source_url"] and "test-paper-" in r["source_url"])]
    papers_unique_urls = set(r["source_url"] for r in papers_prod_rows)
    papers_missing_urls = sum(1 for r in papers_prod_rows if not r["source_url"])
    papers_invalid_urls = sum(1 for r in papers_prod_rows if r["source_url"] and not r["source_url"].startswith("http"))
    papers_with_github = sum(1 for r in papers_prod_rows if r["github_url"] and r["github_url"].strip() != "")
    papers_with_stars = sum(1 for r in papers_prod_rows if r["github_stars"] is not None)

    # Jobs
    jobs_rows = cur.execute("SELECT * FROM jobs").fetchall()
    jobs_test_fixtures = [r for r in jobs_rows if r["source_url"] and "test-job-" in r["source_url"]]
    jobs_prod_rows = [r for r in jobs_rows if not (r["source_url"] and "test-job-" in r["source_url"])]
    jobs_unique_urls = set(r["source_url"] for r in jobs_prod_rows)
    jobs_missing_urls = sum(1 for r in jobs_prod_rows if not r["source_url"])
    jobs_invalid_urls = sum(1 for r in jobs_prod_rows if r["source_url"] and not r["source_url"].startswith("http"))
    jobs_missing_dates = sum(1 for r in jobs_prod_rows if not r["published_date"] or r["published_date"].strip() == "")

    # News
    news_rows = cur.execute("SELECT * FROM news").fetchall()
    news_test_fixtures = [r for r in news_rows if r["source_url"] and ("test-news-" in r["source_url"] or "test_" in r["source_url"])]
    news_prod_rows = [r for r in news_rows if not (r["source_url"] and ("test-news-" in r["source_url"] or "test_" in r["source_url"]))]
    news_unique_urls = set(r["source_url"] for r in news_prod_rows)
    news_missing_urls = sum(1 for r in news_prod_rows if not r["source_url"])
    news_invalid_urls = sum(1 for r in news_prod_rows if r["source_url"] and not r["source_url"].startswith("http"))
    news_missing_dates = sum(1 for r in news_prod_rows if not r["published_date"] or r["published_date"].strip() == "")

    # Entity Mappings
    mappings_rows = cur.execute("SELECT * FROM entity_mappings").fetchall()

    con.close()

    print("=" * 60)
    print("DATABASE INTEGRITY AUDIT RESULTS:")
    print(f"SQLite Integrity: {'OK' if integrity_ok else 'FAILED'}")
    print(f"Foreign Key Integrity: {'OK' if fk_ok else 'FAILED'}")
    print(f"Tables Present: {tables}")
    print("\nTable Row Counts:")
    for tbl, cnt in table_counts.items():
        print(f"  - {tbl}: {cnt}")

    print("\nPhase I Dataset Details:")
    print(f"  Startups DB Rows: {len(startups_rows)} | Unique URLs: {len(startups_unique_urls)} | Missing URLs: {startups_missing_urls} | Invalid URLs: {startups_invalid_urls}")
    print(f"  Products DB Rows: {len(products_rows)} | Unique URLs: {len(products_unique_urls)} | Missing URLs: {products_missing_urls} | Invalid URLs: {products_invalid_urls}")
    print(f"  Research Papers DB Rows: {len(papers_rows)} (Production: {len(papers_prod_rows)}, Test Fixtures: {len(papers_test_fixtures)}) | Unique Prod URLs: {len(papers_unique_urls)} | Missing URLs: {papers_missing_urls} | Invalid URLs: {papers_invalid_urls} | GitHub URLs: {papers_with_github} | GitHub Stars: {papers_with_stars}")

    print("\nPhase II Dataset Details:")
    print(f"  Jobs DB Rows: {len(jobs_rows)} (Production: {len(jobs_prod_rows)}, Test Fixtures: {len(jobs_test_fixtures)}) | Unique Prod URLs: {len(jobs_unique_urls)} | Missing URLs: {jobs_missing_urls} | Invalid URLs: {jobs_invalid_urls} | Missing Dates: {jobs_missing_dates}")
    print(f"  News DB Rows: {len(news_rows)} (Production: {len(news_prod_rows)}, Test Fixtures: {len(news_test_fixtures)}) | Unique Prod URLs: {len(news_unique_urls)} | Missing URLs: {news_missing_urls} | Invalid URLs: {news_invalid_urls} | Missing Dates: {news_missing_dates}")

    print(f"\nPhase IV Entity Mappings Count: {len(mappings_rows)}")
    print("=" * 60)

if __name__ == "__main__":
    audit_db()
