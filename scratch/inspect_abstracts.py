import sqlite3
import json

conn = sqlite3.connect("pipeline.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, source_name, source_url, title, data_json, abstract FROM research_papers;")
rows = cur.fetchall()

has_abstract_in_json = 0
sample_abstracts = []

for r in rows:
    data_str = r["data_json"]
    if data_str:
        try:
            data = json.loads(data_str)
            # check content.abstract or content.summary
            content = data.get("content", {})
            abs_val = content.get("abstract") or content.get("summary") or data.get("abstract") or data.get("summary")
            if abs_val and str(abs_val).strip():
                has_abstract_in_json += 1
                if len(sample_abstracts) < 5:
                    sample_abstracts.append((r["id"], r["title"], abs_val[:100]))
        except Exception as e:
            pass

print(f"Total DB Rows: {len(rows)}")
print(f"Rows with non-empty abstract in data_json: {has_abstract_in_json}")
print("\nSample abstracts from data_json:")
for sid, title, ab in sample_abstracts:
    print(f"ID {sid} ({title[:30]}...): {ab}...")

conn.close()
