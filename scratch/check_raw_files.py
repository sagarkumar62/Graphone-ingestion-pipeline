import sqlite3
import json
import os

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

raw_rows = cur.execute("SELECT source_name, source_url, raw_file_path FROM raw_payloads WHERE source_name = 'GitHub Organizations'").fetchall()
print(f"Total raw payloads for GitHub Orgs: {len(raw_rows)}")

found_files = 0
org_data_sample = []

for r in raw_rows:
    path = r[2]
    if path and os.path.exists(path):
        found_files += 1
        if len(org_data_sample) < 5:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    org_data_sample.append((r[1], data))
            except Exception as e:
                pass

print(f"Existing raw files on disk: {found_files}")

for url, data in org_data_sample:
    print("=" * 60)
    print("URL:", url)
    print("Name:", data.get("name"))
    print("Login:", data.get("login"))
    print("Company/Is Verified:", data.get("is_verified"))
    print("Blog:", data.get("blog"))
    print("Description:", data.get("description"))
    print("Keys:", list(data.keys()))

con.close()
