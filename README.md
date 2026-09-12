# GraphOne / FrontierAtlas AI Engineer Ingestion Pipeline

Production-grade, asynchronous, fault-tolerant AI & Data Ingestion Pipeline for startups, products, research papers (with GitHub metrics), 24-hr fresh jobs, and news signals.

---

## 📌 Executive Summary & Assessment Scope
GraphOne / FrontierAtlas requires an enterprise ingestion graph spanning startups, products, research papers (with GitHub metrics), 24-hr fresh jobs, and real-time news signals.

This repository implements the complete end-to-end technical pipeline architecture:
- **Phase I Bulk Extraction:** Asynchronous scraping engine with rate limiting and checkpointing for large directories.
- **Phase II High-Fidelity Signal Ingestion:** Live crawl adapters for AI news and AI job boards with strict 24-hour freshness gating based solely on source publication timestamps.
- **Phase III Multi-Tier LLM Orchestration:** Fallback chain (**Gemini 2.5 Flash &rarr; Groq compound &rarr; DeepSeek**) with HTTP 413 structural chunking and HTTP 429 full jitter exponential backoff.
- **Phase IV Deterministic Entity Resolution:** Multi-stage canonical normalization (Unicode NFKC, legal suffix removal, seed dictionary, composite evidence) preventing false-positive merges.
- **Phase V Asynchronous Crawlers & Anti-Bot Strategy:** Async HTTP (`httpx`) and headless browser (`Playwright Async`) with circuit breakers and Cloudflare classification.
- **Phase VI Scalable Production Architecture:** Comprehensive 500,000+ records/day architecture based on **Apache Kafka** as the primary production queue, documented in `docs/ARCHITECTURE.pdf`.

---

## 🛠️ Tech Stack & Technology Principles
- **Language:** Python 3.11+ / 3.12
- **Async Framework:** `asyncio`
- **Crawlers:** `httpx` (async HTTP) + `Playwright Async` (SPA headless browser fallback)
- **Validation:** `pydantic-settings` + `jsonschema` (Draft-07)
- **LLM Provider Chain:** 3-Tier Fallback (**Gemini 2.5 Flash $\rightarrow$ Groq compound $\rightarrow$ DeepSeek**) with 413 payload chunking & 429 jitter backoff
- **Entity Resolution:** Deterministic multi-stage normalization (Unicode NFKC, legal suffix removal, seed dictionary, composite evidence matching)
- **Storage Strategy:**
  - **IMPLEMENTED (Demo/Local):** SQLite (`pipeline.db`) via `aiosqlite` with atomic upsert primitives and local raw staging (`data/raw/`).
  - **DESIGNED (Production Scale):** Managed PostgreSQL, pgvector / Qdrant, Neo4j property graph, and AWS S3 object storage.
  - **OPTIONAL / PLANNED:** Redis Sentinel/Cluster for distributed rate limiting and atomic claim locking.
- **Primary Queue:** **Apache Kafka** (DESIGNED production queue for partition-level ordering, replayable logs, and backpressure).

---

## 📁 Project Structure

```text
src/
├── core/
│   ├── config.py           # Pydantic environment configuration
│   ├── logging.py          # Structured JSON logger
│   ├── models.py           # Domain models & Pydantic schemas
│   └── exceptions.py       # Custom pipeline exception hierarchy
├── storage/
│   ├── database.py         # Async SQLite connection manager (PostgreSQL compatible)
│   ├── repositories.py     # Relational entity, audit, and DLQ repositories
│   └── migrations/
├── validators/
│   └── schema_validator.py # JSON Schema Draft-07 validator
├── crawlers/
│   ├── base.py             # Abstract crawler with exponential backoff & jitter
│   ├── http.py             # Async HTTP crawler (httpx)
│   └── playwright.py       # Playwright Async SPA browser crawler
├── llm/
│   ├── providers/
│   │   ├── base.py         # Abstract LLM provider interface
│   │   ├── gemini.py       # Gemini 2.5 Flash adapter (Tier 1 - LIVE VERIFIED)
│   │   ├── groq.py         # Groq compound adapter (Tier 2 - LIVE VERIFIED)
│   │   └── deepseek.py     # DeepSeek adapter (Tier 3 - NOT LIVE VERIFIED)
│   ├── chunker.py          # 413 Context window payload chunker & HTML cleaner
│   ├── retry.py            # Exponential backoff retries helper
│   └── orchestrator.py     # Multi-tier fallback orchestrator
├── resolver/
│   ├── normalizer.py       # Multi-stage string normalizer
│   ├── seed.py             # Seed entity & alias dictionary
│   ├── matcher.py          # Deterministic resolver & composite matcher
│   ├── fuzzy.py            # Jaro-Winkler distance algorithm
│   └── audit.py            # Entity resolution audit logger
├── enrichment/
│   └── github.py           # GitHub URL parser & live star counter
├── pipeline/
│   ├── freshness.py        # 24-hr signal freshness validator
│   ├── deduplication.py    # URL SHA256 & SimHash deduplication
│   └── processor.py        # E2E Vertical Slice Processor
└── utils/
    ├── hashing.py          # URL canonicalization & hashing
    └── time.py             # ISO-8601 formatting & relative date parsing

docs/                       # Architecture & design specifications
schemas/                    # Canonical JSON Schemas (6 schemas)
tests/                      # Unit & Integration test suite
main.py                     # E2E Vertical Slice CLI entrypoint
```

