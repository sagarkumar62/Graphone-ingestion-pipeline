# GraphOne / FrontierAtlas AI Engineer Ingestion Pipeline

Production-oriented, asynchronous, fault-tolerant AI & Data Ingestion Pipeline for startups, products, research papers (with GitHub metrics), 24-hr fresh jobs, and news signals.

---

## 📌 Executive Summary & Assessment Scope
GraphOne / FrontierAtlas requires an enterprise ingestion graph spanning startups, products, research papers (with GitHub metrics), 24-hr fresh jobs, and real-time news signals.

This repository implements the core ingestion pipeline and documents the complete production-scale architecture, with local/demo infrastructure clearly separated from production design:
- **Phase I Bulk Extraction:** Asynchronous scraping engine with rate limiting and checkpointing for large directories.
- **Phase II High-Fidelity Signal Ingestion:** Live crawl adapters for AI news and AI job boards with strict 24-hour freshness gating based solely on source publication timestamps.
- **Phase III Multi-Tier LLM Orchestration:** Fallback chain (**Gemini 2.5 Flash &rarr; Groq compound &rarr; DeepSeek**) with HTTP 413 structural chunking and HTTP 429 full jitter exponential backoff.
- **Phase IV Deterministic Entity Resolution:** Multi-stage canonical normalization (Unicode NFKC, legal suffix removal, seed dictionary, composite evidence) preventing false-positive merges.
- **Phase V Asynchronous Crawlers & Anti-Bot Strategy:** Async HTTP (`httpx`) and headless browser (`Playwright Async`) with circuit breakers and Cloudflare classification.
- **Phase VI Scalable Production Architecture:** Comprehensive 500,000+ records/day architecture based on **Apache Kafka** as the primary production queue, documented in [`docs/ARCHITECTURE.pdf`](docs/ARCHITECTURE.pdf).

---

## 🛠️ Tech Stack & Technology Principles
- **Language:** Python 3.11+ / 3.12 (Tested on Python 3.12.5)
- **Async Framework:** `asyncio`
- **Crawlers:** `httpx` (async HTTP) + `Playwright Async` (SPA headless browser fallback)
- **Validation:** `pydantic-settings` + `jsonschema` (Draft-07)
- **LLM Provider Chain:** 3-Tier Fallback (**Gemini 2.5 Flash** `LIVE VERIFIED` $\rightarrow$ **Groq compound** `LIVE VERIFIED` $\rightarrow$ **DeepSeek** `CONFIGURED / NOT LIVE VERIFIED`) with 413 payload chunking & 429 jitter backoff
- **Entity Resolution:** Deterministic multi-stage normalization (Unicode NFKC, legal suffix removal, seed dictionary, composite evidence matching)
- **Storage Strategy:**
  - **IMPLEMENTED (Demo/Local):** SQLite (`pipeline.db`) via `aiosqlite` with atomic upsert primitives and local raw staging (`./data/raw/`).
  - **DESIGNED FOR PRODUCTION SCALE (Not Deployed):** Managed PostgreSQL, pgvector / Qdrant, Neo4j property graph, and AWS S3 object storage.
  - **OPTIONAL / PLANNED:** Redis Sentinel/Cluster for distributed rate limiting and atomic claim locking.
- **Primary Queue:** **Apache Kafka** (DESIGNED production queue for partition-level ordering, replayable logs, and backpressure; NOT DEPLOYED locally).

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
│   │   └── deepseek.py     # DeepSeek adapter (Tier 3 - CONFIGURED / NOT LIVE VERIFIED)
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

scripts/
├── export_sheets.py        # Data exporter for 6 canonical tabs (CSV/JSON)
└── publish_to_google_sheets.py # Google Sheets publisher script

docs/                       # Architecture & design specifications
schemas/                    # Canonical JSON Schemas (6 schemas)
tests/                      # Unit & Integration test suite
main.py                     # E2E Vertical Slice CLI entrypoint
.env.example                # Environment configuration template (Source of truth for env vars)
```

---

## 🚀 Quick Start Guide & Setup Instructions

### 1. Prerequisites
- **Python:** Python 3.11+ or 3.12 (Python 3.12 recommended).
- **Virtual Environment:** Recommended to prevent global package conflicts.
- **Headless Browser:** Playwright Chromium binaries (required for JavaScript dynamic SPA crawling).

#### Environment Creation & Dependencies Installation
```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install repository dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

