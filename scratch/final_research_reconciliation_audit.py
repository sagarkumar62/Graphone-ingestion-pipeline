import sqlite3
import csv
import json

db_path = "pipeline.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Keywords used for fixture classification
test_keywords = ["test-paper-", "test-job-", "test_id=", "test_raw_", "test_checkpoint_", "paper/98456"]

def is_test_record(source_url):
    if not source_url:
        return True
    return any(kw in source_url for kw in test_keywords)

print("=== 1. DATABASE RECONCILIATION ===")
cur.execute("SELECT id, source_name, source_url, title, published_date, abstract FROM research_papers;")
all_db_rows = cur.fetchall()

total_db = len(all_db_rows)
fixture_rows = [r for r in all_db_rows if is_test_record(r["source_url"])]
prod_rows = [r for r in all_db_rows if not is_test_record(r["source_url"])]

print(f"Total DB rows: {total_db}")
print(f"Fixture rows: {len(fixture_rows)}")
print(f"Production rows: {len(prod_rows)}")
print(f"Reconciliation check: {len(prod_rows)} + {len(fixture_rows)} = {len(prod_rows) + len(fixture_rows)} (Matches DB Total: {total_db == len(prod_rows) + len(fixture_rows)})")

# Check Row 1
cur.execute("SELECT id, source_url, title FROM research_papers WHERE id = 1;")
row_1 = cur.fetchone()
print(f"ID 1 fixture check: source_url='{row_1['source_url']}' -> is_test={is_test_record(row_1['source_url'])}")

# Check 1706.03762
cur.execute("SELECT id, source_url, title FROM research_papers WHERE source_url LIKE '%1706.03762%';")
arxiv_transformer = cur.fetchall()
print(f"ArXiv 1706.03762 records count: {len(arxiv_transformer)}")
prod_transformer = [r for r in arxiv_transformer if not is_test_record(r['source_url'])]
print(f"Legitimate production 1706.03762 records count: {len(prod_transformer)}")

print("\n=== 2. ABSTRACT RECONCILIATION ===")
db_with_abstract = sum(1 for r in all_db_rows if r["abstract"] and r["abstract"].strip())
db_without_abstract = total_db - db_with_abstract

prod_with_abstract = sum(1 for r in prod_rows if r["abstract"] and r["abstract"].strip())
prod_without_abstract = len(prod_rows) - prod_with_abstract

fixture_with_abstract = sum(1 for r in fixture_rows if r["abstract"] and r["abstract"].strip())
fixture_without_abstract = len(fixture_rows) - fixture_with_abstract

print(f"Total DB with abstract: {db_with_abstract}, without: {db_without_abstract}")
print(f"Prod with abstract: {prod_with_abstract}, without: {prod_without_abstract}")
print(f"Fixture with abstract: {fixture_with_abstract}, without: {fixture_without_abstract}")
print(f"Prod Abstract Math Check: {prod_with_abstract} + {prod_without_abstract} = {prod_with_abstract + prod_without_abstract} (Matches Prod Total: {len(prod_rows)})")

print("\n=== 3. EXPORT RECONCILIATION ===")
csv_path = "data/exports/research_papers.csv"
json_path = "data/exports/research_papers.json"
jsonl_path = "data/exports/research_papers.jsonl"

with open(csv_path, "r", encoding="utf-8") as f:
    csv_rows = list(csv.DictReader(f))

with open(json_path, "r", encoding="utf-8") as f:
    json_data = json.load(f)
    json_records = json_data.get("records", [])

with open(jsonl_path, "r", encoding="utf-8") as f:
    jsonl_records = [json.loads(line) for line in f if line.strip()]

print(f"CSV Row Count: {len(csv_rows)}")
print(f"JSON Record Count: {len(json_records)}")
print(f"JSONL Record Count: {len(jsonl_records)}")
print(f"Counts match legitimate production: {len(csv_rows) == len(json_records) == len(jsonl_records) == len(prod_rows)}")

# Search for fixtures in exports
forbidden_terms = [
    "paperswithcode.co/paper/98456",
    "openai/gpt-4",
    "test-paper-",
    "test_id=",
    "test_raw_",
    "test_checkpoint_"
]

forbidden_matches = []
for idx, r in enumerate(csv_rows):
    row_str = json.dumps(r)
    for term in forbidden_terms:
        if term in row_str:
            forbidden_matches.append((idx + 1, term, r.get("SourceURL")))

