import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()
con.close()

sample_parsed = []
for r in rows:
    rec_id, s_name, s_url, name, dj_str = r
    try:
        dj = json.loads(dj_str)
        content = dj.get("content", {})
        sample_parsed.append({
            "id": rec_id,
            "source_name": s_name,
            "source_url": s_url,
            "entity_name": name,
            "description": content.get("description"),
            "website": content.get("website"),
            "founding_year": content.get("foundingYear"),
            "hq_location": content.get("hqLocation")
        })
    except Exception as e:
        print(f"Error parsing row {rec_id}: {e}")

with open("scratch/db_startups_parsed.json", "w", encoding="utf-8") as f:
    json.dump(sample_parsed, f, indent=2)

print(f"Successfully saved {len(sample_parsed)} parsed startup records to scratch/db_startups_parsed.json")