```bash
# Linux / macOS (Bash / Zsh)
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

---

### 2. Environment Configuration

Copy `.env.example` to create your local `.env` configuration file:

```powershell
# Windows (PowerShell / CMD)
copy .env.example .env
```

```bash
# Linux / macOS
cp .env.example .env
```

> [!IMPORTANT]
> **Security Rules:**
> - Fill only the credentials and configuration variables required for your environment.
> - **NEVER commit `.env`** to source control (enforced via `.gitignore`).
> - **NEVER commit Google Cloud Service Account JSON credentials** (`credentials.json`).
> - [`.env.example`](.env.example) is the source of truth for configuration keys and must only contain safe, placeholder values.

---

### 3. Environment Variable Reference

The pipeline relies on `pydantic-settings` to load configuration from environment variables or `.env`. Below is the complete reference table corresponding 1-to-1 with [`.env.example`](.env.example):

| Variable | Required? | Purpose | Example / Allowed Value |
|----------|-----------|---------|-------------------------|
| `ENVIRONMENT` | No | Target runtime environment mode (`development`, `staging`, `production`) | `development` |
| `LOG_LEVEL` | No | Log output verbosity for structured JSON logger (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `DATABASE_URL` | No | Relational database connection URI (SQLite via `aiosqlite` default) | `sqlite+aiosqlite:///./pipeline.db` |
| `RAW_STORAGE_DIR` | No | Local filesystem directory path for raw HTML/JSON payload staging | `./data/raw` |
| `MAX_RECORDS` | No | Record count limit per bulk extraction processing pass | `10` |
| `BULK_BATCH_SIZE` | No | Database batch transaction size and checkpoint interval | `50` |
| `CRAWL_CONCURRENCY` | No | Maximum number of concurrent async crawler tasks/workers | `5` |
| `RATE_LIMIT_PER_SECOND` | No | Global HTTP rate limit per target domain (requests/sec) | `2.0` |
| `LLM_PRIMARY_PROVIDER` | No | Tier 1 Primary LLM provider adapter name | `GeminiFlash` |
| `LLM_PRIMARY_MODEL` | No | Primary LLM model identifier (**LIVE VERIFIED**) | `gemini-2.5-flash` |
| `LLM_SECONDARY_PROVIDER` | No | Tier 2 Secondary LLM provider adapter name | `GroqLlama` |
| `LLM_SECONDARY_MODEL` | No | Secondary LLM model identifier (**LIVE VERIFIED**) | `groq/compound` |
| `LLM_TERTIARY_PROVIDER` | No | Tier 3 Tertiary LLM provider adapter name | `DeepSeek` |
| `LLM_TERTIARY_MODEL` | No | Tertiary LLM model identifier (**CONFIGURED / NOT LIVE VERIFIED**) | `deepseek-chat` |
| `GEMINI_API_KEY` | Optional | API key for Google Gemini (Tier 1 Primary). | `your_gemini_api_key_here` |
| `GROQ_API_KEY` | Optional | API key for Groq (Tier 2 Secondary). | `your_groq_api_key_here` |
| `DEEPSEEK_API_KEY` | Optional | API key for DeepSeek (Tier 3 Tertiary). | `your_deepseek_api_key_here` |
| `GITHUB_TOKEN` | Optional | GitHub Personal Access Token for authentic repository star count fetching without rate limits. | `your_github_token_here` |
| `GOOGLE_SHEETS_CREDENTIALS` | Optional | Relative file path to Google Cloud Service Account JSON credentials for export publishing. | `./credentials/google_service_account.json` |
| `GOOGLE_SHEET_ID` | Optional | Target Google Sheet ID string from spreadsheet URL for automated publishing. | `your_google_sheet_id_here` |

> [!NOTE]
> **LLM Provider & Fallback Behavior:**
> - **Gemini 2.5 Flash $\rightarrow$ Groq compound $\rightarrow$ DeepSeek** is the configured fallback chain.
> - **Gemini 2.5 Flash** and **Groq compound** are **LIVE VERIFIED**.
> - **DeepSeek** is **CONFIGURED / NOT LIVE VERIFIED**.
> - If all configured LLM providers fail, the record follows the failure/DLQ path.
> - Deterministic source-specific parsing exists only where explicitly implemented, such as the ArXiv parser.

---

### 4. Google Sheets Export & Publishing Integration

Google Sheets serves as an **export and publishing integration layer** for delivering cleaned canonical datasets to stakeholders. It is **not** used as a primary application database, runtime storage engine, or production queue. The production event stream queue remains **Apache Kafka** (`DESIGNED FOR PRODUCTION SCALE / NOT DEPLOYED`).

#### Configuration & Service Account Setup
1. **Credentials File Path:** Set `GOOGLE_SHEETS_CREDENTIALS` in `.env` to the path of your Google Cloud Service Account key file (e.g. `credentials/google_service_account.json`). Credentials must **never** be committed to source control.
2. **Spreadsheet Access:** Open your target Google Sheet in a browser and share it with the service account's `client_email` (found inside your JSON key file), granting **Editor** permissions.
3. **Spreadsheet ID:** Copy the unique ID string from the spreadsheet URL (`https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit`) and set `GOOGLE_SHEET_ID` in `.env`.

