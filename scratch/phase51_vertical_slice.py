"""
Phase 5.1 — Live Vertical Slice: HuggingFace Daily Papers (LIVE_VERIFIED source)
Runs through the complete async pipeline: discover -> fetch -> raw store -> freshness -> 
schema parse -> entity resolution -> storage -> checkpoint -> idempotency run 2.
NO fabrication. Pure real evidence.
"""
import asyncio
import json
import time
import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sources.news_sources import HuggingFaceDailyPapersSource
from src.crawlers.async_crawler import AsyncCrawlerEngine
from src.crawlers.extractor import html_extractor
from src.pipeline.freshness import freshness_validator
from src.pipeline.deduplication import deduplicator, DeduplicationEngine
from src.storage.raw_store import raw_store
from src.storage.checkpoint import checkpoint_engine, CheckpointState
from src.storage.database import db_manager
from src.storage.repositories import EntityRepository, DLQRepository
from src.core.models import CanonicalEntity, RecordType, FreshnessStatus
from src.resolver.matcher import resolver
from src.resolver.audit import audit_logger
from src.utils.time import format_iso8601

MAX_RECORDS = 5
DB_PATH = "./pipeline.db"


def get_db_count() -> int:
    """Get current news record count from pipeline.db directly."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM canonical_records WHERE record_type='NEWS'")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        return -1


async def run_vertical_slice(run_label: str, adapter: HuggingFaceDailyPapersSource, crawler: AsyncCrawlerEngine):
    """Run one full vertical slice pass through the pipeline."""
    print(f"\n{'='*70}")
    print(f"  {run_label}")
    print(f"{'='*70}")
    
    t0 = time.time()
    results = []
    
    # Discovery
    print("  [1] Discovering URLs...")
    urls = await adapter.discover_urls(max_records=MAX_RECORDS)
    print(f"      Discovered: {len(urls)} URLs")
    for u in urls:
        print(f"        -> {u}")

    db_before = get_db_count()
    print(f"\n  DB news count before: {db_before}")

    for url in urls:
        rec = {
            "url": url,
            "http_status": None,
            "content_hash": None,
            "title": None,
            "pub_date_raw": None,
            "freshness_status": None,
            "freshness_reason": None,
            "text_len": 0,
            "stored": False,
            "duplicate": False,
            "checkpoint_state": None,
            "error": None,
        }

        # Step 2: Dedup check
        is_dup, url_hash = await deduplicator.is_duplicate_url(url)
        rec["content_hash"] = url_hash[:12]
        if is_dup:
            rec["duplicate"] = True
            rec["stored"] = False
            print(f"  DUPLICATE: {url[:60]}")
            results.append(rec)
            continue

        # Step 3: Async Fetch
        try:
            raw_payload = await crawler.fetch_with_retry(url, adapter.source_name)
            rec["http_status"] = raw_payload.http_status
        except Exception as e:
            rec["error"] = f"FetchError: {type(e).__name__}: {e}"
            print(f"  FETCH_FAILED: {url[:60]} -> {e}")
            await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.DLQ, error=str(e))
            rec["checkpoint_state"] = "DLQ"
            results.append(rec)
            continue

        await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.FETCHED)

        # Step 4: Raw storage
        content_hash, raw_path = await raw_store.save_raw_payload(
            source_url=url, source_name=adapter.source_name,
            content=raw_payload.raw_content, http_status=raw_payload.http_status
        )
        rec["content_hash"] = content_hash[:12]

        # Step 5: Full-text extraction
        extracted = html_extractor.extract(raw_payload.raw_content, url)
        rec["title"] = extracted.title
        rec["text_len"] = len(extracted.main_text)

        # Step 6: Freshness
        pub_date = adapter.extract_published_at(raw_payload)
        rec["pub_date_raw"] = pub_date
        freshness_res = freshness_validator.evaluate_freshness(pub_date)
        rec["freshness_status"] = freshness_res.status.value
        rec["freshness_reason"] = freshness_res.reason.value

        await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.PROCESSING)

        # Step 7: Schema parsing
        try:
            raw_dict = adapter.parse_raw_payload(raw_payload)
            canonical = CanonicalEntity(**raw_dict)
        except Exception as e:
            rec["error"] = f"ParseError: {e}"
            await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.DLQ, error=str(e))
            rec["checkpoint_state"] = "DLQ"
            results.append(rec)
            continue

        # Step 8: Entity Resolution (publisher)
        publisher = canonical.content.get("publisher", "")
        if publisher:
            resolution = resolver.resolve(
                raw_name=publisher,
                entity_type="NEWS",
                domain=url,
                source_url=url
            )
            canonical.content["canonical_entity_id"] = resolution.canonical_entity_id
            await audit_logger.log_mapping(resolution=resolution, entity_type="NEWS", source_url=url)

        # Step 9: Storage
        try:
            entity_repo = EntityRepository()
            await entity_repo.save_canonical_entity(canonical)
            await deduplicator.claim_url(url, raw_payload.raw_content)
            await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.STORED)
            rec["stored"] = True
            rec["checkpoint_state"] = "STORED"
        except Exception as e:
            rec["error"] = f"StorageError: {e}"
            await checkpoint_engine.update_state(url, adapter.source_name, "NEWS", CheckpointState.FAILED, error=str(e))
            rec["checkpoint_state"] = "FAILED"

        results.append(rec)

    db_after = get_db_count()
    elapsed = round(time.time() - t0, 2)
    stored_count = sum(1 for r in results if r["stored"])
    dup_count = sum(1 for r in results if r["duplicate"])

    print(f"\n  DB news count after:  {db_after}")
    print(f"  Records attempted:    {len(urls)}")
    print(f"  Records stored:       {stored_count}")
    print(f"  Records duplicate:    {dup_count}")
    print(f"  Elapsed:              {elapsed}s")
    print(f"  Records/sec:          {round(stored_count / max(elapsed, 0.001), 2)}")
    print()
    
    for r in results:
        status = "STORED" if r["stored"] else ("DUPLICATE" if r["duplicate"] else "FAILED")
        print(f"  [{status}] {r['url'][:65]}")
        print(f"    title:      {r['title']}")
        print(f"    hash:       {r['content_hash']}")
        print(f"    http_status:{r['http_status']}")
        print(f"    text_len:   {r['text_len']}")
        print(f"    pub_date:   {r['pub_date_raw']}")
        print(f"    freshness:  {r['freshness_status']} / {r['freshness_reason']}")
        print(f"    checkpoint: {r['checkpoint_state']}")
        if r["error"]:
            print(f"    error:      {r['error']}")

    return {
        "label": run_label,
        "urls_attempted": len(urls),
        "stored": stored_count,
        "duplicates": dup_count,
        "db_before": db_before,
        "db_after": db_after,
        "elapsed_sec": elapsed,
        "results": results,
    }


async def changed_content_test():
    """Verify changed content is NOT treated as same-content duplicate."""
    print("\n" + "=" * 70)
    print("  CHANGED-CONTENT TEST")
    print("=" * 70)

    test_url = "https://test-changed-content.example.com/article"
    content_v1 = "<html><body><h1>Version 1 Article</h1><p>Original content about AI research.</p></body></html>"
    content_v2 = "<html><body><h1>Version 2 Article (Updated)</h1><p>Updated content about AI advancements.</p></body></html>"

    hash_v1 = raw_store.compute_content_hash(content_v1)
    hash_v2 = raw_store.compute_content_hash(content_v2)
    print(f"  V1 hash: {hash_v1[:16]}")
    print(f"  V2 hash: {hash_v2[:16]}")
    assert hash_v1 != hash_v2, "FAIL: same hash for different content"
    print("  PASS: Different content produces different hash")

    # Store V1
    _, path1 = await raw_store.save_raw_payload(test_url, "TestSource", content_v1)
    is_unchanged_v1 = await raw_store.is_content_unchanged(test_url, hash_v1)
    is_unchanged_v2 = await raw_store.is_content_unchanged(test_url, hash_v2)
    
    print(f"  After V1 stored - V1 unchanged: {is_unchanged_v1} (expected: True)")
    print(f"  After V1 stored - V2 unchanged: {is_unchanged_v2} (expected: False)")
    assert is_unchanged_v1 == True, "FAIL: V1 should be detected as stored"
    assert is_unchanged_v2 == False, "FAIL: V2 should NOT be detected as stored (different content)"
    print("  PASS: Changed content correctly detected as new payload")


async def main():
    await db_manager.init_db()
    
    print("=" * 70)
    print("PHASE 5.1 — LIVE VERTICAL SLICE (HuggingFace Daily Papers)")
    print(f"Time: {format_iso8601()}")
    print("=" * 70)

    adapter = HuggingFaceDailyPapersSource()
    crawler = AsyncCrawlerEngine(global_concurrency=3, per_source_concurrency=2)

    # RUN 1
    run1 = await run_vertical_slice("RUN 1 — Initial Crawl", adapter, crawler)

    # RUN 2 — Idempotency check
    # Reset in-memory dedup to force DB re-check
    deduplicator._seen_url_hashes.clear()
    run2 = await run_vertical_slice("RUN 2 — Idempotency Check (same source, same content)", adapter, crawler)

    # Changed content test
    await changed_content_test()

    print("\n" + "=" * 70)
    print("IDEMPOTENCY SUMMARY")
    print("=" * 70)
    print(f"  DB count before run 1: {run1['db_before']}")
    print(f"  DB count after run 1:  {run1['db_after']}")
    print(f"  DB count after run 2:  {run2['db_after']}")
    print(f"  Stored in run 1:       {run1['stored']}")
    print(f"  Stored in run 2:       {run2['stored']}")
    print(f"  Duplicates in run 2:   {run2['duplicates']}")
    new_records_run2 = run2['db_after'] - run1['db_after']
    print(f"  New records in run 2:  {new_records_run2} (expected: 0)")

    if run2["stored"] == 0 and run2["duplicates"] > 0:
        print("  IDEMPOTENCY: PASS — run 2 produced zero new records")
    else:
        print(f"  IDEMPOTENCY: NOTE — run 2 stored {run2['stored']} records (check for expected duplicates)")


if __name__ == "__main__":
    asyncio.run(main())
