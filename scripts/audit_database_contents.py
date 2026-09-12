import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("TABLES FOUND IN pipeline.db:")
for t in tables:
    count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  - {t}: {count} rows")

print("\n--- SAMPLE ROWS / STATS ---")
for t in tables:
    rows = cur.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
    print(f"\n--- {t} (first {len(rows)}) ---")
    for r in rows:
        print(r)