print(f"Forbidden terms matches in export CSV: {len(forbidden_matches)}")
for fm in forbidden_matches:
    print(f"  Match in CSV row {fm[0]}: term='{fm[1]}', url='{fm[2]}'")

print("\n=== 4. PROVENANCE ===")
source_url_present = sum(1 for r in csv_rows if r.get("SourceURL"))
paper_url_present = sum(1 for r in csv_rows if r.get("PaperURL"))
source_url_valid = sum(1 for r in csv_rows if r.get("SourceURL", "").startswith("http"))
paper_url_valid = sum(1 for r in csv_rows if r.get("PaperURL", "").startswith("http"))
source_name_present = sum(1 for r in csv_rows if r.get("SourceName"))
pub_date_present = sum(1 for r in csv_rows if r.get("PublishedDate"))
title_present = sum(1 for r in csv_rows if r.get("Title"))
authors_present = sum(1 for r in csv_rows if r.get("Authors"))

print(f"SourceURL present: {source_url_present} / {len(csv_rows)}")
print(f"PaperURL present: {paper_url_present} / {len(csv_rows)}")
print(f"SourceURL valid: {source_url_valid} / {len(csv_rows)}")
print(f"PaperURL valid: {paper_url_valid} / {len(csv_rows)}")
print(f"SourceName present: {source_name_present} / {len(csv_rows)}")
print(f"PublishedDate present: {pub_date_present} / {len(csv_rows)}")
print(f"Title present: {title_present} / {len(csv_rows)}")
print(f"Authors present: {authors_present} / {len(csv_rows)}")

print("\n=== 5. ABSTRACT SOURCE INTEGRITY ===")
export_with_abstract = sum(1 for r in csv_rows if r.get("Abstract") and r.get("Abstract").strip())
export_without_abstract = len(csv_rows) - export_with_abstract

print(f"Export with abstract: {export_with_abstract}")
print(f"Export without abstract: {export_without_abstract}")

# Sample 6 abstracts
print("\nSample Exported Abstracts:")
for idx, r in enumerate(csv_rows[:6]):
    print(f"[{idx+1}] {r.get('Title')[:30]}... -> {r.get('Abstract')[:80]}...")

print("\n=== 6. GITHUB METRICS ===")
gh_urls = sum(1 for r in csv_rows if r.get("GitHubURL") and r.get("GitHubURL").strip())
gh_stars = sum(1 for r in csv_rows if r.get("GitHubStars") and r.get("GitHubStars").strip())
without_stars = len(csv_rows) - gh_stars
urls_without_stars = sum(1 for r in csv_rows if r.get("GitHubURL") and (not r.get("GitHubStars") or not r.get("GitHubStars").strip()))

print(f"Exported rows with GitHubURL: {gh_urls}")
print(f"Exported rows with GitHubStars: {gh_stars}")
print(f"Exported rows without GitHubStars: {without_stars}")
print(f"GitHub URLs that could not be enriched (URL exists but stars missing): {urls_without_stars}")

print("\n=== 7. DUPLICATION ===")
source_urls_list = [r.get("SourceURL") for r in csv_rows]
dup_source_urls = len(source_urls_list) - len(set(source_urls_list))

paper_urls_list = [r.get("PaperURL") for r in csv_rows]
dup_paper_urls = len(paper_urls_list) - len(set(paper_urls_list))

title_date_pairs = [(r.get("Title"), r.get("PublishedDate")) for r in csv_rows]
dup_title_date = len(title_date_pairs) - len(set(title_date_pairs))

print(f"Duplicate SourceURL: {dup_source_urls}")
print(f"Duplicate PaperURL: {dup_paper_urls}")
print(f"Duplicate Title + Date: {dup_title_date}")

print("\n=== 8. EXPORT FIELD QUALITY ===")
with open(csv_path, "r", encoding="utf-8") as f:
    r_csv = csv.reader(f)
    headers = next(r_csv)
    print(f"Headers ({len(headers)} cols): {headers}")

empty_cols = []
for h in headers:
    vals = [r.get(h) for r in csv_rows if r.get(h) and r.get(h).strip()]
    if len(vals) == 0:
        empty_cols.append(h)

print(f"Completely empty columns: {empty_cols}")

conn.close()
