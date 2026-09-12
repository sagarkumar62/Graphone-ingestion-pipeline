import sqlite3
import json
import httpx
import asyncio
import os
import re

async def deep_inspect():
    con = sqlite3.connect('pipeline.db')
    cur = con.cursor()
    rows = cur.execute('SELECT id, source_name, source_url, entity_name, data_json FROM startups').fetchall()
    con.close()

    print(f"Deep inspecting {len(rows)} records...")

    token = os.environ.get("GITHUB_TOKEN")
    headers = {"User-Agent": "GraphOne-Audit/1.0", "Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    limits = httpx.Limits(max_keepalive_connections=30, max_connections=50)

    org_details = []

    async with httpx.AsyncClient(limits=limits, timeout=12.0, headers=headers) as client:
        semaphore = asyncio.Semaphore(20)

        async def fetch_one(row):
            rec_id, s_name, s_url, name, d_json = row
            if "ycombinator.com" in s_url or s_name == "YC Directory":
                return {
                    "id": rec_id, "url": s_url, "name": name, "source": s_name,
                    "is_yc": True, "org_data": {}
                }

            login = s_url.strip("/").split("/")[-1]
            api_url = f"https://api.github.com/orgs/{login}"

            data = {}
            async with semaphore:
                try:
                    res = await client.get(api_url)
                    if res.status_code == 200:
                        data = res.json()
                    elif res.status_code == 404:
                        res_u = await client.get(f"https://api.github.com/users/{login}")
                        if res_u.status_code == 200:
                            data = res_u.json()
                except Exception as e:
                    pass

            return {
                "id": rec_id, "url": s_url, "name": name, "source": s_name,
                "login": login, "is_yc": False, "org_data": data
            }

        tasks = [fetch_one(r) for r in rows]
        org_details = await asyncio.gather(*tasks)

    # Save fetched org details to scratch JSON so we don't re-fetch during analysis
    with open("scratch/fetched_org_details.json", "w", encoding="utf-8") as f:
        json.dump(org_details, f, indent=2)

    print(f"Saved details for {len(org_details)} records to scratch/fetched_org_details.json")

if __name__ == "__main__":
    asyncio.run(deep_inspect())
