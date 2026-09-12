import sqlite3
import json
import httpx
import asyncio
import re
from datetime import datetime

# Legal corporate entity suffixes (must be explicit word boundary)
LEGAL_ENTITY_REGEX = re.compile(
    r'\b(inc\.?|incorporated|corp\.?|corporation|ltd\.?|limited|gmbh|llc|c-corp|s-corp|pvt\.?\s*ltd\.?|pte\.?\s*ltd\.?|b\.?v\.?|s\.?a\.?|co\.,?\s*ltd\.?|s\.?r\.?o\.?)\b',
    re.IGNORECASE
)

# Non-startup entity keywords (academic, foundation, community, individual project, government)
NON_STARTUP_REGEX = re.compile(
    r'\b(university|univ|college|school|faculty|institute of technology|research group|academic|lab group|foundation|open source community|developer community|personal project|awesome-|curated list|learning resource|non-profit|nonprofit|government|gov|department of)\b',
    re.IGNORECASE
)

# Commercial / business indicators in description/bio
EXPLICIT_COMPANY_DESC_REGEX = re.compile(
    r'\b(venture-backed|funded startup|commercial software|enterprise platform|company building|official github org|official github organization|leading provider|headquartered in|commercial AI|corporate)\b',
    re.IGNORECASE
)

async def audit_all_startups():
    con = sqlite3.connect('pipeline.db')
    cur = con.cursor()
    rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()
    con.close()

    print(f"Auditing {len(rows)} database records...")

    accepted = []
    rejected = []

    # Map of results
    # We will fetch live GitHub org info using async httpx
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)

    # Let's inspect headers with optional GITHUB_TOKEN
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"User-Agent": "GraphOne-Audit/1.0", "Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    async with httpx.AsyncClient(limits=limits, timeout=10.0, headers=headers) as client:
        semaphore = asyncio.Semaphore(15)

        async def inspect_record(row):
            rec_id, s_name, s_url, name, d_json = row

            if "ycombinator.com" in s_url or s_name == "YC Directory":
                return {
                    "id": rec_id, "name": name, "url": s_url, "source": s_name,
                    "status": "ACCEPT", "evidence_type": "YC_DIRECTORY_RECORD",
                    "evidence_strength": "STRONG", "reason": "Verified Y Combinator directory company"
                }

            login = s_url.strip("/").split("/")[-1]
            api_url = f"https://api.github.com/orgs/{login}"

            org_data = {}
            async with semaphore:
                try:
                    res = await client.get(api_url)
                    if res.status_code == 200:
                        org_data = res.json()
                    elif res.status_code == 404:
                        # Try user endpoint if org endpoint returns 404
                        res_user = await client.get(f"https://api.github.com/users/{login}")
                        if res_user.status_code == 200:
                            org_data = res_user.json()
                except Exception as e:
                    pass

            # Fallback to data_json if API call failed
            try:
                dj = json.loads(d_json)
                content = dj.get("content", {})
            except Exception:
                content = {}

            org_name = (org_data.get("name") or name or "").strip()
            desc = (org_data.get("description") or content.get("description") or "").strip()
            blog = (org_data.get("blog") or content.get("website") or "").strip()
            company_field = (org_data.get("company") or "").strip()
            is_verified = bool(org_data.get("is_verified"))
            email = (org_data.get("email") or "").strip()

            text_combined = f"{org_name} {login} {desc} {company_field}".strip()

            # Rule Check 1: Non-startup disqualification (Academic/Foundation/Community/Personal)
            if NON_STARTUP_REGEX.search(text_combined):
                return {
                    "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
                    "status": "REJECT", "evidence_type": "ACADEMIC_OR_NON_PROFIT",
                    "evidence_strength": "WEAK", "reason": f"Non-startup entity type detected in metadata"
                }

            # Rule Check 2: Strong Evidence - Verified GitHub domain
            if is_verified:
                return {
                    "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
                    "status": "ACCEPT", "evidence_type": "VERIFIED_COMPANY_DOMAIN",
                    "evidence_strength": "STRONG", "reason": "GitHub verified corporate domain"
                }

            # Rule Check 3: Strong Evidence - Explicit legal entity suffix
            legal_match = LEGAL_ENTITY_REGEX.search(org_name) or LEGAL_ENTITY_REGEX.search(company_field)
            if legal_match:
                return {
                    "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
                    "status": "ACCEPT", "evidence_type": "EXPLICIT_LEGAL_ENTITY",
                    "evidence_strength": "STRONG", "reason": f"Explicit corporate legal entity suffix: {legal_match.group(0)}"
                }

            # Rule Check 4: Moderate Evidence - Legitimate commercial website domain AND explicit company description/profile
            has_company_desc = bool(EXPLICIT_COMPANY_DESC_REGEX.search(desc))
            has_valid_blog = bool(blog and not any(s in blog.lower() for s in ["github.io", "twitter.com", "x.com", "t.me", "discord.gg", "wikipedia.org"]))

            if has_valid_blog and has_company_desc:
                return {
                    "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
                    "status": "ACCEPT", "evidence_type": "COMMERCIAL_WEBSITE_AND_PROFILE",
                    "evidence_strength": "MODERATE", "reason": f"Official company website ({blog}) with commercial product/service description"
                }

            # Otherwise: Insufficient evidence
            return {
                "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
                "status": "REJECT", "evidence_type": "INSUFFICIENT_COMPANY_EVIDENCE",
                "evidence_strength": "WEAK", "reason": "Lacks verified domain, legal suffix, or explicit corporate evidence"
            }

        tasks = [inspect_record(r) for r in rows]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r["status"] == "ACCEPT":
                accepted.append(r)
            else:
                rejected.append(r)

    print("=" * 60)
    print(f"AUDIT SUMMARY:")
    print(f"Total Evaluated: {len(rows)}")
    print(f"Accepted Records: {len(accepted)}")
    print(f"Rejected Records: {len(rejected)}")
    print("=" * 60)

    # Save initial audit report
    with open("scratch/audit_results_test.json", "w", encoding="utf-8") as f:
        json.dump({"accepted": accepted, "rejected": rejected}, f, indent=2)

import os
if __name__ == "__main__":
    asyncio.run(audit_all_startups())
