"""
Phase 5.1 — Live Audit Script
Runs discovery probes against all 10 configured sources with MAX_RECORDS=2 each.
Records actual HTTP results, discovery counts, and extraction attempts.
NO fabrication. NO synthetic fallback. Pure real evidence.
"""
import asyncio
import json
import time
import sys
import os
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from src.sources.registry import registry
from src.sources.news_sources import (
    HuggingFaceDailyPapersSource, TechCrunchAISource, MITTechReviewAISource,
    OpenAIBlogSource, HackerNewsAISource
)
from src.sources.job_sources import (
    AIJobsNetSource, YCWorkAtAStartupSource, RemoteOKAISource,
    WeWorkRemotelyAISource, CryptoJobsAISource
)
from src.crawlers.async_crawler import AsyncCrawlerEngine
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator
from src.core.models import FreshnessStatus, RawPayload
from src.utils.time import format_iso8601
from src.core.logging import logger


ALL_NEWS_ADAPTERS = [
    HuggingFaceDailyPapersSource(),
    TechCrunchAISource(),
    MITTechReviewAISource(),
    OpenAIBlogSource(),
    HackerNewsAISource(),
]

ALL_JOB_ADAPTERS = [
    AIJobsNetSource(),
    YCWorkAtAStartupSource(),
    RemoteOKAISource(),
    WeWorkRemotelyAISource(),
    CryptoJobsAISource(),
]

MAX_PER_SOURCE = 2
crawler = AsyncCrawlerEngine(global_concurrency=5, per_source_concurrency=2)


async def probe_source(adapter, category: str) -> dict:
    """Probe a single source adapter: discover + fetch + extract, NO fabrication."""
    result = {
        "source": adapter.source_name,
        "category": category,
        "adapter_class": adapter.__class__.__name__,
        "discovery_status": "NOT_RUN",
        "discovered_count": 0,
        "fetched_count": 0,
        "http_statuses": [],
        "freshness_results": [],
        "full_text_sample": None,
        "full_text_length": 0,
        "extraction_evidence": [],
        "errors": [],
        "classification": "NOT_LIVE_VERIFIED",
        "elapsed_sec": 0.0,
    }
    
    t0 = time.time()
    
    # Step 1: Discovery
    try:
        urls = await adapter.discover_urls(max_records=MAX_PER_SOURCE)
        result["discovered_count"] = len(urls)
        result["discovery_status"] = "SUCCESS" if urls else "EMPTY"
        result["discovered_urls"] = urls[:MAX_PER_SOURCE]
    except Exception as e:
        result["discovery_status"] = "FAILED"
        result["errors"].append(f"Discovery error: {type(e).__name__}: {e}")
        result["elapsed_sec"] = round(time.time() - t0, 2)
        result["classification"] = "BLOCKED" if "403" in str(e) or "429" in str(e) else "NOT_LIVE_VERIFIED"
        return result

    if not urls:
        result["classification"] = "NOT_LIVE_VERIFIED"
        result["errors"].append("No URLs discovered — source may be blocked, empty, or JS-required")
        result["elapsed_sec"] = round(time.time() - t0, 2)
        return result

    # Step 2: Fetch + Extract (up to MAX_PER_SOURCE)
    fetched_ok = 0
    for url in urls[:MAX_PER_SOURCE]:
        try:
            raw_payload = await crawler.fetch_with_retry(url, adapter.source_name)
            result["http_statuses"].append(raw_payload.http_status)
            fetched_ok += 1

            # Full-text extraction
            extracted = html_extractor.extract(raw_payload.raw_content, url)
            content_hash = hashlib.sha256(raw_payload.raw_content.encode("utf-8")).hexdigest()[:16]

            # Freshness check
            pub_date = adapter.extract_published_at(raw_payload)
            freshness_res = freshness_validator.evaluate_freshness(pub_date)
            result["freshness_results"].append({
                "url": url,
                "pub_date_raw": pub_date,
                "freshness_status": freshness_res.status.value,
                "freshness_reason": freshness_res.reason.value,
                "age_hours": freshness_res.age_hours
            })

            # Full-text evidence
            text_len = len(extracted.main_text)
            if text_len > 0 and result["full_text_sample"] is None:
                result["full_text_sample"] = extracted.main_text[:200] + "..." if text_len > 200 else extracted.main_text
                result["full_text_length"] = text_len

            evidence = {
                "url": url,
                "content_hash": content_hash,
                "http_status": raw_payload.http_status,
                "content_bytes": len(raw_payload.raw_content.encode("utf-8")),
                "title": extracted.title,
                "extracted_text_len": text_len,
                "json_ld_dates": extracted.json_ld_dates,
                "meta_dates": extracted.meta_dates,
                "freshness_status": freshness_res.status.value,
            }
            result["extraction_evidence"].append(evidence)

        except Exception as e:
            result["errors"].append(f"Fetch/parse error on {url}: {type(e).__name__}: {e}")
            result["http_statuses"].append("ERROR")

    result["fetched_count"] = fetched_ok
    result["elapsed_sec"] = round(time.time() - t0, 2)

    # Classification
    if fetched_ok > 0 and result["full_text_length"] > 100:
        result["classification"] = "LIVE_VERIFIED"
    elif fetched_ok > 0:
        result["classification"] = "PARTIALLY_LIVE_VERIFIED"
    elif any("403" in str(e) for e in result["errors"]):
        result["classification"] = "BLOCKED"
    else:
        result["classification"] = "NOT_LIVE_VERIFIED"

    return result


