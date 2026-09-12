import sqlite3

con = sqlite3.connect('pipeline.db')
cur = con.cursor()

def audit_table(table_name):
    cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cols = [d[0] for d in cur.description]
    
    url_col = 'source_url' if 'source_url' in cols else ('url' if 'url' in cols else None)
    
    rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
    total = len(rows)
    
    verified_sources = set()
    suspect_legacy = 0
    legit_count = 0
    
    url_idx = cols.index(url_col) if url_col else None
    
    for r in rows:
        url = r[url_idx] if url_idx is not None else ""
        if url:
            if any(k in url for k in ["test-paper-", "test_id=", "test_raw_", "test_checkpoint_"]):
                suspect_legacy += 1
            else:
                legit_count += 1
                verified_sources.add(url)
        else:
            suspect_legacy += 1
            
    return total, len(verified_sources), suspect_legacy, legit_count

tables = ['startups', 'products', 'research_papers', 'jobs', 'news', 'entity_mappings']
print(f"{'TABLE':<20} | {'RECORD COUNT':<12} | {'VERIFIED SOURCES':<16} | {'SUSPECT/LEGACY':<14} | {'LEGITIMATE RECORDS':<18}")
print("-" * 88)

for t in tables:
    total, v_src, susp, legit = audit_table(t)
    print(f"{t:<20} | {total:<12} | {v_src:<16} | {susp:<14} | {legit:<18}")
