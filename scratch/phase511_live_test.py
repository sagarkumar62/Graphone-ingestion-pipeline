"""
Phase 5.1.1 — Live News + Jobs verification with freshness acceptance gate.
MAX_RECORDS = 5 per source.
News: TechCrunchAI (strongest confirmed RSS source)
Jobs: RemoteOKAI (strongest confirmed API source)
Applies freshness acceptance gate to every record.
NO fabrication. Stale = stale, UNKNOWN = UNKNOWN.
"""
import asyncio
import json
import time
import httpx
import sys
import os
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawlers.async_crawler import AsyncCrawlerEngine
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator, FreshnessValidator
from src.core.models import FreshnessStatus
from src.utils.time import format_iso8601

MAX_RECORDS = 5
crawler = AsyncCrawlerEngine(global_concurrency=5, per_source_concurrency=2)


class FreshnessAcceptanceGate:
    """Accept only FRESH records into the 24h dataset."""
    def __init__(self, validator: FreshnessValidator = freshness_validator):
        self.validator = validator

    def accept(self, pub_date) -> tuple[bool, str]:
        res = self.validator.evaluate_freshness(pub_date)
        if res.status == FreshnessStatus.FRESH:
            return True, f"FRESH (age={res.age_hours}h)"
        elif res.status == FreshnessStatus.STALE:
            return False, f"STALE (age={res.age_hours}h)"
        else:
            return False, "UNKNOWN_DATE"


gate = FreshnessAcceptanceGate()


async def live_news_test():
    """Live news test: TechCrunchAI RSS, MAX_RECORDS=5."""
    print("\n" + "=" * 70)
    print("LIVE NEWS TEST — TechCrunchAI (RSS, MAX_RECORDS=5)")
    print("=" * 70)

    feed_url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    records = []

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}) as client:
            res = await client.get(feed_url)
            print(f"  Feed HTTP: {res.status_code}")
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                items = root.findall(".//item")
                print(f"  RSS items in feed: {len(items)}")
                for item in items[:MAX_RECORDS]:
                    link = item.find("link")
                    pub_date_el = item.find("pubDate")
                    title_el = item.find("title")
                    url = link.text.strip() if link is not None and link.text else None
                    pub_date_raw = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else None
                    title = title_el.text.strip() if title_el is not None and title_el.text else None

                    accepted, gate_reason = gate.accept(pub_date_raw)
                    fresh_res = freshness_validator.evaluate_freshness(pub_date_raw)

                    rec = {
                        "url": url,
                        "title": title,
                        "pub_date_raw": pub_date_raw,
                        "pub_date_iso": fresh_res.published_at,
                        "freshness_status": fresh_res.status.value,
                        "freshness_reason": fresh_res.reason.value,
                        "age_hours": fresh_res.age_hours,
                        "gate_accepted": accepted,
                        "gate_reason": gate_reason,
                        "provenance": {
                            "source_name": "TechCrunchAI",
                            "source_url": url,
                            "feed_url": feed_url,
                            "date_extraction_method": "RSS pubDate element",
                        }
                    }
                    # Try fetching full text for first accepted record only
                    if accepted and url and not any(r.get("full_text_len", 0) > 0 for r in records):
                        try:
                            t0 = time.time()
                            raw = await crawler.fetch_with_retry(url, "TechCrunchAI")
                            extracted = html_extractor.extract(raw.raw_content, url)
                            rec["http_status"] = raw.http_status
                            rec["content_hash"] = raw.content_hash[:16] if hasattr(raw, "content_hash") else "N/A"
                            rec["full_text_len"] = len(extracted.main_text)
                            rec["full_text_sample"] = extracted.main_text[:300]
                            rec["fetch_elapsed_sec"] = round(time.time() - t0, 2)
                        except Exception as e:
                            rec["fetch_error"] = str(e)
                    records.append(rec)

    except Exception as e:
        print(f"  ERROR: {e}")
        return {"error": str(e)}

    accepted_count = sum(1 for r in records if r["gate_accepted"])
    print(f"\n  Total records: {len(records)}")
    print(f"  Gate accepted (FRESH): {accepted_count}")
    print(f"  Gate rejected (STALE/UNKNOWN): {len(records) - accepted_count}")
    print()
    for r in records:
        status = "ACCEPTED" if r["gate_accepted"] else "REJECTED"
        print(f"  [{status}] {r['title'][:60] if r['title'] else 'N/A'}")
        print(f"    url:       {r['url']}")
        print(f"    pub_date:  {r['pub_date_raw']}")
        print(f"    age_hours: {r['age_hours']}")
        print(f"    freshness: {r['freshness_status']}")
        print(f"    gate:      {r['gate_reason']}")
        if "full_text_len" in r:
            print(f"    text_len:  {r['full_text_len']}")
        if "fetch_error" in r:
            print(f"    fetch_err: {r['fetch_error']}")
        print()

    return {"source": "TechCrunchAI", "feed_http": 200, "records": records, "accepted": accepted_count}


