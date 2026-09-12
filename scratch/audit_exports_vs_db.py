import csv
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from datetime import datetime, timezone
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus

def audit_exports():
    export_files = {
        "startups.csv": "data/exports/startups.csv",
        "products.csv": "data/exports/products.csv",
        "research_papers.csv": "data/exports/research_papers.csv",
        "research_papers.json": "data/exports/research_papers.json",
        "jobs.csv": "data/exports/jobs.csv",
        "news.csv": "data/exports/news.csv",
        "entity_mappings.csv": "data/exports/entity_mappings.csv"
    }

    print("=" * 60)
    print("EXPORTS FILE AUDIT RESULTS:")
    for key, path in export_files.items():
        if not os.path.exists(path):
            print(f"  - {key}: MISSING ({path})")
            continue

        if path.endswith(".csv"):
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                rows = list(reader)
                print(f"  - {key}: {len(rows)} data rows (Header: {header[:4]}...)")
        elif path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                recs = data.get("records", [])
                print(f"  - {key}: {len(recs)} records in JSON payload")

    print("=" * 60)

if __name__ == "__main__":
    audit_exports()
