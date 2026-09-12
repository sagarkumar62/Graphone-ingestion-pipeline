import os
import sqlite3
import csv
import json

db_path = "pipeline.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. DB Integrity
cursor.execute("PRAGMA integrity_check;")
integrity = cursor.fetchone()[0]
cursor.execute("PRAGMA foreign_key_check;")
fk_check = cursor.fetchall()

print(f"=== 1. DB INTEGRITY ===")
print(f"Integrity check: {integrity}")
print(f"FK check errors: {len(fk_check)}")

# 2. Table Counts
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
print(f"\n=== 2. TABLE COUNTS ===")
counts = {}
for t in sorted(tables):
    cursor.execute(f"SELECT COUNT(*) FROM {t};")
    c = cursor.fetchone()[0]
    counts[t] = c
    print(f"Table {t}: {c} rows")

# 3. Export Counts & Quality
print(f"\n=== 3. EXPORT AUDIT ===")
export_files = [
    ("startups.csv", 1000),
    ("products.csv", 1000),
    ("research_papers.csv", 1000),
    ("jobs.csv", 1),
    ("news.csv", 1),
    ("entity_mappings.csv", 1)
]

for filename, target in export_files:
    filepath = os.path.join("data/exports", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            rows = list(reader)
            print(f"Export {filename}: {len(rows)} rows, {len(header) if header else 0} columns")
    else:
        print(f"Export {filename}: NOT FOUND")

# 4. Provenance & Duplicate Check across exports
print(f"\n=== 4. PROVENANCE & DUPLICATES IN EXPORTS ===")
for filename, _ in export_files:
    filepath = os.path.join("data/exports", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            urls = []
            missing_url = 0
            invalid_url = 0
            for r in reader:
                u = r.get("SourceURL") or r.get("source_url") or r.get("PaperURL") or r.get("url") or r.get("canonical_url")
                if not u:
                    missing_url += 1
                else:
                    urls.append(u)
                    if not u.startswith("http://") and not u.startswith("https://"):
                        invalid_url += 1
            unique_urls = set(urls)
            dups = len(urls) - len(unique_urls)
            print(f"{filename}: Total URLs={len(urls)}, Unique={len(unique_urls)}, Dups={dups}, Missing={missing_url}, Invalid={invalid_url}")

# 5. Product Sample Audit
print(f"\n=== 5. PRODUCT SAMPLE AUDIT ===")
cursor.execute("SELECT product_name, data_json, source_url FROM products LIMIT 50;")
prod_sample = cursor.fetchall()
clear_prod = 0
plausible_prod = 0
unclear_prod = 0
not_prod = 0
for name, data_str, url in prod_sample:
    desc_lower = (data_str or "").lower()
    name_lower = (name or "").lower()
    if "chatgpt" in name_lower or "producthunt" in (url or ""):
        clear_prod += 1
    elif any(k in desc_lower for k in ["agent", "tool", "framework", "library", "model", "cli", "sdk", "app", "ui", "platform", "engine", "copilot", "bot"]):
        plausible_prod += 1
    else:
        unclear_prod += 1

print(f"Sample of 50 products: Clear={clear_prod}, Plausible={plausible_prod}, Unclear={unclear_prod}, Not Product={not_prod}")

# 6. Research Papers GitHub Metrics Audit
print(f"\n=== 6. RESEARCH PAPERS METRICS ===")
cursor.execute("SELECT github_url, github_stars FROM research_papers;")
papers = cursor.fetchall()
gh_url_count = sum(1 for p in papers if p[0])
gh_star_count = sum(1 for p in papers if p[1] is not None)
print(f"Total Papers in DB: {len(papers)}")
print(f"Papers with GitHub URL: {gh_url_count}")
print(f"Papers with GitHub Stars: {gh_star_count}")

# Export research papers inspect
rp_export = "data/exports/research_papers.csv"
if os.path.exists(rp_export):
    with open(rp_export, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        exp_gh_url = sum(1 for r in reader if r.get("github_url"))
        exp_gh_stars = sum(1 for r in reader if r.get("github_stars") and r.get("github_stars") != "None" and r.get("github_stars") != "")
        print(f"Exported Papers: {len(reader)} rows | GitHub URLs: {exp_gh_url} | GitHub Stars: {exp_gh_stars}")

conn.close()