async def main():
    print("=" * 80)
    print("PHASE 5.1 — SOURCE AUDIT: ALL 10 NEWS + JOB SOURCES")
    print(f"Time: {format_iso8601()}")
    print("=" * 80)
    print()

    all_results = {"news": [], "jobs": []}

    # Test News Sources
    print("== NEWS SOURCES ==")
    for adapter in ALL_NEWS_ADAPTERS:
        print(f"  Probing: {adapter.source_name}...")
        res = await probe_source(adapter, "NEWS")
        all_results["news"].append(res)
        print(f"    -> {res['classification']} | discovered={res['discovered_count']} | fetched={res['fetched_count']} | text_len={res['full_text_length']}")
        if res["errors"]:
            print(f"    -> Errors: {res['errors'][:2]}")

    print()
    print("== JOB SOURCES ==")
    for adapter in ALL_JOB_ADAPTERS:
        print(f"  Probing: {adapter.source_name}...")
        res = await probe_source(adapter, "JOB")
        all_results["jobs"].append(res)
        print(f"    -> {res['classification']} | discovered={res['discovered_count']} | fetched={res['fetched_count']} | text_len={res['full_text_length']}")
        if res["errors"]:
            print(f"    -> Errors: {res['errors'][:2]}")

    # Print full detailed report
    print()
    print("=" * 80)
    print("DETAILED EVIDENCE REPORT")
    print("=" * 80)
    print(json.dumps(all_results, indent=2, default=str))

    # Summary table
    print()
    print("=" * 80)
    print("AUDIT SUMMARY TABLE")
    print("=" * 80)
    header = f"{'Source':<28} {'Type':<6} {'Disc':>5} {'Fetch':>5} {'TextLen':>8} {'Freshness':<12} {'Status'}"
    print(header)
    print("-" * 90)
    for res in all_results["news"] + all_results["jobs"]:
        fresh_strs = [f["freshness_status"] for f in res.get("freshness_results", [])]
        fresh_summary = "/".join(fresh_strs) if fresh_strs else "N/A"
        print(f"{res['source']:<28} {res['category']:<6} {res['discovered_count']:>5} {res['fetched_count']:>5} {res['full_text_length']:>8} {fresh_summary:<12} {res['classification']}")

    return all_results


if __name__ == "__main__":
    asyncio.run(main())
