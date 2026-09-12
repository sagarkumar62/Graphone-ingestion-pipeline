# System Requirements Specification: GraphOne / FrontierAtlas Ingestion Pipeline

## Executive Summary
This document specifies the functional, non-functional, and operational requirements for the GraphOne / FrontierAtlas production-grade AI/Data Ingestion Pipeline. The pipeline automates the continuous extraction, normalization, enrichment, entity resolution, and schema validation of multi-vertical entity data (startups, products, research papers, AI job postings, and AI news signals).

---

## 1. Functional Requirements

### 1.1 Vertical Data Acquisition (Phase I & II)
- **FR-1.1.1 (Startup Acquisition):** Extract a minimum of 1,000 unique startup records from public directories (e.g., Y Combinator Directory, Product Hunt, Crunchbase public pages) containing entity name, employee count, website, description, and founding info.
- **FR-1.1.2 (Product Acquisition):** Extract a minimum of 1,000 unique AI product records detailing product name, parent startup/company, pricing model (`FREE`, `FREEMIUM`, `PAID`, `ENTERPRISE`, `UNKNOWN`), and product description.
- **FR-1.1.3 (Research Paper Acquisition & GitHub Correlation):** Extract a minimum of 1,000 unique AI research papers from Arxiv and Papers With Code.
  - Automatically parse associated GitHub repository URLs where available.
  - Query current GitHub repository star counts dynamically via GitHub REST/GraphQL API or web extraction.
- **FR-1.1.4 (24-Hour Freshness Signal Monitoring):** Monitor 5 distinct AI news sources (e.g., TechCrunch AI, VentureBeat AI, MIT Tech Review AI, Hacker News AI, Arxiv Daily AI) and 5 distinct AI job boards (e.g., RemoteOK AI, Wellfound AI Jobs, YC WorkAtAStartup AI, Greenhouse/Lever AI aggregators).
  - Strictly filter and ingest ONLY articles and job postings published within the previous 24 hours of execution.
  - Extract full text content, metadata, and normalized ISO-8601 publication timestamps.

### 1.2 Multi-Tier LLM Extraction Engine (Phase III)
- **FR-1.2.1 (Schema Transformation):** Convert raw un-structured or semi-structured HTML/text content into canonical JSON matching predefined schemas (`schemas/*.schema.json`).
- **FR-1.2.2 (Provider Fallback Chain):** Implement an automated provider fallback mechanism with the priority sequence:
  1. **Primary:** Gemini 2.5 Flash (high speed, cost-effective context window)
  2. **Secondary:** Groq compound (ultra-low latency fallback)
  3. **Tertiary:** DeepSeek V3 (high reasoning extraction fallback)
  4. **Dead-Letter Queue:** Route to DLQ after exhausting tier retries.
- **FR-1.2.3 (Rate Limit & Payload Overload Management):**
  - Intercept HTTP 429 (Too Many Requests) errors and trigger truncated exponential backoff with full jitter.
  - Intercept HTTP 413 / Context Window Exceeded errors and invoke dynamic token-aware payload chunking/truncation while preserving core semantic text blocks.

### 1.3 Deterministic Entity Resolution Engine (Phase IV)
- **FR-1.3.1 (Normalization Pipeline):** Pipeline raw company/product strings through deterministic transformations (Unicode NFKC, lowercase, punctuation removal, legal entity suffix stripping e.g. "Inc", "LLC", "Corp", whitespace collapse).
- **FR-1.3.2 (Canonical Seed Mapping):** Match normalized string candidates against a seeded dictionary of canonical AI entities (e.g. mapping `"OpenAI"`, `"Open AI"`, `"OpenAI, Inc."` -> `"OpenAI"`).
- **FR-1.3.3 (Auditable Logging):** Emit a structured mapping record for every resolved entity capturing raw value, normalized value, canonical value, match method, confidence score, source URL, and timestamp.

