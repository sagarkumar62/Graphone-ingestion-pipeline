import json
import re

with open("scratch/real_github_org_metadata.json", "r", encoding="utf-8") as f:
    meta_dict = json.load(f)

with open("scratch/db_startups_parsed.json", "r", encoding="utf-8") as f:
    db_records = json.load(f)

print(f"Loaded {len(db_records)} records from db_startups_parsed.json")
print(f"Loaded {len(meta_dict)} metadata entries from real_github_org_metadata.json")

# Legal corporate entity suffixes
LEGAL_ENTITY_REGEX = re.compile(
    r'\b(inc\.?|incorporated|corp\.?|corporation|ltd\.?|limited|gmbh|llc|c-corp|s-corp|pvt\.?\s*ltd\.?|pte\.?\s*ltd\.?|b\.?v\.?|s\.?a\.?|co\.,?\s*ltd\.?|s\.?r\.?o\.?|a/s|ab|oy|gmbh\s*&\s*co|kGaA)\b',
    re.IGNORECASE
)

# Academic / Foundation / Non-profit / Community keywords
NON_STARTUP_REGEX = re.compile(
    r'\b(university|univ|college|school|faculty|polytechnic|academia|institute of technology|research group|academic|lab group|foundation|open source community|developer community|personal project|awesome-|curated list|learning resource|non-profit|nonprofit|government|gov|department of|association|society)\b',
    re.IGNORECASE
)

# Commercial / company indicators in description or bio
COMMERCIAL_INDICATOR_REGEX = re.compile(
    r'\b(company|startup|venture-backed|backed by|commercial|enterprise|platform|solution|solutions|service|services|provider|product|products|headquartered|software company|tech company|ai company|cloud platform|saas|developer tool|infrastructure|analytics|security company|data platform|automation|api|agents|build|deploy|scale|open source company|infra|database|storage)\b',
    re.IGNORECASE
)

# Skip domains for blogs
SKIP_BLOGS = ["twitter.com", "x.com", "t.me", "discord.gg", "github.io", "wikipedia.org", "medium.com", "youtube.com"]

stats = {
    "total": len(db_records),
    "yc_accepted": 0,
    "verified_accepted": 0,
    "legal_suffix_accepted": 0,
    "commercial_domain_profile_accepted": 0,
    "academic_rejected": 0,
    "insufficient_rejected": 0,
    "rejected_details": []
}

accepted_records = []
rejected_records = []

for rec in db_records:
    rec_id = rec["id"]
    s_url = rec["source_url"]
    s_name = rec["source_name"]
    name = rec["entity_name"]

    meta = meta_dict.get(s_url, {})

    # 1. YC Directory Record
    if "ycombinator.com" in s_url or s_name == "YC Directory":
        stats["yc_accepted"] += 1
        accepted_records.append({
            "id": rec_id, "name": name, "url": s_url, "source": s_name,
            "evidence_type": "YC_DIRECTORY_RECORD", "evidence_strength": "STRONG",
            "reason": "Verified Y Combinator directory company"
        })
        continue

    org_name = (meta.get("name") or name or "").strip()
    login = s_url.strip("/").split("/")[-1]
    desc = (meta.get("description") or rec.get("description") or "").strip()
    company_field = (meta.get("company") or "").strip()
    blog = (meta.get("blog") or rec.get("website") or "").strip()
    is_verified = bool(meta.get("is_verified"))
    email = (meta.get("email") or "").strip()
    location = (meta.get("location") or rec.get("hq_location") or "").strip()

    combined_text = f"{org_name} {login} {desc} {company_field} {blog}".strip()

    # Rule Check 1: Non-startup disqualification (Academic/Foundation/Community/Personal)
    if NON_STARTUP_REGEX.search(combined_text):
        stats["academic_rejected"] += 1
        rejected_records.append({
            "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
            "evidence_type": "ACADEMIC_OR_NON_PROFIT", "evidence_strength": "WEAK",
            "reason": f"Non-startup academic, foundation, community, or individual project detected"
        })
        continue

    # Rule Check 2: Strong Evidence - GitHub verified domain
    if is_verified:
        stats["verified_accepted"] += 1
        accepted_records.append({
            "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
            "evidence_type": "VERIFIED_COMPANY_DOMAIN", "evidence_strength": "STRONG",
            "reason": "GitHub verified corporate domain"
        })
        continue

    # Rule Check 3: Strong Evidence - Explicit corporate legal entity suffix
    legal_match = LEGAL_ENTITY_REGEX.search(org_name) or LEGAL_ENTITY_REGEX.search(company_field)
    if legal_match:
        stats["legal_suffix_accepted"] += 1
        accepted_records.append({
            "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
            "evidence_type": "EXPLICIT_LEGAL_ENTITY", "evidence_strength": "STRONG",
            "reason": f"Explicit corporate legal entity suffix: {legal_match.group(0)}"
        })
        continue

    # Rule Check 4: Moderate Evidence - Legitimate commercial website domain AND explicit company/commercial description
    has_valid_blog = bool(blog and not any(skip in blog.lower() for skip in SKIP_BLOGS) and any(ext in blog.lower() for ext in [".com", ".ai", ".io", ".co", ".org", ".net", ".dev", ".app", ".tech", ".de", ".fr", ".uk", ".ca", ".us", ".jp", ".cn", ".in", ".eu", ".sh"]))
    has_commercial_profile = bool(COMMERCIAL_INDICATOR_REGEX.search(desc) or COMMERCIAL_INDICATOR_REGEX.search(company_field))

    if has_valid_blog and has_commercial_profile:
        stats["commercial_domain_profile_accepted"] += 1
        accepted_records.append({
            "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
            "evidence_type": "COMMERCIAL_WEBSITE_AND_PROFILE", "evidence_strength": "MODERATE",
            "reason": f"Official company domain ({blog}) and commercial software/company description"
        })
        continue

    # Fallback: Insufficient evidence
    stats["insufficient_rejected"] += 1
    rejected_records.append({
        "id": rec_id, "name": org_name, "url": s_url, "source": s_name,
        "evidence_type": "INSUFFICIENT_COMPANY_EVIDENCE", "evidence_strength": "WEAK",
        "reason": "Lacks verified domain, legal suffix, or explicit corporate profile evidence"
    })

total_accepted = len(accepted_records)
total_rejected = len(rejected_records)

print("=" * 60)
print("AUTHENTICATED GITHUB METADATA AUDIT RESULTS:")
print(f"Total Evaluated: {stats['total']}")
print(f"Total Accepted: {total_accepted}")
print(f"  - YC Directory Records: {stats['yc_accepted']}")
print(f"  - GitHub Verified Domains: {stats['verified_accepted']}")
print(f"  - Explicit Legal Entity Suffixes: {stats['legal_suffix_accepted']}")
print(f"  - Commercial Domain & Company Profile: {stats['commercial_domain_profile_accepted']}")
print(f"Total Rejected: {total_rejected}")
print(f"  - Academic / Foundation / Non-Profit / Community: {stats['academic_rejected']}")
print(f"  - Insufficient Company Evidence: {stats['insufficient_rejected']}")
print("=" * 60)

with open("scratch/audit_authenticated_summary.json", "w", encoding="utf-8") as f:
    json.dump({"stats": stats, "accepted": accepted_records, "rejected": rejected_records}, f, indent=2)

print("Saved summary to scratch/audit_authenticated_summary.json")
