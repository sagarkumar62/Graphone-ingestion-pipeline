import sqlite3
import csv
import json

db_path = "pipeline.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== PART A & B: DB ABSTRACT ANALYSIS ===")
cur.execute("SELECT id, source_name, source_url, title, abstract FROM research_papers;")
all_papers = cur.fetchall()

total_db = len(all_papers)
db_non_empty_abstract = sum(1 for p in all_papers if p["abstract"] and p["abstract"].strip())
db_empty_abstract = total_db - db_non_empty_abstract

def is_test_record(source_url):
    if not source_url:
        return True
    test_keywords = ["test-paper-", "test-job-", "test_id=", "test_raw_", "test_checkpoint_"]
    return any(kw in source_url for kw in test_keywords)

test_records = [p for p in all_papers if is_test_record(p["source_url"])]
prod_records = [p for p in all_papers if not is_test_record(p["source_url"])]

prod_non_empty_abstract = sum(1 for p in prod_records if p["abstract"] and p["abstract"].strip())
prod_empty_abstract = len(prod_records) - prod_non_empty_abstract

print(f"Total DB rows: {total_db}")
print(f"DB rows with non-empty abstract: {db_non_empty_abstract}")
print(f"DB rows with empty/null abstract: {db_empty_abstract}")
print(f"Test records count: {len(test_records)}")
print(f"Prod records count in DB: {len(prod_records)}")
print(f"Prod DB rows with non-empty abstract: {prod_non_empty_abstract}")
print(f"Prod DB rows with empty abstract: {prod_empty_abstract}")

print("\n=== CSV ABSTRACT ANALYSIS ===")
csv_path = "data/exports/research_papers.csv"
with open(csv_path, "r", encoding="utf-8") as f:
    csv_rows = list(csv.DictReader(f))

csv_total = len(csv_rows)
csv_non_empty_abstract = sum(1 for r in csv_rows if r.get("Abstract") and r.get("Abstract").strip())
csv_empty_abstract = csv_total - csv_non_empty_abstract

print(f"CSV Total rows: {csv_total}")
print(f"CSV rows with non-empty abstract: {csv_non_empty_abstract}")
print(f"CSV rows with empty abstract: {csv_empty_abstract}")

print("\n=== PART C: ROW ID 1 FORENSIC ANALYSIS ===")
cur.execute("SELECT * FROM research_papers WHERE id = 1;")
row_1_db = cur.fetchone()
print("DB Row 1:")
if row_1_db:
    for k in row_1_db.keys():
        print(f"  {k}: {row_1_db[k]}")

row_1_csv = csv_rows[0] if csv_rows else {}
print("\nCSV Row 1:")
for k, v in row_1_csv.items():
    print(f"  {k}: {v}")

# Find Attention Is All You Need records in DB
cur.execute("SELECT id, source_name, source_url, title, published_date, github_url, github_stars, abstract FROM research_papers WHERE title LIKE '%Attention Is All You Need%';")
attention_records = cur.fetchall()
print(f"\nAll 'Attention Is All You Need' records in DB ({len(attention_records)}):")
for r in attention_records:
    print(dict(r))

print("\n=== PART D: COMPLETE DB RECONCILIATION ===")
# Let's inspect all 1095 DB rows and see why 1070 was reported vs 1009 exported
# Check how many rows in DB match various criteria
print(f"Total DB rows: {len(all_papers)}")
print(f"Test records (is_test_record = True): {len(test_records)}")
print(f"Prod records (is_test_record = False): {len(prod_records)}")
print(f"Exported count in CSV: {len(csv_rows)}")
print(f"Difference (Prod DB - Exported): {len(prod_records) - len(csv_rows)}")

# Let's inspect if any prod records are not in CSV or vice-versa
exported_ids = set(int(r["ID"]) for r in csv_rows)
prod_ids = set(p["id"] for p in prod_records)
test_ids = set(p["id"] for p in test_records)

unexported_prod_ids = prod_ids - exported_ids
exported_test_ids = test_ids & exported_ids

print(f"Unexported Prod IDs count: {len(unexported_prod_ids)}")
print(f"Unexported Prod IDs list: {sorted(list(unexported_prod_ids))}")
print(f"Exported Test IDs count: {len(exported_test_ids)}")

if unexported_prod_ids:
    print("\nSample of Unexported Prod IDs:")
    cur.execute(f"SELECT id, source_name, source_url, title FROM research_papers WHERE id IN ({','.join(map(str, sorted(list(unexported_prod_ids))[:10]))});")
    for r in cur.fetchall():
        print(dict(r))

print("\n=== PART E: DATA QUALITY OF EXPORTED 1009 ROWS ===")
valid_title = sum(1 for r in csv_rows if r.get("Title") and r.get("Title").strip())
valid_authors = sum(1 for r in csv_rows if r.get("Authors") and r.get("Authors").strip())
valid_pub_date = sum(1 for r in csv_rows if r.get("PublishedDate") and r.get("PublishedDate").strip())
valid_source_url = sum(1 for r in csv_rows if r.get("SourceURL") and r.get("SourceURL").startswith("http"))
valid_paper_url = sum(1 for r in csv_rows if r.get("PaperURL") and r.get("PaperURL").startswith("http"))
gh_url_cnt = sum(1 for r in csv_rows if r.get("GitHubURL") and r.get("GitHubURL").strip())
gh_star_cnt = sum(1 for r in csv_rows if r.get("GitHubStars") and r.get("GitHubStars").strip())

urls = [r.get("SourceURL") for r in csv_rows]
dup_urls = len(urls) - len(set(urls))

title_dates = [(r.get("Title"), r.get("PublishedDate")) for r in csv_rows]
dup_title_dates = len(title_dates) - len(set(title_dates))

suspicious_fixtures = sum(1 for r in csv_rows if is_test_record(r.get("SourceURL")))

print(f"Valid Title count: {valid_title} / {csv_total}")
print(f"Valid Authors count: {valid_authors} / {csv_total}")
print(f"Valid PublishedDate count: {valid_pub_date} / {csv_total}")
print(f"Valid SourceURL count: {valid_source_url} / {csv_total}")
print(f"Valid PaperURL count: {valid_paper_url} / {csv_total}")
print(f"Non-empty Abstract count: {csv_non_empty_abstract} / {csv_total}")
print(f"GitHub URL count: {gh_url_cnt} / {csv_total}")
print(f"GitHub Stars count: {gh_star_cnt} / {csv_total}")
print(f"Duplicate SourceURL count: {dup_urls}")
print(f"Duplicate Title+Date count: {dup_title_dates}")
print(f"Suspicious/Test Fixture count in Export: {suspicious_fixtures}")

conn.close()
