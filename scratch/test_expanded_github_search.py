import asyncio
import httpx
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from src.core.config import settings
from src.sources.startup_sources import GitHubOrganizationsStartupSource

async def test_expanded_search():
    token = getattr(settings, "GITHUB_TOKEN", None)
    headers = {
        "User-Agent": "GraphOne-Audit/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    adapter = GitHubOrganizationsStartupSource(token=token)

    # Expanded search query facets across locations, tech topics, and creation date ranges
    expanded_queries = [
        "type:org+location:San+Francisco",
        "type:org+location:San+Jose",
        "type:org+location:Palo+Alto",
        "type:org+location:Mountain+View",
        "type:org+location:Sunnyvale",
        "type:org+location:Seattle",
        "type:org+location:New+York",
        "type:org+location:Boston",
        "type:org+location:Austin",
        "type:org+location:Chicago",
        "type:org+location:Los+Angeles",
        "type:org+location:London",
        "type:org+location:Berlin",
        "type:org+location:Paris",
        "type:org+location:Toronto",
        "type:org+location:Vancouver",
        "type:org+location:Tokyo",
        "type:org+location:Singapore",
        "type:org+location:Tel+Aviv",
        "type:org+location:Stockholm",
        "type:org+location:Amsterdam",
        "type:org+topic:artificial-intelligence",
        "type:org+topic:machine-learning",
        "type:org+topic:deep-learning",
        "type:org+topic:llm",
        "type:org+topic:developer-tools",
        "type:org+topic:cloud-native",
        "type:org+topic:database",
        "type:org+followers:10..100",
        "type:org+repos:20..100",
        "type:org+created:2021-01-01..2021-12-31",
        "type:org+created:2022-01-01..2022-12-31",
        "type:org+created:2023-01-01..2023-12-31",
        "type:org+created:2024-01-01..2024-12-31"
    ]

    # Existing 697 accepted URLs to avoid duplicates
    with open("scratch/audit_authenticated_summary.json", "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    existing_urls = set(r["url"] for r in audit_data.get("accepted", []))
    print(f"Loaded {len(existing_urls)} existing accepted URLs.")

    new_discovered_urls = []

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
    async with httpx.AsyncClient(limits=limits, timeout=15.0, headers=headers) as client:
        for q in expanded_queries:
            if len(new_discovered_urls) >= 1000:
                break
            for page in range(1, 6): # top 5 pages per query
                if len(new_discovered_urls) >= 1000:
                    break
                api_url = f"https://api.github.com/search/users?q={q}&per_page=100&page={page}"
                try:
                    res = await client.get(api_url)
                    if res.status_code == 200:
                        items = res.json().get("items", [])
                        if not items:
                            break
                        for item in items:
                            html_url = item.get("html_url")
                            if html_url and html_url not in existing_urls and html_url not in new_discovered_urls:
                                new_discovered_urls.append(html_url)
                    elif res.status_code in {403, 429}:
                        print("Rate limited on search API, waiting 2s...")
                        await asyncio.sleep(2.0)
                        break
                    else:
                        break
                except Exception as e:
                    print("Search error:", e)
                    break

    print(f"Discovered {len(new_discovered_urls)} NEW candidate URLs!")

    # Now evaluate candidate URLs with strict defensibility validator
    new_accepted = []
    new_rejected = []

    semaphore = asyncio.Semaphore(15)
    async with httpx.AsyncClient(limits=limits, timeout=12.0, headers=headers) as client:
        async def evaluate_candidate(url):
            login = url.strip("/").split("/")[-1]
            api_url = f"https://api.github.com/orgs/{login}"
            async with semaphore:
                try:
                    res = await client.get(api_url)
                    if res.status_code == 200:
                        data = res.json()
                        is_def, reason = adapter.is_defensible_startup(data, url)
                        if is_def:
                            new_accepted.append({"url": url, "name": data.get("name") or login, "reason": reason, "data": data})
                        else:
                            new_rejected.append({"url": url, "reason": reason})
                except Exception as e:
                    pass

        tasks = [evaluate_candidate(url) for url in new_discovered_urls[:800]]
        await asyncio.gather(*tasks)

    print("=" * 60)
    print("EXPANDED CANDIDATE EVALUATION RESULTS:")
    print(f"Candidates Evaluated: {min(len(new_discovered_urls), 800)}")
    print(f"New Defensible Accepted: {len(new_accepted)}")
    print(f"New Rejected: {len(new_rejected)}")
    print(f"Projected Total Defensible Startups: {len(existing_urls) + len(new_accepted)}")
    print("=" * 60)

    with open("scratch/new_defensible_candidates.json", "w", encoding="utf-8") as f:
        json.dump(new_accepted, f, indent=2)

if __name__ == "__main__":
    asyncio.run(test_expanded_search())
