import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sources.registry import registry
from src.pipeline.async_pipeline import async_pipeline_processor
from src.pipeline.metrics import metrics_collector
from src.core.models import RecordType
from src.core.logging import logger

async def run_phase5_live_demo():
    print("=" * 80)
    print("PHASE 5 — ASYNC CRAWLING, FRESHNESS, AND SOURCE EXPANSION DEMO")
    print("=" * 80)

    target_sources = [
        ("arxiv", RecordType.RESEARCH_PAPER, 3),
        ("huggingfacedailypapers", RecordType.NEWS, 3),
        ("techcrunchai", RecordType.NEWS, 2),
        ("remoteokai", RecordType.JOB, 2),
    ]

    total_discovered_urls = []

    for source_key, rec_type, limit in target_sources:
        adapter = registry.get(source_key)
        if not adapter:
            print(f"[!] Source adapter '{source_key}' not found in registry.")
            continue

        print(f"\n[+] Discovering records for source: {adapter.source_name} ({rec_type.value}, max={limit})...")
        try:
            urls = await adapter.discover_urls(max_records=limit)
            await metrics_collector.record_discovered(adapter.source_name, len(urls))
            print(f"    Discovered {len(urls)} URLs: {urls[:2]}...")
            for url in urls:
                total_discovered_urls.append((url, adapter.source_name, rec_type))
        except Exception as e:
            print(f"    Discovery failed for {adapter.source_name}: {e}")

    print(f"\n[+] Total Discovered URLs across sources: {len(total_discovered_urls)}")
    print("[+] Starting high-concurrency async crawling and processing batch...")

    tasks = [
        async_pipeline_processor.process_record(url, src_name, rec_type)
        for url, src_name, rec_type in total_discovered_urls
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    print("\n" + "=" * 80)
    print("CRAWL & INGESTION RESULTS SUMMARY")
    print("=" * 80)

    for i, res in enumerate(results):
        url, src_name, _ = total_discovered_urls[i]
        if isinstance(res, Exception):
            print(f"[{i+1}/{len(results)}] FAILED ({src_name}) -> {url}: {res}")
        else:
            status_code, entity, meta = res
            print(f"[{i+1}/{len(results)}] {status_code.value:<28} | Source: {src_name:<22} | URL: {url[:50]}")
            if meta.get("entity_resolved"):
                print(f"    Entity Resolution: {meta['entity_resolved']}")
            if meta.get("freshness"):
                print(f"    Freshness Status: {meta['freshness']}")

    print("\n" + "=" * 80)
    print("TELEMETRY METRICS & OBSERVABILITY REPORT")
    print("=" * 80)

    metrics_summary = metrics_collector.get_summary()
    import json
    print(json.dumps(metrics_summary, indent=2))
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_phase5_live_demo())
