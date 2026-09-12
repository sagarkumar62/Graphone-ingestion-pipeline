import sqlite3
import json

conn = sqlite3.connect("pipeline.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def is_test_record(source_url):
    if not source_url:
        return True
    test_keywords = ["test-paper-", "test-job-", "test_id=", "test_raw_", "test_checkpoint_", "paper/98456"]
    return any(kw in source_url for kw in test_keywords)

cur.execute("SELECT id, source_url, title, data_json FROM research_papers;")
rows = cur.fetchall()

prod_rows = [r for r in rows if not is_test_record(r["source_url"])]
prod_with_abstract = 0
prod_without_abstract = 0

for r in prod_rows:
    data_str = r["data_json"]
    abs_val = None
    if data_str:
        try:
            data = json.loads(data_str)
            content = data.get("content", {})
            abs_val = content.get("abstract") or content.get("summary") or data.get("abstract")
        except Exception:
            pass
    if abs_val and str(abs_val).strip():
        prod_with_abstract += 1
    else:
        prod_without_abstract += 1

print(f"Production rows count: {len(prod_rows)}")
print(f"Production rows with non-empty abstract in data_json: {prod_with_abstract}")
print(f"Production rows without abstract in data_json: {prod_without_abstract}")

conn.close()
