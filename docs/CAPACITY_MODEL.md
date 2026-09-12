# Capacity Model for GraphOne / FrontierAtlas Ingestion Pipeline

The following table presents engineering estimates for four target ingest volumes. **All numeric constants are labeled `ASSUMPTION`** and are **not** derived from measurements.

| Target (records/day) | Average records/sec | **ASSUMPTION** Burst multiplier | Burst records/sec | **ASSUMPTION** Crawler concurrency | Worker throughput (records/sec) | LLM extraction throughput (records/sec) | DB write throughput (records/sec) | Queue buffering (records) | **ASSUMPTION** Retry amplification (×) | Primary bottleneck |
|----------------------|---------------------|-------------------|------------------|-------------------------------|----------------------------------|------------------------------------------|-----------------------------------|---------------------------|------------------------------|-------------------|
| **1,000** | 1000 / 86 400 ≈ **0.012** | 5 | **0.06** | 5 (default `CRAWL_CONCURRENCY`) | 0.05 (each worker processes one record per second) | 0.04 (LLM latency ≈ 25 s per record) | 0.04 (PostgreSQL upsert ≈ 25 s) | 50 (small buffer) | 1.5 (average 1 retry) | **LLM latency** |
| **10,000** | 10 000 / 86 400 ≈ **0.116** | 5 | **0.58** | 10 (`CRAWL_CONCURRENCY=10`) | 0.5 (10 workers * 0.05) | 0.45 (parallel LLM calls) | 0.45 | 200 | 2 (some records need 2 retries) | **LLM concurrency** |
| **100,000** | 100 000 / 86 400 ≈ **1.16** | 5 | **5.8** | 20 (`CRAWL_CONCURRENCY=20`) | 5.0 (20 workers * 0.25) | 4.2 (batch LLM calls) | 4.2 | 1 000 | 3 (higher retry amplification) | **Worker CPU / I/O** |
| **500,000** | 500 000 / 86 400 ≈ **5.79** | 5 | **28.9** | 50 (`CRAWL_CONCURRENCY=50`) | 28.0 (50 workers * 0.56) | 24.0 (scaled LLM clusters) | 24.0 | 5 000 | 4 (multiple retries, back‑pressure) | **Queue back‑pressure** |

**Explanation of columns**
- **Average records/sec** – simple division of target daily records by 86 400 seconds.
- **Burst multiplier** – factor to handle traffic spikes; chosen as a conservative **5×** (`ASSUMPTION`).
- **Crawler concurrency** – number of async crawler tasks; increased to meet burst demand (`ASSUMPTION`).
- **Worker throughput** – records a worker can finish per second given network latency, parsing, and I/O (`ASSUMPTION`).
- **LLM extraction throughput** – limited by provider rate‑limit windows; we assume each LLM request takes ~25 s for a 1.5 k token payload (`ASSUMPTION`).
- **DB write throughput** – PostgreSQL upsert latency similar to LLM latency in our design (`ASSUMPTION`).
- **Queue buffering** – size of Kafka lag that can be safely absorbed before back‑pressure throttles crawlers (`ASSUMPTION`).
- **Retry amplification** – expected total work factor when retries (including 429/413 handling) occur (`ASSUMPTION`).
- **Primary bottleneck** – the component that most limits scale at the given target.

All numbers are illustrative; real deployments should replace each `ASSUMPTION` with measured values.
