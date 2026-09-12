import sqlite3
import json
import re

def is_defensible_startup(org_data: dict, name: str, url: str) -> tuple[bool, str]:
    if not isinstance(org_data, dict):
        org_data = {}

    name = (name or org_data.get("name") or "").strip()
    blog = (org_data.get("blog") or "").strip()
    desc = (org_data.get("description") or "").strip()
    is_verified = bool(org_data.get("is_verified"))

    # Rule 1: YC directory record
    if "ycombinator.com" in url:
        return True, "YC_DIRECTORY_RECORD"

    # Rule 2: Verified GitHub company domain
    if is_verified:
        return True, "VERIFIED_COMPANY_DOMAIN"

    # Rule 3: Company website domain present (e.g. blog has http/https domain)
    if blog and not any(skip in blog.lower() for skip in ["twitter.com", "x.com", "t.me", "discord.gg", "github.io"]):
        if any(ext in blog.lower() for ext in [".com", ".ai", ".io", ".co", ".org", ".net", ".dev", ".app", ".tech", ".de", ".fr", ".uk"]):
            return True, "COMPANY_WEBSITE_DOMAIN"

    # Rule 4: Explicit company keywords in name or description
    text_to_search = (name + " " + desc).lower()
    company_keywords = [
        r"\binc\b", r"\bcorp\b", r"\bcorporation\b", r"\bltd\b", r"\bgmbh\b", r"\bllc\b",
        r"\blabs\b", r"\blab\b", r"\btechnologies\b", r"\btechnology\b", r"\bsolutions\b",
        r"\bcompany\b", r"\bstartup\b", r"\bplatform\b", r"\bsoftware\b", r"\bsystems\b",
        r"\bventures\b", r"\bstudio\b", r"\bintelligence\b", r"\benterprise\b", r"\bcloud\b",
        r"\b Security\b", r"\b data\b", r"\bai\b"
    ]
    for kw in company_keywords:
        if re.search(kw, text_to_search):
            return True, f"COMPANY_KEYWORD_MATCH({kw})"

    return False, "INSUFFICIENT_COMPANY_EVIDENCE"

def test_filtering():
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("SELECT * FROM startups").fetchall()
    print(f"Auditing {len(rows)} existing startups in pipeline.db...")

    accepted = 0
    rejected = 0
    reasons = {}

    for r in rows:
        url = r["source_url"]
        name = r["entity_name"]
        data_json = json.loads(r["data_json"]) if r["data_json"] else {}
        content = data_json.get("content", {})
        org_data = {
            "name": name,
            "blog": content.get("website"),
            "description": content.get("description"),
            "is_verified": False
        }

        is_keep, reason = is_defensible_startup(org_data, name, url)
        reasons[reason] = reasons.get(reason, 0) + 1
        if is_keep:
            accepted += 1
        else:
            rejected += 1

    print(f"Results: Total={len(rows)}, Accepted={accepted}, Rejected/Excluded={rejected}")
    print("Breakdown by reason:", json.dumps(reasons, indent=2))

if __name__ == "__main__":
    test_filtering()
