import asyncio
import httpx
from xml.etree import ElementTree as ET
from datetime import datetime, timezone
import json

from src.sources.news_sources import (
    HuggingFaceDailyPapersSource,
    TechCrunchAISource,
    MITTechReviewAISource,
    OpenAIBlogSource,
    HackerNewsAISource
)
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus, RawPayload

async def audit_sources():
    sources = [
        ("HuggingFaceDailyPapers", HuggingFaceDailyPapersSource()),
        ("TechCrunchAI", TechCrunchAISource()),
        ("MITTechReviewAI", MITTechReviewAISource()),
        ("OpenAIBlog", OpenAIBlogSource()),
        ("HackerNewsAI", HackerNewsAISource()),
    ]

    now = datetime.now(timezone.utc)
    print(f"Audit started at: {now.isoformat()}")
    results = {}

    for name, adapter in sources:
        print(f"\n--- Auditing {name} ---")
        item_summary = {
            "source_name": name,
            "access_method": "",
            "discovery_url": getattr(adapter, "api_url", getattr(adapter, "feed_url", getattr(adapter, "rss_url", getattr(adapter, "top_stories_url", "")))),
            "http_status": None,
            "accessible": False,
            "discovered_count": 0,
            "sample_articles": [],
            "status": "NOT_VERIFIED"
        }

        if name == "HuggingFaceDailyPapers":
            item_summary["access_method"] = "JSON API (https://huggingface.co/api/daily_papers)"
        elif name in ("TechCrunchAI", "MITTechReviewAI", "OpenAIBlog"):
            item_summary["access_method"] = "RSS XML Feed"
        elif name == "HackerNewsAI":
            item_summary["access_method"] = "Firebase JSON API"

        try:
            urls = await adapter.discover_urls(max_records=15)
            item_summary["discovered_count"] = len(urls)
            item_summary["http_status"] = 200
            item_summary["accessible"] = True if len(urls) > 0 else False
        except Exception as e:
            print(f"Discovery error for {name}: {e}")
            item_summary["http_status"] = "ERROR"

        fresh_count = 0
        stale_count = 0
        unknown_count = 0
        full_text_count = 0
        partial_text_count = 0

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
            for url in urls[:5]:
                sample = {
                    "url": url,
                    "fetch_status": None,
                    "pub_date_raw": None,
                    "pub_date_parsed": None,
                    "freshness_status": None,
                    "age_hours": None,
                    "title": None,
                    "full_text_length": 0,
                    "ai_relevant": True
                }

                # Create raw payload / test page fetch
                try:
                    res = await client.get(url)
                    sample["fetch_status"] = res.status_code
                    if res.status_code == 200:
                        payload = RawPayload(source_name=name, url=url, raw_content=res.text, content_type="text/html")
                        parsed = adapter.parse_raw_payload(payload)

                        title = parsed.get("content", {}).get("title")
                        pub_date = parsed.get("content", {}).get("published_date")
                        full_text = parsed.get("content", {}).get("full_text", "")

                        sample["title"] = title
                        sample["pub_date_raw"] = pub_date
                        sample["full_text_length"] = len(full_text) if full_text else 0

                        if len(full_text) > 500:
                            full_text_count += 1
                        elif len(full_text) > 0:
                            partial_text_count += 1

                        f_res = freshness_validator.evaluate_freshness(pub_date, reference_now=now)
                        sample["freshness_status"] = f_res.status.value
                        sample["age_hours"] = f_res.age_hours
                        sample["pub_date_parsed"] = f_res.published_at

                        if f_res.status == FreshnessStatus.FRESH:
                            fresh_count += 1
                        elif f_res.status == FreshnessStatus.STALE:
                            stale_count += 1
                        else:
                            unknown_count += 1
                    else:
                        print(f"Failed to fetch article page {url}: status {res.status_code}")
                except Exception as e:
                    print(f"Error fetching article {url}: {e}")
                    sample["fetch_status"] = str(e)

                item_summary["sample_articles"].append(sample)

        item_summary["fresh_count_sample"] = fresh_count
        item_summary["stale_count_sample"] = stale_count
        item_summary["unknown_count_sample"] = unknown_count
        item_summary["full_text_count_sample"] = full_text_count

        if item_summary["accessible"] and item_summary["discovered_count"] > 0:
            if fresh_count > 0 or stale_count > 0:
                item_summary["status"] = "LIVE_VERIFIED"
            else:
                item_summary["status"] = "PARTIALLY_LIVE_VERIFIED"
        else:
            item_summary["status"] = "BLOCKED" if item_summary["http_status"] in (403, 406) else "NOT_VERIFIED"

        results[name] = item_summary
        print(f"Result for {name}: Discovered={item_summary['discovered_count']}, Status={item_summary['status']}, FreshSample={fresh_count}/{len(urls[:5])}")

    with open("scratch/news_audit_live_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved scratch/news_audit_live_result.json")

if __name__ == "__main__":
    asyncio.run(audit_sources())
