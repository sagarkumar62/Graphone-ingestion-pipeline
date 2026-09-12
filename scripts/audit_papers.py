import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

rows = cur.execute("SELECT id, source_name, source_url, title, github_url, github_stars, published_date, collected_at FROM research_papers").fetchall()
print(f"TOTAL RESEARCH PAPERS: {len(rows)}")

stars_count = sum(1 for r in rows if r[5] is not None and r[5] > 0)
github_url_count = sum(1 for r in rows if r[4] is not None and str(r[4]).strip() != "")
print(f"Papers with GitHub URL: {github_url_count}")
print(f"Papers with GitHub Stars > 0: {stars_count}")

print("\nSample 5 papers:")
for r in rows[:5]:
    print(r)
