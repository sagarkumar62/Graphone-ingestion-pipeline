import asyncio
import sqlite3
import json
import os
from datetime import datetime
from src.storage.database import db_manager
from src.utils.normalization import (
    normalize_title,
    normalize_authors_list,
    normalize_whitespace,
    normalize_arxiv_url,
    extract_arxiv_id
)
from src.utils.hashing import compute_research_paper_hash

def is_test_record(source_url: str) -> bool:
    if not source_url:
        return True
    test_keywords = ["test-paper-", "test_id=", "test_raw_", "test_checkpoint_"]
    return any(kw in source_url for kw in test_keywords)

async def backfill_database(db_path: str = "pipeline.db"):
    print("Initializing DB schemas and migrations...")
    await db_manager.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_papers")
    rows = cursor.fetchall()

    prod_rows = [r for r in rows if not is_test_record(r["source_url"])]
    print(f"Loaded {len(prod_rows)} production research papers for backfill (excluding {len(rows) - len(prod_rows)} test fixtures).")

    updated_count = 0
    now_iso = datetime.utcnow().isoformat() + "Z"

    for r in prod_rows:
        paper_id = r["id"]
        source_url = r["source_url"]
        title = r["title"]
        authors_raw = r["authors_json"]
        published_date = r["published_date"]
        gh_url = r["github_url"]
        gh_stars = r["github_stars"]
        data_json_raw = r["data_json"]

        # 1. Extract abstract and primaryCategory from data_json if present
        abstract = None
        primary_cat = "cs.AI"
        authors = []

        try:
            authors = json.loads(authors_raw) if authors_raw else []
        except Exception:
            authors = []

        try:
            data = json.loads(data_json_raw)
            content = data.get("content", {})
            abstract = content.get("abstract")
            if content.get("primaryCategory"):
                primary_cat = content.get("primaryCategory")
            if not authors and content.get("authors"):
                authors = content.get("authors")
        except Exception:
            pass

        # 2. Compute normalized fields
        norm_title = normalize_title(title)
        arxiv_id = extract_arxiv_id(source_url)
        content_hash = compute_research_paper_hash(
            title=title,
            authors=authors,
            abstract=abstract,
            published_date=published_date,
            source_url=source_url,
            primary_category=primary_cat
        )

        # 3. Determine enrichment status
        status = "PENDING"
        if gh_stars is not None:
            status = "COMPLETED"
        elif gh_url is not None and gh_url.strip() != "":
            status = "PENDING"
        else:
            status = "NO_DATA"

        cursor.execute("""
            UPDATE research_papers
            SET arxiv_id = ?,
                normalized_title = ?,
                primary_category = ?,
                abstract = ?,
                content_hash = ?,
                enrichment_status = ?,
                enrichment_updated_at = ?
            WHERE id = ?
        """, (arxiv_id, norm_title, primary_cat, abstract, content_hash, status, now_iso, paper_id))

        updated_count += 1

    conn.commit()
    conn.close()
    print(f"Phase 6 Backfill Complete! Successfully updated {updated_count} production research papers.")

if __name__ == "__main__":
    asyncio.run(backfill_database())
