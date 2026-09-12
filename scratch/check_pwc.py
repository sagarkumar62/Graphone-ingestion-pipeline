import sqlite3

conn = sqlite3.connect("pipeline.db")
cur = conn.cursor()
cur.execute("SELECT id, source_name, source_url, title FROM research_papers WHERE source_name = 'PapersWithCode' OR source_url LIKE '%paperswithcode%';")
rows = cur.fetchall()
print(f"PapersWithCode records in DB ({len(rows)}):")
for r in rows:
    print(r)
conn.close()
