import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()

print(f"Total startup rows in DB: {len(rows)}")

keys_in_content = set()
keys_in_data = set()

for r in rows:
    try:
        dj = json.loads(r[4])
        content = dj.get("content", {})
        keys_in_content.update(content.keys())
        data_obj = content.get("data", {})
        if isinstance(data_obj, dict):
            keys_in_data.update(data_obj.keys())
    except Exception:
        pass

print("Keys in content:", keys_in_content)
print("Keys in content.data:", keys_in_data)

con.close()
