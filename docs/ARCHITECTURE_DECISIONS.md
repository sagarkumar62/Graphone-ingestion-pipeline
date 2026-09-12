# Architecture Decision Records (ADRs)

This document records the key architectural and design decisions for the GraphOne / FrontierAtlas Ingestion Pipeline.

---

## Index of ADRs
- [ADR-001: Async Messaging & Queue Selection](#adr-001-async-messaging--queue-selection)
- [ADR-002: Primary Storage & Database Selection](#adr-002-primary-storage--database-selection)
- [ADR-003: Raw Payload Storage Selection](#adr-003-raw-payload-storage-selection)
- [ADR-004: Crawler & Web Extraction Framework](#adr-004-crawler--web-extraction-framework)
- [ADR-005: Multi-Tier LLM Abstraction & Fallback Chain](#adr-005-multi-tier-llm-abstraction--fallback-chain)
- [ADR-006: Deterministic Multi-Stage Entity Resolution Engine](#adr-006-deterministic-multi-stage-entity-resolution-engine)
- [ADR-007: Python Asyncio Concurrency Model](#adr-007-python-asyncio-concurrency-model)
- [ADR-008: Containerized Modular Deployment Strategy](#adr-008-containerized-modular-deployment-strategy)

---

### ADR-001: Async Messaging & Queue Selection
- **Status:** Approved
- **Decision:** Use **Kafka** as the primary task queue broker for the pipeline.
- **Alternatives Considered:** RabbitMQ, Redis, AWS SQS.
- **Rationale:** Kafka provides high‑throughput partitioned logs, durable storage, configurable retention, consumer‑group parallelism, and built‑in replay capabilities required for large‑scale ingestion.
- **Tradeoffs:** Operates as a distributed service requiring a cluster; operational complexity is higher than a simple in‑memory broker.
- **Consequences:** Workers consume from Kafka topics with explicit offsets and dead‑letter handling.


---

### ADR-002: Primary Storage & Database Selection
- **Status:** Approved
- **Decision:** Use **PostgreSQL (with SQLite local fallback)** as the canonical relational entity store.
- **Alternatives Considered:** MongoDB (Document Store), DynamoDB, Cassandra.
- **Rationale:** Relational SQL engines provide strict schema enforcement, ACID guarantees, native JSONB support, and powerful upsert semantics (`ON CONFLICT (source_url) DO UPDATE`) essential for idempotency.
- **Tradeoffs:** Schema migrations require explicit DDL updates compared to schemaless document stores.
- **Consequences:** Entity tables enforce strict data types, foreign keys, and unique indexes on canonical source URLs.

---

### ADR-003: Raw Payload Storage Selection
- **Status:** Approved
- **Decision:** Use **Local Directory Storage (Partitioned by Date/Vertical)** for demo, with direct abstraction for **AWS S3 / MinIO Object Storage** in production.
- **Alternatives Considered:** Storing raw HTML directly in PostgreSQL `TEXT` columns.
- **Rationale:** Storing large HTML payloads in relational databases bloats DB size and degrades index performance. Blob storage keeps raw payloads isolated and cost-effective.
- **Tradeoffs:** Requires maintaining a URI pointer (`raw_payload_uri`) in queue messages.
- **Consequences:** Enables full auditability and offline re-parsing without hitting external websites again.

---

### ADR-004: Crawler & Web Extraction Framework
- **Status:** Approved
- **Decision:** Implement a dual-engine crawler using **`aiohttp` / `httpx`** for fast static HTML/feed parsing and **`Playwright Async`** for JavaScript SPAs.
- **Alternatives Considered:** Scrapy, Selenium, Requests.
- **Rationale:** Scrapy lacks native support for modern async Playwright headless browser contexts within standard Python `asyncio` event loops. A custom async adapter pattern allows choosing the lightest engine required for each site.
- **Tradeoffs:** Playwright headless browsers consume higher memory per worker node (~150MB RAM per context).
- **Consequences:** Static sites execute at 50+ req/sec while JS-rendered SPAs render reliably without missing content.

---

### ADR-005: Multi-Tier LLM Abstraction & Fallback Chain
- **Status:** Approved
- **Decision:** Implement an abstract provider interface managing a 3-tier fallback sequence: **Gemini 2.5 Flash → Groq compound → DeepSeek V3**.
- **Note:** DeepSeek V3 is **NOT LIVE VERIFIED**.
- **Alternatives Considered:** Direct hardcoded SDK calls, single-provider dependency, OpenAI GPT-4o only.
- **Rationale:** Prevents single‑vendor lock‑in and protects against provider outage, HTTP 429 rate limits, and regional API downtime. Gemini 2.5 Flash provides massive context at low cost, Groq compound offers sub‑second latency, and DeepSeek provides reasoning fallback.
- **Tradeoffs:** Requires schema translation logic across provider SDKs.
- **Consequences:** Zero single point of failure in LLM extraction.

---

### ADR-006: Deterministic Multi-Stage Entity Resolution Engine
- **Status:** Approved
- **Decision:** Implement a **deterministic pipeline** (Unicode NFKC $\rightarrow$ Lowercase $\rightarrow$ Punctuation $\rightarrow$ Legal Suffix $\rightarrow$ Seed Dictionary $\rightarrow$ Jaro-Winkler Fuzzy Matching). Do NOT use uncontrolled LLMs as primary resolvers.
- **Alternatives Considered:** LLM-based entity clustering (e.g. asking GPT to cluster company names).
- **Rationale:** LLM entity matching is non-deterministic, expensive, hallucination-prone, and slow. Deterministic pipelines guarantee 100% reproducible canonical mappings and produce auditable mapping logs.
- **Tradeoffs:** Requires maintaining legal suffix dictionaries and canonical seed alias maps.
- **Consequences:** Messy names (`Open AI`, `OpenAI, Inc.`) resolve cleanly to `OpenAI` with 1.0 confidence.

---

### ADR-007: Python Asyncio Concurrency Model
- **Status:** Approved
- **Decision:** Adopt **Python 3.11+ `asyncio`** single-threaded event loops per worker process, scaled across multi-core CPU architectures using process worker pools.
- **Alternatives Considered:** Multi-threading with `threading`, synchronous `gevent` monkey-patching.
- **Rationale:** Web ingestion is heavily I/O bound (waiting on network sockets and API responses). Asyncio handles tens of thousands of open connections with minimal CPU overhead.
- **Tradeoffs:** CPU-bound tasks (e.g. SimHash calculation) must be offloaded to process pools or executed in non-blocking chunks.
- **Consequences:** High throughput concurrency with minimal memory footprint.

---

### ADR-008: Containerized Modular Deployment Strategy
- **Status:** Approved
- **Decision:** Package the pipeline into decoupled **Docker containers** orchestrated via `docker-compose` (demo) and Kubernetes HPA (production).
- **Alternatives Considered:** Monolithic single-script deployment, serverless AWS Lambda functions.
- **Rationale:** Lambda functions suffer from 15-minute execution limits and Playwright browser bundle size limits. Containerization ensures exact environment replication across local test and cloud production environments.
- **Tradeoffs:** Requires maintaining Dockerfiles and container image builds.
- **Consequences:** Seamless horizontal scaling of worker containers based on queue depth metrics.