#### Export & Publishing Commands
The exporter script [`scripts/export_sheets.py`](scripts/export_sheets.py) dumps canonical database entities into clean CSV, JSON, and JSONL formats inside `data/exports/`. The Google Sheets publisher script publishes these datasets directly to your target spreadsheet:

```powershell
# Export all 6 canonical tabs to local CSV/JSON files
python scripts/export_sheets.py

# Export startups tab only
python scripts/export_sheets.py --startups-only

# Dry-run Google Sheets publishing
python scripts/publish_to_google_sheets.py --dry-run

# Actual Google Sheets publishing
python scripts/publish_to_google_sheets.py
```

#### Verified Google Sheets Publish
The Google Sheets integration has been live-verified against the configured spreadsheet. The publisher successfully authenticated, validated the required tabs, and wrote the current exported datasets.

The six published tabs are:
- `Startups`
- `Products`
- `Research Papers`
- `Jobs`
- `News`
- `Entity Mapping Log`

The publisher output reports the exact row counts for each publish run.

---

## 🧪 Running the Pipeline & Verification Commands

### Environment Verification & Full Test Suite
Run `python -m pytest tests/ -v --tb=short` to obtain the current test result.

### Run Vertical Slice Execution CLI
Executes end-to-end crawling, extraction, entity resolution, and SQLite storage for a single vertical slice:
```powershell
python main.py
```

### Run Batch Ingestion (ArXiv / News)
Executes asynchronous batch ingestion for arXiv papers and fresh AI news feeds:
```powershell
python -m src.pipeline.batch_processor
```

### Run Google Sheets Export & Publishing
```powershell
# Local export to data/exports/
python scripts/export_sheets.py

# Dry-run Google Sheets publishing
python scripts/publish_to_google_sheets.py --dry-run

# Actual Google Sheets publishing
python scripts/publish_to_google_sheets.py
```

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
- **Research Papers (1,008 records exported):** 1,008 production records from arXiv and Papers with Code with authentic GitHub repository links and star counts.
- **Jobs (683 fresh records exported / 1,275 DB total):** Exactly 24-hour freshness enforced. 683 fresh jobs included in final deliverable export; 592 stale/rejected postings excluded.
- **News (14 fresh records exported / 28 DB total):** 5 AI news sources monitored:
  - *Clearly Qualifies:* TechCrunch AI, MIT Technology Review AI, OpenAI Blog
  - *Borderline:* Hugging Face Daily Papers, Hacker News AI
  - *OpenAI Blog Note:* RSS feed accessible; article detail GET encounters Cloudflare HTTP 403 (no anti-bot bypass mechanisms used).
  - *Requirement Status:* **PARTIAL PASS** under strict interpretation of 5 dedicated AI news sources.
- **Entity Mappings (870 records exported):** Deterministic canonical resolution log with seed dictionary and confidence thresholds (verified directly from `data/exports/entity_mappings.csv`).

### 2. Multi-Tier LLM Orchestration & Provider Verification
- **Tier 1:** Gemini 2.5 Flash (`gemini-2.5-flash`) — **LIVE VERIFIED**
- **Tier 2:** Groq compound (`groq/compound`) — **LIVE VERIFIED**
- **Tier 3:** DeepSeek (`deepseek-chat`) — **CONFIGURED / NOT LIVE VERIFIED**
- HTTP 413 context window structural chunking and HTTP 429 full-jitter exponential backoff implemented and verified. Zero synthetic fallback data.

### 3. Architecture & Infrastructure Classification
- **IMPLEMENTED (Local Workspace / Demo):** SQLite (`pipeline.db`), local filesystem raw payload storage (`./data/raw/`), async HTTP/Playwright crawler engine, LLM orchestrator, deterministic entity resolver.
- **DESIGNED FOR PRODUCTION SCALE (Not Deployed):** Managed PostgreSQL, **Apache Kafka** (PRIMARY event stream & queue architecture), Redis supporting infrastructure, pgvector / Qdrant vector storage, Neo4j property graph, AWS S3 / MinIO object storage, Kubernetes container deployment, distributed production workers.
- **Capacity Model:** All 500,000+ records/day throughput figures are explicitly designated as **ASSUMPTIONS / DESIGN CAPACITY** (theoretical capacity model, not measured production throughput).

### 4. Phase 5.1 Status
- **PARTIAL PASS**

### 5. Automated Test Suite Status
Run `python -m pytest tests/ -v --tb=short` to obtain the current test result.
