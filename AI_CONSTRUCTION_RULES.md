# AI Construction Rules

This document defines the strict, non-negotiable operational rules for building and maintaining the GraphOne / FrontierAtlas production-grade AI/Data Ingestion Pipeline. All engineers and AI subagents working on this codebase MUST adhere to these rules without exception.

---

## Core Engineering Directives

### 1. Zero Hallucination & Fact Integrity
- **Rule 1: Never fabricate data.** Under no circumstances should an LLM or heuristic step invent, guess, or extrapolate fields that do not exist in the source raw material.
- **Rule 2: Every record must have legitimate source provenance.** Every extracted item must maintain a verifiable lineage linking back to its original source URL (`source.url`) and source identifier (`source.name`).
- **Rule 11: LLMs are extractors, not sources of truth.** LLMs must strictly operate in structured extraction mode. If a field (such as `employeeCount` or `github_url`) cannot be unambiguously verified from raw page content, it must be returned as `null` or omitted per schema rules, never hallucinated.
- **Rule 12: Preserve raw source data wherever practical.** Raw HTTP/HTML/JSON payloads must be persisted to cold/raw storage prior to processing to enable full auditability, re-parsing, and forensic debugging.

### 2. Resilience, Timeouts & Rate Limiting
- **Rule 3: Never silently discard failures.** Every failure—whether network timeout, HTTP error, LLM parsing error, schema validation failure, or database error—must be explicitly logged, categorized, and emitted to retry queues or Dead-Letter Queues (DLQ).
- **Rule 4: All network operations must have timeouts.** Every HTTP request, Playwright navigation, queue fetch, database query, and LLM API call MUST be wrapped with explicit, configurable connection and read timeouts.
- **Rule 5: All retryable operations must have bounded retries.** No infinite loops. Retryable operations must be constrained by explicit maximum retry counts (e.g., max 3-5 attempts).
- **Rule 6: Use exponential backoff with jitter.** All retries across crawlers, LLM providers, and storage writers MUST implement truncated exponential backoff with randomized jitter (e.g., Full Jitter or Equal Jitter) to prevent thundering herd problems.

### 3. State Management & Idempotency
- **Rule 7: Processing must be idempotent.** Re-running the pipeline on the same source input or re-ingesting a payload multiple times must produce identical target state without duplicate canonical entries or corrupted metrics.
- **Rule 8: Duplicate messages must be safe.** In-flight network retries or message queue duplicate deliveries (`at-least-once` delivery semantics) must be handled gracefully via unique content hash keys, atomic lock acquisition, and upsert operations.

### 4. Data Validation & Quality Enforcement
- **Rule 9: Invalid LLM output must never enter canonical storage.** Raw LLM responses must undergo rigorous multi-stage JSON parsing and strict JSON Schema validation before being committed to persistent canonical storage.
- **Rule 10: Validate all LLM JSON against schemas.** Every extracted entity must validate cleanly against its target schema version (`schemas/*.schema.json`). Failed validation triggers retry with schema error context or DLQ route.
- **Rule 21: Do not make changes that break documented data contracts.** Modifications to schemas, API request formats, or queue message formats must strictly follow semantic versioning (`schemaVersion`) and preserve backwards compatibility.

### 5. Security & Secret Management
- **Rule 13: Never hardcode secrets.** API keys, database credentials, proxy user/passwords, and authorization tokens must never be checked into repository source code.
- **Rule 14: Use environment variables/secrets management.** All credentials and dynamic configuration parameters must be ingested at runtime via `.env` files, environment variables, or dedicated secret management stores.

### 6. Observability & System Transparency
- **Rule 15: Use structured logging.** All log entries must be emitted as formatted JSON with contextual metadata fields (e.g., `trace_id`, `record_type`, `source_url`, `worker_id`, `attempt_count`, `component`).
- **Rule 16: Add metrics for throughput, latency, failures, retries, and DLQ.** System components must expose counters, histograms, and gauges monitoring item ingestion rate, extraction duration, HTTP status distributions, LLM token counts, rate-limit hits, and DLQ accumulation.

### 7. Architectural Decoupling & Provider Abstraction
- **Rule 17: Do not create unnecessary infrastructure.** Keep the deployment footprint minimal, pragmatic, and simple. Avoid over-engineering unneeded microservices when decoupled asynchronous modules with standard queueing suffice.
- **Rule 18: Prefer interfaces and dependency injection for external providers.** Wrap external services (crawlers, LLM API clients, vector DBs) behind clean abstract interface classes to facilitate isolated unit testing and dynamic backend swapping.
- **Rule 19: No provider-specific logic should leak throughout the application.** Low-level details (such as Gemini-specific request parameters or Groq error formats) must be completely encapsulated within provider adapter layers.

### 8. Engineering Rigor & Governance
- **Rule 20: Architecture decisions must be documented.** Any structural design choice, protocol selection, or database choice must be recorded as an Architecture Decision Record (ADR) in `docs/ARCHITECTURE_DECISIONS.md`.
- **Rule 22: Address ambiguity with low-risk choices.** If requirements conflict or are ambiguous, document the ambiguity clearly, select the lowest-risk implementation strategy, and seek explicit clarification.
- **Rule 23: Keep components independently testable.** Crawlers, extractors, validators, resolvers, and queue consumers must be unit-testable in isolation using mocks or synthetic fixtures without external dependencies.
- **Rule 24: Do not claim scalability without identifying bottlenecks.** Every performance or scale statement must identify explicit physical bottlenecks (e.g., network bandwidth, LLM provider RPM/TPM, DB connection limits, disk IOPS).
- **Rule 25: Do not claim anti-bot capabilities that are not actually implemented.** Document real, working, compliant anti-bot and crawler strategies; do not use speculative claims or illegal bypass claims.
- **Rule 26: Keep demo implementation realistic for a 3-day engineering assessment.** Focus effort on clean abstractions, robust edge-case handling, full test coverage for core paths, and clean runnable demo code.