### 1.4 Anti-Bot & Adaptive Scraping (Phase V)
- **FR-1.4.1 (Asynchronous Architecture):** Execute all network requests asynchronously using non-blocking event loops (`asyncio`, `aiohttp`, `Playwright Async`).
- **FR-1.4.2 (Anti-Protection Resilience):** Support dynamic rendering for JavaScript-heavy single-page applications (SPAs) and compliant anti-bot handling for high-protection domains.

---

## 2. Non-Functional Engineering Requirements

- **NFR-2.1 (Scalability to 500,000+ Records):** The system architecture must decouple crawler producers, message queue brokers, worker consumers, LLM extractors, and database writers so that scaling from 1k to 500k+ records requires zero code modifications—only adding queue partitions and worker container replicas.
- **NFR-2.2 (Fault Isolation & Decoupling):**
  - A crawler failure must NOT crash the LLM extraction queue.
  - An LLM provider outage must NOT stop crawlers from filling the raw queue.
  - Database downtime must NOT cause raw message loss (buffered in persistent queue).
- **NFR-2.3 (Idempotency & Anti-Duplication):** Distributed workers processing identical items concurrently must avoid duplicate processing using URL SHA256 fingerprints, content SimHash signatures, and atomic database upserts (`ON CONFLICT DO UPDATE`).
- **NFR-2.4 (Provenance & Zero Hallucination):** Every record must retain its original source URL and source identifier. LLMs must be strictly constrained to extract factual content; missing fields must be stored as `null`, never invented.
- **NFR-2.5 (Observability & Logging):** Formatted structured JSON logging must be emitted across all services, tagging records with `trace_id`, `record_type`, `attempt`, and performance metrics.

---

## 3. Deliverables & Evaluation Criteria Mapping

| Assessment Category | Weight | Specific System Deliverables | Evaluation Verification |
| :--- | :--- | :--- | :--- |
| **LLM Orchestration** | 25% | 3-tier fallback chain (Gemini Flash → Groq compound → DeepSeek), 413 truncation, 429 jitter backoff | Unit tests for fallbacks, schema-validated JSON outputs |
| **Data Quality** | 25% | ISO-8601 date parsing, 24-hr freshness filters, GitHub star fetching | 1000+ Startups, 1000+ Products, 1000+ Papers CSV/Sheets |
| **Scale Thinking** | 20% | Decoupled queue architecture, partitioning design, horizontal worker scaling specs | `SCALABILITY.md` throughput math, concurrency design |
| **Engineering Rigor** | 20% | `asyncio` engine, structural logging, retry bounds, fault tolerance boundaries | `AI_CONSTRUCTION_RULES.md` compliance, clean code |
| **Entity Resolution** | 10% | Multi-stage normalization pipeline, seed dictionary matching, auditable log output | Entity Mapping CSV tab & audit schema validation |

---

## 4. Key Assumptions & System Risks

### Assumptions
1. External AI news and job sources provide public HTML/JSON endpoints accessible via standard HTTP or headless browsers with appropriate headers and rate limits.
2. API rate limit ceilings for primary LLM providers (e.g. Gemini 15 RPM/1M TPM on free tier, or pay-as-you-go quotas) require backpressure queue throttling to operate reliably under concurrent loads.
3. Seed entity mapping rules cover major AI ecosystem players while novel names dynamically register as new canonical entities.

### Technical Risks & Mitigations
- **Risk 1: Cloudflare/Datadome dynamic blocking on target news/job boards.**
  - *Mitigation:* Implement Playwright browser context rotation, stealth plugins, fallback RSS/feed parsing, and official public API endpoints.
- **Risk 2: LLM rate-limit cascades across multiple providers during peak batch scrapes.**
  - *Mitigation:* Redis dynamic token-bucket rate limiters per provider, backoff queues, and tertiary provider routing.
- **Risk 3: Date ambiguity on legacy or unstructured blogs (e.g. "Posted Tuesday").**
  - *Mitigation:* Fallback to HTTP `Last-Modified` headers, URL regex date patterns, and page microdata/JSON-LD metadata extractors.
