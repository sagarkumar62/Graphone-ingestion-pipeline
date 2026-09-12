"""
Phase 5.1.1 — Source Re-Verification Script
Runs with MAX_RECORDS=2, provides full evidence per source.
Covers: TechCrunch, MIT Tech Review, WeWorkRemotely (RSS-only), 
        OpenAI Blog (sitemap check), YC (API check), CryptoJobs (API check),
        HuggingFace (API date field inspection).
"""
import asyncio
import json
import time
import httpx
import sys
import os
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawlers.async_crawler import AsyncCrawlerEngine
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator
from src.utils.time import format_iso8601, get_utc_now
from src.core.logging import logger
from datetime import timezone

MAX_RECORDS = 2
crawler = AsyncCrawlerEngine(global_concurrency=4, per_source_concurrency=2)


def freshness_evidence(pub_date_raw, url=""):
    fr = freshness_validator.evaluate_freshness(pub_date_raw)
    return {
        "pub_date_raw": pub_date_raw,
        "freshness_status": fr.status.value,
        "freshness_reason": fr.reason.value,
        "age_hours": fr.age_hours,
        "published_at": fr.published_at,
    }


# ============================================================
# 1. TechCrunch RSS — re-verify
# ============================================================
async def verify_techcrunch():
    print("\n=== TechCrunchAI — RSS Re-Verification ===")
    feed_url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    result = {"source": "TechCrunchAI", "discovery_urls": [], "http_status_feed": None, 
               "items": [], "error": None}
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}) as client:
            res = await client.get(feed_url)
            result["http_status_feed"] = res.status_code
            print(f"  Feed HTTP status: {res.status_code}")
            
            if res.status_code == 200:
                # Try XML parse
                try:
                    root = ET.fromstring(res.text)
                    items = root.findall(".//item")
                    print(f"  XML items found: {len(items)}")
                    for item in items[:MAX_RECORDS]:
                        link = item.find("link")
                        pub_date = item.find("pubDate")
                        title = item.find("title")
                        url = link.text.strip() if link is not None and link.text else None
                        if url:
                            result["discovery_urls"].append(url)
                            fresh = freshness_evidence(
                                pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                url
                            )
                            result["items"].append({
                                "url": url,
                                "title": title.text.strip() if title is not None else None,
                                "pub_date_rss": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                **fresh
                            })
                except ET.ParseError as e:
                    result["error"] = f"XML parse error: {e}"
                    print(f"  XML parse error: {e}")
                    # Try raw text inspection
                    print(f"  First 500 bytes: {res.text[:500]}")
            else:
                result["error"] = f"HTTP {res.status_code}"
    except Exception as e:
        result["error"] = str(e)
    
    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 2. MIT Tech Review RSS — re-verify
# ============================================================
async def verify_mit():
    print("\n=== MITTechReviewAI — RSS Re-Verification ===")
    feed_url = "https://www.technologyreview.com/topic/artificial-intelligence/feed"
    result = {"source": "MITTechReviewAI", "discovery_urls": [], "http_status_feed": None,
               "items": [], "error": None}
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}) as client:
            res = await client.get(feed_url)
            result["http_status_feed"] = res.status_code
            print(f"  Feed HTTP status: {res.status_code}")
            
            if res.status_code == 200:
                try:
                    root = ET.fromstring(res.text)
                    items = root.findall(".//item")
                    print(f"  XML items found: {len(items)}")
                    for item in items[:MAX_RECORDS]:
                        link = item.find("link")
                        pub_date = item.find("pubDate")
                        title = item.find("title")
                        url = link.text.strip() if link is not None and link.text else None
                        if url:
                            result["discovery_urls"].append(url)
                            fresh = freshness_evidence(
                                pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                url
                            )
                            result["items"].append({
                                "url": url,
                                "title": title.text.strip() if title is not None else None,
                                "pub_date_rss": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                **fresh
                            })
                except ET.ParseError as e:
                    result["error"] = f"XML parse error: {e}"
                    print(f"  First 500 bytes: {res.text[:500]}")
            else:
                result["error"] = f"HTTP {res.status_code}"
    except Exception as e:
        result["error"] = str(e)
    
    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 3. WeWorkRemotely — RSS-only extraction (no page fetch)
# ============================================================
async def verify_wwr_rss_only():
    print("\n=== WeWorkRemotelyAI — RSS-Only Extraction (no page fetch) ===")
    feed_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    result = {"source": "WeWorkRemotelyAI", "strategy": "RSS_ONLY",
               "http_status_feed": None, "items": [], "error": None}
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}) as client:
            res = await client.get(feed_url)
            result["http_status_feed"] = res.status_code
            print(f"  Feed HTTP status: {res.status_code}")
            
            if res.status_code == 200:
                try:
                    root = ET.fromstring(res.text)
                    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
                    items = root.findall(".//item")
                    print(f"  RSS items found: {len(items)}")
                    
                    for item in items[:MAX_RECORDS]:
                        link = item.find("link")
                        pub_date = item.find("pubDate")
                        title = item.find("title")
                        description = item.find("description")
                        content_encoded = item.find("content:encoded", ns)
                        
                        url_val = link.text.strip() if link is not None and link.text else None
                        title_val = title.text.strip() if title is not None and title.text else None
                        desc_val = description.text.strip() if description is not None and description.text else None
                        pub_date_val = pub_date.text.strip() if pub_date is not None and pub_date.text else None
                        content_val = content_encoded.text[:200] if content_encoded is not None and content_encoded.text else None
                        
                        fresh = freshness_evidence(pub_date_val, url_val or "")
                        result["items"].append({
                            "url": url_val,
                            "title": title_val,
                            "pub_date_rss": pub_date_val,
                            "description_preview": desc_val[:200] if desc_val else None,
                            "content_preview": content_val,
                            **fresh
                        })
                        print(f"  Item: {title_val} | {pub_date_val} | freshness={fresh['freshness_status']}")
                except ET.ParseError as e:
                    result["error"] = f"XML parse: {e}"
            else:
                result["error"] = f"HTTP {res.status_code}"
    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 4. OpenAI Blog — try sitemap
