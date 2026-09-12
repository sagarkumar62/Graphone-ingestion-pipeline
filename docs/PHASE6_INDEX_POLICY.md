# PHASE 6 SEARCH INDEX POLICY

**Date:** September 11, 2026  
**Pipeline Codebase:** `graphone-ingestion-pipeline`  
**Database:** `pipeline.db` (SQLite / PostgreSQL compatible)

---

## 1. Overview

To optimize performance for downstream graph analysis, entity resolution, semantic search filtering, and reporting queries, secondary B-tree indexes have been defined on the `research_papers` table in `src/storage/database.py`.

---

## 2. Index Registry & Query Justifications

| Index Name | Target Column(s) | Supported Query Pattern | Performance Benefit | Write Overhead |
| :--- | :--- | :--- | :--- | :--- |
| `idx_research_papers_published_date` | `published_date DESC` | Recent paper lookups, date range filtering, chronologically ordered feeds | Prevents full table scan on date sorting | Minimal (1 integer/ISO string insert per row) |
| `idx_research_papers_primary_category` | `primary_category` | Filtering papers by arXiv category (e.g. `cs.AI`, `cs.CL`, `cs.CV`) | Instant category grouping and stats | Low (low-cardinality category strings) |
| `idx_research_papers_github_stars` | `github_stars DESC` | Ranking top open-source research codebases by popularity | Fast top-K queries for viral AI research | Minimal (NULLs indexed efficiently) |
| `idx_research_papers_arxiv_id` | `arxiv_id` | Direct ID lookup, cross-referencing citations | $O(\log N)$ exact lookup | Minimal |
| `idx_research_papers_enrichment_status` | `enrichment_status` | Incremental reprocessing pipeline (`SELECT WHERE status='PENDING'`) | Fast queue polling for enrichment jobs | Low |

---

## 3. Implementation Verification

All secondary indexes are created automatically during database initialization via `DatabaseManager.init_db()` in `src/storage/database.py` using `CREATE INDEX IF NOT EXISTS` DDL statements.
