import sqlite3
import json

def backfill_abstracts(db_path: str = "pipeline.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, data_json FROM research_papers;")
    rows = cur.fetchall()

    updated_abstracts = 0
    updated_categories = 0

    for r in rows:
        data_str = r["data_json"]
        if not data_str:
            continue

        try:
            data = json.loads(data_str)
            content = data.get("content", {})
            abstract_val = content.get("abstract") or content.get("summary") or data.get("abstract") or data.get("summary")
            category_val = content.get("primaryCategory") or data.get("primaryCategory") or "cs.AI"

            if abstract_val and str(abstract_val).strip():
                cur.execute("UPDATE research_papers SET abstract = ?, primary_category = ? WHERE id = ?;", (str(abstract_val).strip(), category_val, r["id"]))
                updated_abstracts += 1
        except Exception as e:
            print(f"Error processing row {r['id']}: {e}")

    conn.commit()
    print(f"Successfully backfilled abstracts for {updated_abstracts} research paper records in {db_path}.")
    conn.close()

if __name__ == "__main__":
    backfill_abstracts()