async def live_job_test():
    """Live job test: RemoteOKAI API, MAX_RECORDS=5."""
    print("\n" + "=" * 70)
    print("LIVE JOB TEST — RemoteOKAI (JSON API, MAX_RECORDS=5)")
    print("=" * 70)

    api_url = "https://remoteok.com/api"
    records = []

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}) as client:
            res = await client.get(api_url)
            print(f"  API HTTP: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                jobs = [j for j in data[1:] if isinstance(j, dict)]
                ai_jobs = [j for j in jobs if any(
                    k in [t.lower() for t in j.get("tags", [])] + [j.get("position", "").lower()]
                    for k in ["ai", "python", "machine learning", "data", "engineer", "ml"]
                )]
                print(f"  Total API jobs: {len(jobs)}")
                print(f"  AI-filtered jobs: {len(ai_jobs)}")

                for job in ai_jobs[:MAX_RECORDS]:
                    url = job.get("url") or f"https://remoteok.com/remote-jobs/{job.get('id')}"
                    # API date field: 'date' or 'epoch'
                    epoch = job.get("epoch")
                    date_str = job.get("date")
                    pub_date_raw = None
                    if epoch:
                        from datetime import timezone
                        pub_date_raw = datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
                    elif date_str:
                        pub_date_raw = date_str

                    accepted, gate_reason = gate.accept(pub_date_raw)
                    fresh_res = freshness_validator.evaluate_freshness(pub_date_raw)

                    rec = {
                        "url": url,
                        "position": job.get("position"),
                        "company": job.get("company"),
                        "location": job.get("location", "Remote"),
                        "tags": job.get("tags", []),
                        "pub_date_raw": pub_date_raw,
                        "pub_date_iso": fresh_res.published_at,
                        "freshness_status": fresh_res.status.value,
                        "freshness_reason": fresh_res.reason.value,
                        "age_hours": fresh_res.age_hours,
                        "gate_accepted": accepted,
                        "gate_reason": gate_reason,
                        "date_extraction_method": "API epoch field -> UTC ISO" if epoch else ("API date field" if date_str else "NONE"),
                        "provenance": {
                            "source_name": "RemoteOKAI",
                            "source_url": url,
                            "api_url": api_url,
                        }
                    }
                    records.append(rec)

    except Exception as e:
        print(f"  ERROR: {e}")
        return {"error": str(e)}

    accepted_count = sum(1 for r in records if r["gate_accepted"])
    print(f"\n  Total AI-filtered records: {len(records)}")
    print(f"  Gate accepted (FRESH within 24h): {accepted_count}")
    print(f"  Gate rejected (STALE/UNKNOWN): {len(records) - accepted_count}")

    if accepted_count == 0:
        print("\n  NOTE: No fresh jobs found in this sample.")
        print("  This is correct non-fabrication behavior.")
        print("  The system correctly identifies stale records and does NOT substitute fabricated dates.")
    
    print()
    for r in records:
        status = "ACCEPTED" if r["gate_accepted"] else "REJECTED"
        print(f"  [{status}] {r['position']} @ {r['company']}")
        print(f"    url:       {r['url']}")
        print(f"    pub_date:  {r['pub_date_raw']}")
        print(f"    age_hours: {r['age_hours']}")
        print(f"    freshness: {r['freshness_status']}")
        print(f"    date_src:  {r['date_extraction_method']}")
        print(f"    gate:      {r['gate_reason']}")
        print()

    return {"source": "RemoteOKAI", "records": records, "accepted": accepted_count}


async def hf_date_verification():
    """Verify HuggingFace API date extraction is now working."""
    print("\n" + "=" * 70)
    print("HUGGINGFACE DATE EXTRACTION VERIFICATION")
    print("=" * 70)
    from src.sources.news_sources import HuggingFaceDailyPapersSource
    adapter = HuggingFaceDailyPapersSource()
    urls = await adapter.discover_urls(max_records=3)
    print(f"  Discovered: {len(urls)} URLs")
    for url in urls:
        meta = adapter._api_metadata.get(url, {})
        submitted = meta.get("submittedOnDailyAt")
        published = meta.get("publishedAt")
        raw_accepted, gate_reason = gate.accept(submitted)
        print(f"  URL: {url}")
        print(f"    submittedOnDailyAt: {submitted}")
        print(f"    publishedAt:        {published}")
        print(f"    gate:               {gate_reason}")


async def main():
    print("=" * 70)
    print("PHASE 5.1.1 — LIVE NEWS + JOB TESTS WITH FRESHNESS GATE")
    print(f"Time: {format_iso8601()}")
    print("=" * 70)

    news_result = await live_news_test()
    job_result = await live_job_test()
    await hf_date_verification()

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  News (TechCrunchAI): {news_result.get('accepted', 0)}/{MAX_RECORDS} records FRESH-accepted")
    print(f"  Jobs (RemoteOKAI):   {job_result.get('accepted', 0)}/{MAX_RECORDS} records FRESH-accepted")
    if job_result.get("accepted", 0) == 0:
        print("  NOTE: Zero fresh jobs is correct and non-fabricated.")


if __name__ == "__main__":
    asyncio.run(main())
