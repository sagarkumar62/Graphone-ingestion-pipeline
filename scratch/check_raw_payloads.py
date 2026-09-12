import sqlite3
import json
import os

con = sqlite3.connect('pipeline.db')
cur = con.cursor()
rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()

print(f"Loaded {len(rows)} records from pipeline.db")

# Let's inspect raw_payloads table if it exists
tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in pipeline.db:", tables)

if "raw_payloads" in tables:
    raw_rows = cur.execute("SELECT source_url, content_type, length(raw_content) FROM raw_payloads").fetchall()
    print(f"Total raw payloads: {len(raw_rows)}")

con.close()
