import sqlite3
import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from src.sources.startup_sources import GitHubOrganizationsStartupSource

def clean_and_sync_startups():
    with open("scratch/audit_authenticated_summary.json", "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    accepted_list = audit_data.get("accepted", [])
    accepted_urls = set(r["url"] for r in accepted_list)

    print(f"Loaded {len(accepted_urls)} defensible accepted URLs from audit.")

    con = sqlite3.connect("pipeline.db")
    cur = con.cursor()

    cur.execute("SELECT id, source_name, source_url, entity_name FROM startups")
    all_rows = cur.fetchall()

    print(f"Current database startup rows: {len(all_rows)}")

    rows_to_delete = [r for r in all_rows if r[2] not in accepted_urls]
    rows_to_keep = [r for r in all_rows if r[2] in accepted_urls]

    print(f"Rows to keep: {len(rows_to_keep)}")
    print(f"Rows to remove: {len(rows_to_delete)}")

    if rows_to_delete:
        delete_ids = [r[0] for r in rows_to_delete]
        cur.executemany("DELETE FROM startups WHERE id = ?", [(i,) for i in delete_ids])
        con.commit()
        print(f"Deleted {len(delete_ids)} non-defensible startup records from pipeline.db.")

    cur.execute("SELECT COUNT(*) FROM startups")
    final_count = cur.fetchone()[0]
    print(f"Final pipeline.db startups count: {final_count}")

    con.close()

if __name__ == "__main__":
    clean_and_sync_startups()
