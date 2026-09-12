# Fault Tolerance & Edge Case Recovery Matrix

## System Resilience Philosophy
The pipeline is engineered under the assumption that external web sources, LLM providers, network connections, and infrastructure nodes **will fail continuously**. The architecture guarantees **zero data loss**, **fault isolation**, **bounded retries**, and **idempotent state recovery**.

---

## Exhaustive Failure Mode Recovery Matrix

| Failure Category | Failure Scenario | Trigger Condition / Status Code | System Detection Mechanism | Immediate Recovery Behavior | Max Retries | Ultimate Escalation / DLQ Route |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Crawler** | Source Timeout | `asyncio.TimeoutError` (> 15s) | Connection client timer | Retry request with backoff & jitter | 3 Attempts | Log warning, re-queue with lower priority |
| **Crawler** | HTTP 403 Forbidden | HTTP Status `403` | Response status check | Rotate HTTP headers / UA / Proxy IP | 3 Attempts | Route to anti-bot dynamic browser queue |
| **Crawler** | Cloudflare / Captcha | HTTP 403 / Captcha HTML | Body keyword inspection | Switch from HTTP client to Playwright Async | 2 Attempts | Log source blocking; route to `dlq:crawler_blocked` |
| **Crawler** | Malformed HTML | `bs4` / `lxml` parser failure | Parser exception catch | Fallback to raw regex text extraction | 1 Attempt | Route to `dlq:malformed_html` |
| **Freshness**| Missing Pub Date | Metadata missing/unparseable | Date normalization failure | Apply URL regex date & HTTP `Last-Modified` | N/A | Heuristic freshness filter or drop if stale |
| **LLM Engine**| HTTP 429 Rate Limit | HTTP Status `429` | API Client response status | Switch immediately to Secondary LLM Provider | 5 (Tiered) | Exhaust tier chain -> Route to `dlq:llm_rate_limit` |
| **LLM Engine**| HTTP 413 / Context Overflow | HTTP Status `413` or context error | Payload size / API exception | Dynamic payload chunking & truncation | 3 Attempts | Route to `dlq:payload_too_large` |
| **LLM Engine**| LLM API Timeout | `TimeoutError` (> 30s) | Provider client socket timer | Retry primary -> Fallback to Groq / DeepSeek | 3 Attempts | Fallback provider chain -> DLQ |
| **LLM Engine**| Malformed JSON Response| JSON decode error / markdown tags| Pydantic / `json.loads` catch | Extract raw JSON substring via regex | 2 Attempts | Re-prompt LLM with schema hint -> DLQ |
| **Validation**| Schema Validation Fail | `jsonschema.ValidationError` | Schema validation wrapper | Re-prompt LLM attaching specific schema error | 2 Attempts | Route to `dlq:schema_validation` |
| **Storage** | Database Outage | `asyncpg.PostgresError` / DB down | Storage wrapper exception | Buffer in Redis queue; pause worker batch commit | Infinite (Wait)| Worker re-claims message when DB restores |
| **Execution**| Worker Node Crash | Container SIGKILL / OOM | Redis visibility timeout expiry | Redis broker re-delivers message to active worker | Auto | Idempotent upsert prevents double write |
| **Messaging**| Duplicate Message | Duplicate queue message delivery | Redis URL / Content hash check | Ignore duplicate payload, ACK message | 0 Retries | Dropped as harmless duplicate |

---

## Retry Mathematics & Backoff Configuration

All retryable network and LLM operations implement **Full Jitter Exponential Backoff**:

$$T_{\text{wait}} = \text{random\_between}\left(0, \min\left(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}\right)\right)$$

### Default Parameter Configuration
- **Base Backoff ($T_{\text{base}}$):** $1.5$ seconds
- **Max Backoff ($T_{\text{max}}$):** $60.0$ seconds
- **Max Retry Attempts:** $5$ attempts
- **Jitter Factor:** Uniform random variation $[0.5, 1.5]$

---

## Dead-Letter Queue (DLQ) Architecture

Messages that exhaust maximum retry attempts or encounter fatal unrecoverable errors are routed to the Dead-Letter Queue.

### DLQ Message Metadata Schema
```json
{
  "dlq_id": "dlq_984f1a2b-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "original_payload": { ... },
  "error_category": "SCHEMA_VALIDATION_FAILURE",
  "error_message": "'published_date' is a required property",
  "failed_component": "JSONSchemaValidator",
  "attempt_history": [
    {"attempt": 1, "provider": "GeminiFlash", "timestamp": "2026-09-10T14:00:10Z", "error": "Invalid schema"},
    {"attempt": 2, "provider": "GroqLlama", "timestamp": "2026-09-10T14:00:14Z", "error": "Invalid schema"}
  ],
  "enqueued_at": "2026-09-10T14:00:15Z"
}
```

### Idempotency & Failure Recovery Guarantees
1. **At-Least-Once Processing Safety:** Database operations use SQL `ON CONFLICT (source_url) DO UPDATE` or `ON CONFLICT (entity_name, record_type) DO NOTHING`, ensuring duplicate deliveries produce zero side effects.
2. **Crash Recovery:** State is strictly held in persistent stores (Redis/PostgreSQL/Disk). Worker crashes lose zero raw data.
