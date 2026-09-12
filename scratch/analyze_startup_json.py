import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups LIMIT 10').fetchall()

for r in rows:
    print("=" * 60)
    print(f"ID: {r[0]} | Source: {r[1]} | URL: {r[2]} | Name: {r[3]}")
    try:
        dj = json.loads(r[4])
        print("Data JSON keys:", list(dj.keys()))
        print("Content:", json.dumps(dj.get("content", {}), indent=2))
    except Exception as e:
        print("Error parsing data_json:", e)

con.close()