---

## 🚀 Quick Start Guide

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key settings in `.env`:
- `GEMINI_API_KEY`: API key for Gemini 2.5 Flash (Tier 1 Primary).
- `GROQ_API_KEY`: API key for Groq compound (Tier 2 Secondary).
- `DEEPSEEK_API_KEY`: API key for DeepSeek (Tier 3 Tertiary).
- `DATABASE_URL`: `sqlite+aiosqlite:///./pipeline.db` (default).

*(Note: If LLM API keys are unconfigured, the pipeline operates with deterministic rule-based extractions and graceful fallbacks).*

---

## 🧪 Running the Pipeline & Verification

### Run Vertical Slice Execution
```bash
python main.py
```

### Run Batch Ingestion (ArXiv / News)
```bash
python -m src.pipeline.batch_processor
```

### Run Full Test Suite
```bash
pytest tests/unit/ -q
```
*Current unit test suite passing: 117 passed, 0 failed, 2 warnings in ~22s (Exit Code 0).*

---

## 📊 Data Provenance & Anti-Fabrication Principles
1. **Zero Fabrication:** The pipeline never invents attributes or values. If an attribute (e.g. employee count, funding total) is missing from raw source text, it is set to `None`/`null`.
2. **Strict URL Traceability:** Every canonical record in the database maps to an authentic, reachable `source.url`.
3. **Publication Timestamp Rule:** Freshness is computed exclusively from source-declared publication timestamps (JSON-LD, OpenGraph, HTML `<time>`, URL date patterns). The crawler collection time (`collectedAt`) is **never** substituted for publication time.
4. **No Synthetic Inflation:** The repository refuses to generate synthetic fake records to hit arbitrary volume quotas.

---

## 📑 Overall Submission Status & Documented Limitations

### Overall Status: `SUBMISSION READY WITH DOCUMENTED LIMITATIONS`

### 1. Dataset Status & Provenance
- **Startups (1,134 records exported):** 1,134 production startup/company candidates with legitimate source provenance. YC explicitly establishes startup status for the YC record; GitHub organization evidence establishes authentic technology-company/software-entity evidence but does not universally establish funding stage or venture-backed startup status. In a deterministic adversarial audit of 151 sampled records, 151/151 were defensible, 0 were false positives, 0 were fabricated, and 0 were synthetic.
- **Products (1,501 records exported):** 1,501 production records with valid provenance and GitHub repository metrics.
- **Research Papers (1,009 records exported):** 1,009 production records from arXiv and Papers with Code with authentic GitHub repository links and star counts.
- **Jobs (683 fresh records exported / 1,275 DB total):** Exactly 24-hour freshness enforced. 683 fresh jobs included in final deliverable export; 592 stale/rejected postings excluded.
- **News (14 fresh records exported / 28 DB total):** 5 AI news sources monitored:
  - *Clearly Qualifies:* TechCrunch AI, MIT Technology Review AI, OpenAI Blog
  - *Borderline:* Hugging Face Daily Papers, Hacker News AI
  - *OpenAI Blog Note:* RSS feed accessible; article detail GET encounters Cloudflare HTTP 403 (no anti-bot bypass mechanisms used).
  - *Requirement Status:* **PARTIAL** under strict interpretation of 5 dedicated AI news sources.
- **Entity Mappings (865 records exported):** Deterministic canonical resolution log with seed dictionary and confidence thresholds.

### 2. Multi-Tier LLM Orchestration
- **Tier 1:** Gemini 2.5 Flash (**LIVE VERIFIED**)
- **Tier 2:** Groq Llama 3.3 70B (**LIVE VERIFIED**)
- **Tier 3:** DeepSeek (**CONFIGURED / NOT LIVE VERIFIED**)
- HTTP 413 context window structural chunking and HTTP 429 full-jitter exponential backoff implemented and verified. Zero synthetic fallback data.

### 3. Architecture & Infrastructure Classification
- **IMPLEMENTED / DEMO (Local Workspace):** SQLite (`pipeline.db`), local filesystem raw payload storage (`data/raw/`), async HTTP/Playwright crawler engine, LLM orchestrator, deterministic entity resolver.
- **DESIGNED FOR PRODUCTION SCALE:** Managed PostgreSQL, **Apache Kafka** (PRIMARY event stream & queue architecture), Redis supporting infrastructure, pgvector / Qdrant vector storage, Neo4j property graph, AWS S3 / MinIO object storage, Kubernetes container deployment.
- **Capacity Model:** All 500,000+ records/day throughput figures are explicitly designated as **ASSUMPTIONS / DESIGN CAPACITY** (theoretical capacity model, not measured production throughput).

### 4. Unit Test Suite
- **117 passed, 0 failed, 0 skipped, 2 warnings in ~22s** (`pytest tests/unit/`).

