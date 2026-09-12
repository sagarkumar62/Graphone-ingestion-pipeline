import sqlite3

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("COUNTS PER TABLE IN pipeline.db:")
for t in sorted(tables):
    count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {count}")

# Check entity mapping log count
if 'entity_mappings' in tables:
    em_count = cur.execute("SELECT count(*) FROM entity_mappings").fetchone()[0]
    print(f"\nTotal Entity Mappings: {em_count}")

# Check deduplication store
if 'deduplication_store' in tables:
    ds_count = cur.execute("SELECT count(*) FROM deduplication_store").fetchone()[0]
    print(f"Total Dedup Fingerprints: {ds_count}")
