import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

def inspect_table(name):
    print(f"\n==================== TABLE: {name} ====================")
    cols = [d[0] for d in cur.execute(f"SELECT * FROM {name} LIMIT 0").description]
    print(f"COLUMNS: {cols}")
    rows = cur.execute(f"SELECT * FROM {name}").fetchall()
    print(f"TOTAL ROWS: {len(rows)}")
    for i, r in enumerate(rows):
        print(f"\nRow {i+1}:")
        for col_name, val in zip(cols, r):
            if isinstance(val, str) and len(val) > 120:
                print(f"  {col_name}: {val[:120]}... [truncated]")
            else:
                print(f"  {col_name}: {val}")

for tbl in ['startups', 'products', 'jobs', 'news']:
    inspect_table(tbl)
