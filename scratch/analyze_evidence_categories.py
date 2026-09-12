import json
import re

with open("scratch/fetched_org_details.json", "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Total records in cache: {len(records)}")

yc_records = [r for r in records if r.get("is_yc")]
gh_records = [r for r in records if not r.get("is_yc")]

print(f"YC records: {len(yc_records)}")
print(f"GitHub org records: {len(gh_records)}")

# 1. Check verified orgs
verified_orgs = [r for r in gh_records if r.get("org_data", {}).get("is_verified")]
print(f"GitHub verified orgs (is_verified=True): {len(verified_orgs)}")

# 2. Academic / University / School / Institute / Research Lab / Government / Non-profit / Community keywords
ACADEMIC_NONPROFIT_REGEX = re.compile(
    r'\b(university|univ|college|school|faculty|polytechnic|academia|institute of technology|research group|academic|lab group|foundation|open source community|developer community|personal project|awesome-|curated list|learning resource|non-profit|nonprofit|government|gov|department of|association)\b',
    re.IGNORECASE
)

academic_nonprofit_list = []
for r in gh_records:
    o = r.get("org_data", {})
    name = (o.get("name") or r.get("name") or "").strip()
    login = (r.get("login") or "").strip()
    desc = (o.get("description") or "").strip()
    company = (o.get("company") or "").strip()
    blog = (o.get("blog") or "").strip()

    combined_text = f"{name} {login} {desc} {company} {blog}"
    if ACADEMIC_NONPROFIT_REGEX.search(combined_text):
        academic_nonprofit_list.append(r)

print(f"Academic / University / Foundation / Non-profit / Community orgs: {len(academic_nonprofit_list)}")

# 3. Explicit legal entity suffixes
LEGAL_ENTITY_REGEX = re.compile(
    r'\b(inc\.?|incorporated|corp\.?|corporation|ltd\.?|limited|gmbh|llc|c-corp|s-corp|pvt\.?\s*ltd\.?|pte\.?\s*ltd\.?|b\.?v\.?|s\.?a\.?|co\.,?\s*ltd\.?|s\.?r\.?o\.?|a/s|ab|oy|gmbh\s*&\s*co|kGaA)\b',
    re.IGNORECASE
)

legal_suffix_list = []
for r in gh_records:
    o = r.get("org_data", {})
    name = (o.get("name") or "").strip()
    company = (o.get("company") or "").strip()
    desc = (o.get("description") or "").strip()
    
    if LEGAL_ENTITY_REGEX.search(name) or LEGAL_ENTITY_REGEX.search(company):
        legal_suffix_list.append(r)

print(f"Explicit legal entity suffix orgs (Inc, Corp, Ltd, GmbH, LLC, etc.): {len(legal_suffix_list)}")

# 4. Legitimate company domain + commercial company profile
COMMERCIAL_DESC_REGEX = re.compile(
    r'\b(company|startup|venture-backed|backed by|commercial|enterprise|platform|solution|solutions|service|services|provider|product|products|headquartered|software company|tech company|ai company|cloud platform|saas|developer tool|infrastructure|analytics|security company|data platform|automation|api|agents)\b',
    re.IGNORECASE
)

commercial_domain_profile_list = []
for r in gh_records:
    o = r.get("org_data", {})
    name = (o.get("name") or "").strip()
    login = (r.get("login") or "").strip()
    desc = (o.get("description") or "").strip()
    blog = (o.get("blog") or "").strip()

    # Exclude academic/nonprofit first
    combined_text = f"{name} {login} {desc} {blog}"
    if ACADEMIC_NONPROFIT_REGEX.search(combined_text):
        continue

    # Has valid company domain
    if blog and not any(skip in blog.lower() for skip in ["twitter.com", "x.com", "t.me", "discord.gg", "github.io", "wikipedia.org"]):
        # Has commercial description indicator
        if COMMERCIAL_DESC_REGEX.search(desc) or COMMERCIAL_DESC_REGEX.search(name):
            commercial_domain_profile_list.append(r)

print(f"Commercial website domain + commercial description orgs: {len(commercial_domain_profile_list)}")
