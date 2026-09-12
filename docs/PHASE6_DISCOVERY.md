# PHASE 6 DISCOVERY ASSESSMENT & SYSTEM AUDIT

**Date:** September 11, 2026  
**Pipeline Codebase:** `graphone-ingestion-pipeline`  
**Scope:** Pre-implementation architecture, database schema, and enrichment discovery for Phase 6.

---

## 1. Executive Summary

Phase 6 builds upon the completed Phase 5 ingestion baseline of **1,006 legitimate production research papers** (and **74 isolated test/legacy fixtures**). The goal of Phase 6 is to transform this raw ingested dataset into a production-grade, search-ready, data-audited, and incrementally enrichable corpus without redesigning the system, fabricating metadata, or deleting legitimate records.

---

## 2. Current Architecture & Component Assessment

### 2.1 Core Ingestion & Storage Architecture
- **Database Engine:** `aiosqlite` (Async SQLite for local execution, compatible with PostgreSQL schema concepts). Managed via `DatabaseManager` in `src/storage/database.py`.
- **Entity Model:** `CanonicalEntity` and table-specific rows. The `research_papers` table stores both top-level metadata columns (`title`, `authors_json`, `published_date`, `github_url`, `github_stars`) and raw payload facts in `data_json`.
- **Repository Pattern:** `EntityRepository` in `src/storage/repositories.py` provides atomic `INSERT OR REPLACE` (UPSERT) semantics on `source_url`.
- **Source Adapters:** `ArXivAdapter` (`src/sources/arxiv.py`) queries official arXiv Atom XML (`http://export.arxiv.org/api/query`) and parses metadata via `ArXivDOMParser` (`src/crawlers/arxiv_parser.py`).
- **Deduplication:** Canonical URL normalization, SHA256 hashing, and `deduplication_store` table prevent re-ingesting processed URLs.

### 2.2 Existing `research_papers` Database Schema
```sql
CREATE TABLE IF NOT EXISTS research_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    paper_url TEXT NOT NULL,
    github_url TEXT,
    github_stars INTEGER,
    published_date TEXT NOT NULL,
    data_json TEXT NOT NULL,
    collected_at TEXT NOT NULL
);
```

### 2.3 Existing Indexes
- `idx_canonical_entities_type_norm_name` on `canonical_entities(entity_type, normalized_name)`
- Unique constraint on `research_papers(source_url)`
- Unique constraint on `deduplication_store(url_hash)`

### 2.4 GitHub Enrichment Mechanism
- Class `GitHubEnricher` in `src/enrichment/github.py` regex-extracts repository URLs from arXiv text/HTML and queries `https://api.github.com/repos/{owner}/{repo}` for `stargazers_count`.
- Current limitation: No explicit state machine tracking whether enrichment was attempted, failed, or skipped due to absence of GitHub URL.

---

## 3. Test Fixture & Production Record Isolation Criteria

The production database `pipeline.db` currently contains 1,080 total rows in `research_papers`:
- **1,006 Legitimate Production Records:** Traceable directly to live arXiv abstract landing pages (`https://arxiv.org/abs/...`).
- **74 Test/Legacy Fixtures:** Created during unit/integration tests with URLs containing:
  - `test-paper-`
  - `test_id=`
  - `test_raw_`
  - `test_checkpoint_`

**Isolation Guarantee:** All Phase 6 quality audits, export routines, and index queries must filter out test fixtures deterministically using `source_url NOT LIKE '%test-%'` criteria. Test records are preserved for unit tests but excluded from production analytics.

---

## 4. Safe Extension Points for Phase 6

1. **Schema Evolution:** Non-destructive `ALTER TABLE research_papers ADD COLUMN ...` additions for:
   - `arxiv_id` (extracted from `source_url`)
   - `normalized_title` (lowercased, stripped, normalized)
   - `primary_category` (extracted from `data_json["content"]["primaryCategory"]`)
   - `abstract` (extracted from `data_json["content"]["abstract"]`)
   - `content_hash` (deterministic SHA256)
   - `enrichment_status` (`PENDING`, `COMPLETED`, `NO_DATA`, `RETRYABLE_FAILURE`, `PERMANENT_FAILURE`)
   - `enrichment_updated_at` (ISO timestamp)
2. **Indexing:** Add secondary B-tree indexes for fast queries on `published_date`, `primary_category`, `github_stars`, `arxiv_id`, and `enrichment_status`.
3. **Deterministic Utilities:** Add `src/utils/normalization.py` and `src/utils/hashing.py` without external LLM dependencies.
4. **Semantic Search Abstraction:** Introduce `EmbeddingProvider` interface in `src/embedding/base.py` with mock/deterministic implementations.
5. **Incremental Enrichment Pipeline:** Script `scripts/enrich_papers.py` that processes only pending/failed records with rate limits.
6. **Security Audit Script:** `scripts/security_audit_phase6.py` scanning for secret leaks, unsafe queries, and SSRF risks.