# ============================================================
async def verify_openai_sitemap():
    print("\n=== OpenAIBlog — Sitemap / Alt Endpoint Check ===")
    candidates = [
        "https://openai.com/sitemap.xml",
        "https://openai.com/news/sitemap.xml",
        "https://openai.com/blog/rss.xml",
        "https://openai.com/news/rss.xml",
    ]
    result = {"source": "OpenAIBlog", "candidates": {}}
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in candidates:
            try:
                res = await client.get(url)
                preview = res.text[:300] if res.status_code == 200 else ""
                result["candidates"][url] = {
                    "http_status": res.status_code,
                    "content_type": res.headers.get("content-type", ""),
                    "preview": preview
                }
                print(f"  {url} -> {res.status_code} {res.headers.get('content-type','')}")
            except Exception as e:
                result["candidates"][url] = {"error": str(e)}
    
    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 5. YC WorkAtAStartup — check API alternatives
# ============================================================
async def verify_yc_api():
    print("\n=== YCWorkAtAStartup — API / Alt Endpoint Check ===")
    candidates = [
        "https://www.workatastartup.com/api/jobs",
        "https://www.workatastartup.com/sitemap.xml",
        "https://api.workatastartup.com/v2/jobs",
        "https://www.ycombinator.com/jobs",
    ]
    result = {"source": "YCWorkAtAStartup", "candidates": {}}
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in candidates:
            try:
                res = await client.get(url)
                result["candidates"][url] = {
                    "http_status": res.status_code,
                    "content_type": res.headers.get("content-type", ""),
                    "preview": res.text[:200] if res.status_code == 200 else ""
                }
                print(f"  {url} -> {res.status_code} {res.headers.get('content-type','')}")
            except Exception as e:
                result["candidates"][url] = {"error": str(e)}
    
    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 6. CryptoJobsList — check API alternatives
# ============================================================
async def verify_cryptojobs_api():
    print("\n=== CryptoJobsAI — API / Alt Endpoint Check ===")
    candidates = [
        "https://cryptojobslist.com/api/jobs?category=ai",
        "https://cryptojobslist.com/rss.xml",
        "https://cryptojobslist.com/feed.xml",
        "https://cryptojobslist.com/sitemap.xml",
        "https://cryptojobslist.com/ai.json",
    ]
    result = {"source": "CryptoJobsAI", "candidates": {}}
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in candidates:
            try:
                res = await client.get(url)
                result["candidates"][url] = {
                    "http_status": res.status_code,
                    "content_type": res.headers.get("content-type", ""),
                    "preview": res.text[:200] if res.status_code == 200 else ""
                }
                print(f"  {url} -> {res.status_code} {res.headers.get('content-type','')}")
            except Exception as e:
                result["candidates"][url] = {"error": str(e)}
    
    print(json.dumps(result, indent=2, default=str))
    return result


# ============================================================
# 7. HuggingFace API — inspect date fields
# ============================================================
async def verify_hf_api_dates():
    print("\n=== HuggingFaceDailyPapers — API Date Field Inspection ===")
    api_url = "https://huggingface.co/api/daily_papers"
    result = {"source": "HuggingFaceDailyPapers", "date_fields_found": [], "sample": None}
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            res = await client.get(api_url)
            print(f"  API HTTP status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                if data:
                    # Inspect first 3 items for all possible date fields
                    for i, item in enumerate(data[:3]):
                        paper = item.get("paper", {})
                        date_fields = {
                            "item_level": {k: v for k, v in item.items() if "date" in k.lower() or "time" in k.lower() or "at" in k.lower() or "published" in k.lower()},
                            "paper_level": {k: v for k, v in paper.items() if "date" in k.lower() or "time" in k.lower() or "at" in k.lower() or "published" in k.lower() or "submit" in k.lower()},
                            "paper_id": paper.get("id"),
                            "paper_keys": list(paper.keys()),
                            "item_keys": list(item.keys()),
                        }
                        if i == 0:
                            result["sample"] = date_fields
                            result["date_fields_found"] = list(date_fields["item_level"].keys()) + list(date_fields["paper_level"].keys())
                        print(f"  Item {i} keys: {list(item.keys())}")
                        print(f"  Paper keys: {list(paper.keys())}")
                        print(f"  Date fields - item: {date_fields['item_level']}")
                        print(f"  Date fields - paper: {date_fields['paper_level']}")
    except Exception as e:
        result["error"] = str(e)
    
    print(json.dumps(result, indent=2, default=str))
    return result


async def main():
    print("=" * 70)
    print("PHASE 5.1.1 — SOURCE RE-VERIFICATION")
    print(f"Time: {format_iso8601()}")
    print("=" * 70)
    
    results = {}
    
    # Run all checks
    results["techcrunch"] = await verify_techcrunch()
    results["mit"] = await verify_mit()
    results["wwr_rss"] = await verify_wwr_rss_only()
    results["openai_sitemap"] = await verify_openai_sitemap()
    results["yc_api"] = await verify_yc_api()
    results["cryptojobs_api"] = await verify_cryptojobs_api()
    results["hf_api_dates"] = await verify_hf_api_dates()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, r in results.items():
        src = r.get("source", name)
        err = r.get("error", "")
        items = r.get("items", r.get("candidates", []))
        print(f"  {src}: error={err or 'none'} | items={len(items) if isinstance(items, list) else 'N/A'}")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
