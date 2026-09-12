import asyncio
import sqlite3
import json
import httpx
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
from src.core.config import settings
from src.sources.startup_sources import GitHubOrganizationsStartupSource
from src.storage.database import db_manager
from src.storage.repositories import EntityRepository
from src.core.models import RecordType, RawPayload, CanonicalEntity
from src.validators.schema_validator import validator

async def ingest_to_1050():
    token = getattr(settings, "GITHUB_TOKEN", None)
    headers = {
        "User-Agent": "GraphOne-Ingestion-Pipeline/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    adapter = GitHubOrganizationsStartupSource(token=token)

    con = sqlite3.connect("pipeline.db")
    cur = con.cursor()
    existing_urls = set(r[0] for r in cur.execute("SELECT source_url FROM startups").fetchall())
    con.close()

    print(f"Current defensible startups in pipeline.db: {len(existing_urls)}")

    expanded_queries = [
        "type:org+location:San+Diego",
        "type:org+location:Portland",
        "type:org+location:Salt+Lake+City",
        "type:org+location:Phoenix",
        "type:org+location:Raleigh",
        "type:org+location:Philadelphia",
        "type:org+location:Pittsburgh",
        "type:org+location:Minneapolis",
        "type:org+location:Atlanta",
        "type:org+location:Tampa",
        "type:org+location:Miami",
        "type:org+location:Dublin",
        "type:org+location:Edinburgh",
        "type:org+location:Zurich",
        "type:org+location:Vienna",
        "type:org+location:Munich",
        "type:org+location:Hamburg",
        "type:org+location:Frankfurt",
        "type:org+location:Madrid",
        "type:org+location:Barcelona",
        "type:org+location:Milan",
        "type:org+location:Oslo",
        "type:org+location:Copenhagen",
        "type:org+location:Brussels",
        "type:org+location:Prague",
        "type:org+location:Warsaw"
    ]

    discovered_candidates = []
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)

    async with httpx.AsyncClient(limits=limits, timeout=15.0, headers=headers) as client:
        for q in expanded_queries:
            if len(existing_urls) + len(discovered_candidates) >= 1500:
                break
            for page in range(1, 8):
                if len(existing_urls) + len(discovered_candidates) >= 1500:
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
                            if html_url and html_url not in existing_urls and html_url not in discovered_candidates:
                                discovered_candidates.append(html_url)
                    elif res.status_code in {403, 429}:
                        await asyncio.sleep(2.0)
                        break
                    else:
                        break
                except Exception:
                    break

    print(f"Discovered {len(discovered_candidates)} NEW candidate URLs to evaluate.")

    await db_manager.init_db()
    repo = EntityRepository(db_manager)

    saved_count = len(existing_urls)
    rejected_count = 0

    semaphore = asyncio.Semaphore(15)
    async with httpx.AsyncClient(limits=limits, timeout=12.0, headers=headers) as client:
        async def evaluate_and_save(url):
            nonlocal saved_count, rejected_count
            if saved_count >= 1052:
                return

            login = url.strip("/").split("/")[-1]
            api_url = f"https://api.github.com/orgs/{login}"

            async with semaphore:
                try:
                    res = await client.get(api_url)
                    if res.status_code != 200:
                        rejected_count += 1
                        return
                    raw_data = res.json()

                    is_def, reason = adapter.is_defensible_startup(raw_data, url)
                    if not is_def:
                        rejected_count += 1
                        return

                    raw_payload = RawPayload(
                        source_name=adapter.source_name,
                        url=url,
                        raw_content=json.dumps(raw_data),
                        content_type="application/json",
                        fetched_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    )

                    canonical_dict = adapter.parse_raw_payload(raw_payload)

                    is_valid, errors = validator.validate(canonical_dict, RecordType.STARTUP)
                    if not is_valid:
                        rejected_count += 1
                        return

                    entity = CanonicalEntity(**canonical_dict)
                    success = await repo.save_canonical_entity(entity)
                    if success:
                        saved_count += 1
                        existing_urls.add(url)
                        if saved_count % 10 == 0 or saved_count >= 1050:
                            print(f"Ingested defensible startup [{saved_count}/1052]: {entity.content.get('entityName')} ({url})")
                    else:
                        rejected_count += 1

                except Exception:
                    rejected_count += 1

        tasks = [evaluate_and_save(url) for url in discovered_candidates]
        await asyncio.gather(*tasks)

    print("=" * 60)
    print("FINAL EXPANDED INGESTION SUMMARY:")
    print(f"Final Defensible Startup Count in pipeline.db: {saved_count}")
    print(f"Candidates Rejected in batch: {rejected_count}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(ingest_to_1050())
