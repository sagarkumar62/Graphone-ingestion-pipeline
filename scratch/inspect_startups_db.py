import sqlite3
import json

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()
print(f"Total rows in startups table: {len(rows)}")

stripe_rows = [r for r in rows if 'stripe' in r[2].lower() or 'stripe' in r[3].lower()]
openai_rows = [r for r in rows if 'openai' in r[2].lower() or 'openai' in r[3].lower()]
yc_rows = [r for r in rows if 'ycombinator' in r[2].lower()]

print(f"Stripe rows count: {len(stripe_rows)}")
for r in stripe_rows:
    print("  Stripe row:", r[:4])

print(f"OpenAI rows count: {len(openai_rows)}")
for r in openai_rows:
    print("  OpenAI row:", r[:4])

print(f"YC rows count: {len(yc_rows)}")
for r in yc_rows:
    print("  YC row:", r[:4])

con.close()
