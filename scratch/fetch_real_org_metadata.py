import json
import httpx
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from src.core.config import settings

async def fetch_all_real_org_metadata():
    with open("scratch/db_startups_parsed.json", "r", encoding="utf-8") as f:
        db_records = json.load(f)

    print(f"Loaded {len(db_records)} records from scratch/db_startups_parsed.json")

    token = getattr(settings, "GITHUB_TOKEN", None)
    headers = {
        "User-Agent": "GraphOne-Audit/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        print("Using GitHub Token from settings!")
    else:
        print("WARNING: No GitHub Token found in settings.")

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
    semaphore = asyncio.Semaphore(10)

    fetched_data = {}

    async with httpx.AsyncClient(limits=limits, timeout=15.0, headers=headers) as client:
        async def fetch_org(rec):
            s_url = rec["source_url"]
            if "ycombinator.com" in s_url or rec["source_name"] == "YC Directory":
                fetched_data[s_url] = {
                    "is_yc": True,
                    "name": rec["entity_name"],
                    "url": s_url
                }
                return

            login = s_url.strip("/").split("/")[-1]
            api_url = f"https://api.github.com/orgs/{login}"

            async with semaphore:
                try:
                    res = await client.get(api_url)
                    if res.status_code == 200:
                        fetched_data[s_url] = res.json()
                    elif res.status_code == 404:
                        # Try user endpoint
                        res_u = await client.get(f"https://api.github.com/users/{login}")
                        if res_u.status_code == 200:
                            data = res_u.json()
                            data["is_user_fallback"] = True
                            fetched_data[s_url] = data
                        else:
                            fetched_data[s_url] = {"status_code": res_u.status_code, "error": "Not Found"}
                    else:
                        fetched_data[s_url] = {"status_code": res.status_code, "error": f"HTTP {res.status_code}"}
                except Exception as e:
                    fetched_data[s_url] = {"error": str(e)}

        tasks = [fetch_org(r) for r in db_records]
        await asyncio.gather(*tasks)

    print(f"Successfully processed {len(fetched_data)} items.")

    with open("scratch/real_github_org_metadata.json", "w", encoding="utf-8") as f:
        json.dump(fetched_data, f, indent=2)

    print("Saved real metadata to scratch/real_github_org_metadata.json")

if __name__ == "__main__":
    asyncio.run(fetch_all_real_org_metadata())
