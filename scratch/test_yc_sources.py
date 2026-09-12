import asyncio
import httpx
import json

async def test_yc_sources():
    # Test 1: Algolia YC Company search index endpoint (used publicly by ycombinator.com)
    # Algolia App ID: 45BW2AC4X8, API Key: 99a3e861d378b2a84e976694e9f73f32
    url = "https://45bw2ac4x8-dsn.algolia.net/1/indexes/YCCompany_production/query?x-algolia-agent=Algolia%20for%20JavaScript%20(4.13.0)%3B%20JS%20Helper%20(3.22.5)&x-algolia-api-key=99a3e861d378b2a84e976694e9f73f32&x-algolia-application-id=45BW2AC4X8"

    headers = {"Content-Type": "application/json"}
    body = {
        "params": "query=&hitsPerPage=1000&page=0"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.post(url, headers=headers, json=body)
            print("Algolia YC Status:", res.status_code)
            if res.status_code == 200:
                data = res.json()
                hits = data.get("hits", [])
                print(f"Discovered {len(hits)} YC companies from Algolia API!")
                if hits:
                    print("Sample YC Company:", json.dumps(hits[0], indent=2)[:400])
                    return hits
        except Exception as e:
            print("Algolia YC Error:", e)

    # Test 2: GitHub public dataset of YC companies
    github_yc_url = "https://raw.githubusercontent.com/ycombinator/companies/main/companies.json"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.get(github_yc_url)
            print("GitHub YC JSON Status:", res.status_code)
            if res.status_code == 200:
                data = res.json()
                print(f"Discovered {len(data)} YC companies from GitHub YC JSON!")
                return data
        except Exception as e:
            print("GitHub YC JSON Error:", e)

    return []

if __name__ == "__main__":
    asyncio.run(test_yc_sources())
