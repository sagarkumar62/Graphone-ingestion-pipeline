# Scalability & Capacity Planning: GraphOne / FrontierAtlas Ingestion Pipeline

## Executive Strategy
The pipeline architecture is designed to scale horizontally from **10 records** (Phase 2A baseline demo) to **500,000+ records** (production enterprise scale) with **zero modifications to application code**. Scalability is achieved purely through configuration adjustments (`MAX_RECORDS`, `CRAWL_CONCURRENCY`, `BULK_BATCH_SIZE`), queue partitioning, raw object storage, database indexing/partitioning, and horizontal container worker scaling.

---

## Scale Evolution Tier Comparison

| Metric / Dimension | Tier 1 (10 Records) | Tier 2 (100 Records) | Tier 3 (1,000 Records) | Tier 4 (100,000 Records) | Enterprise Scale (500,000+ Records) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Window** | ~5 seconds | ~30 seconds | ~10 minutes | ~4 hours | ~20 hours continuous |
| **Target Throughput**| 2.0 items/sec | 3.3 items/sec | 5.0 items/sec | 15.0 items/sec | 35.0 items/sec |
| **Config Parameter** | `MAX_RECORDS=10` | `MAX_RECORDS=100` | `MAX_RECORDS=1000` | `MAX_RECORDS=100000` | `MAX_RECORDS=500000` |
| **Concurrency Workers**| 5 Workers | 10 Workers | 20 Workers | 50 Worker Nodes | 150 Worker Containers (K8s HPA) |
| **Discovery Adapter** | ArXiv API / RSS | ArXiv API Paginated | Source Adapters (OAI-PMH) | Sharded Discovery Crawlers | Distributed Source Adapters |
| **Raw Payload Store** | Local Filesystem (`data/raw/`) | Local Filesystem | S3 / MinIO Object Storage | AWS S3 Bucket Cluster | Distributed Object Storage |
| **Database Tier** | SQLite (`pipeline.db`) | SQLite | PostgreSQL (Managed RDS) | PostgreSQL + Read Replicas | PostgreSQL Partitioned Cluster |

---

## Architectural Scaling Components

### 1. Source Adapter Discovery & Pagination
- **Source Adapters (`src/sources/`):** Source discovery is completely decoupled from core processing code via `BaseSourceAdapter` and `SourceRegistry`.
- **Pagination & Cursors:** Discovery methods utilize offset/cursor pagination (`start_offset`, `max_records`) allowing concurrent worker nodes to fetch distinct discovery slices without overlapping.

### 2. Bounded Worker Pool & Backpressure
- **Worker Concurrency (`CRAWL_CONCURRENCY`):** Async worker pools process items from `asyncio.Queue` bounded by `asyncio.Semaphore`, preventing network socket starvation.
- **Source-Aware Rate Limiter (`src/crawlers/rate_limiter.py`):** Domain rate limiters enforce per-second request ceilings, respecting HTTP `Retry-After` headers and applying full jitter exponential backoff on 429 rate limit errors.

### 3. Checkpointing & Idempotency
- **State Checkpointing (`src/storage/checkpoint.py`):** Tracks record lifecycle state (`DISCOVERED` $\rightarrow$ `FETCHED` $\rightarrow$ `PROCESSING` $\rightarrow$ `STORED` $\rightarrow$ `DLQ`). If a process stops after 437/1,000 records, the next run resumes without restarting from zero.
- **Content-Hash Idempotency (`src/storage/raw_store.py`):** Stores SHA256 hashes of raw content. Detects `SAME URL + SAME CONTENT` (skip) vs. `SAME URL + CHANGED CONTENT` (reprocess).

### 4. Database Partitioning & Indexing
- **Database Idempotency:** SQL `ON CONFLICT (source_url) DO UPDATE` ensures concurrent workers cannot create duplicate canonical records.
- **PostgreSQL Table Partitioning:** For 500,000+ records, tables are partitioned by `collected_at` date ranges and indexed on `source_url`, `entity_name`, and `content_hash`.

---

## Physical Bottlenecks & Mathematical Verification

### 500,000 Record Throughput Math
- **Target Record Goal:** 500,000 canonical entities.
- **Target Execution Window:** 24 hours ($86,400$ seconds).
- **Required System Throughput:**
  $$\text{Required Throughput} = \frac{500,000 \text{ records}}{86,400 \text{ seconds}} \approx 5.79 \text{ records/second}$$

### LLM Token & Quota Calculation
- Average input context payload after HTML/DOM cleaning: ~1,500 tokens.
- Total token throughput for 500,000 extractions:
  $$\text{Total Tokens} = 500,000 \times 1,500 = 750,000,000 \text{ tokens/day} \approx 520,833 \text{ TPM}$$
- **Multi-Provider Capacity Provisioning:**
  - Gemini 1.5 Flash Quota: 300,000 TPM
  - Groq compound Quota: 250,000 TPM
  - DeepSeek Quota: 200,000 TPM
  - **Combined Capacity:** 750,000 TPM (144% headroom above required throughput).
