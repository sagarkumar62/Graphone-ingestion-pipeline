# PHASE 6 ENRICHMENT ARCHITECTURE & STATE MACHINE

**Date:** September 11, 2026  
**Pipeline Codebase:** `graphone-ingestion-pipeline`  
**Status:** **ACTIVE**

---

## 1. Overview & Principles

The Phase 6 enrichment system enhances research paper records with live repository metrics (GitHub star counts) while maintaining zero hallucination, rate limit compliance, idempotency, and crash/resume state tracking.

---

## 2. Enrichment State Machine

Every record in `research_papers` tracks its enrichment state in the `enrichment_status` column:

```
                  +-------------------+
                  |   NOT_REQUESTED   |
                  +---------+---------+
                            |
                            v
                    +---------------+
                    |    PENDING    |
                    +-------+-------+
                            |
             +--------------+--------------+
             |                             |
     (No GH URL found)              (GH URL exists)
             |                             |
             v                             v
       +-----------+               +---------------+
       |  NO_DATA  |               |  IN_PROGRESS  |
       +-----------+               +-------+-------+
                                           |
                +--------------------------+--------------------------+
                |                          |                          |
          (HTTP 200 OK)              (HTTP 404/Syntax)        (HTTP 403/5xx/Timeout)
                |                          |                          |
                v                          v                          v
          +-----------+          +-------------------+      +-------------------+
          | COMPLETED |          | PERMANENT_FAILURE |      | RETRYABLE_FAILURE |
          +-----------+          +-------------------+      +---------+---------+
                                                                      |
                                                                (Incremental Retry)
                                                                      |
                                                                      v
                                                            +-------------------+
                                                            |    IN_PROGRESS    |
                                                            +-------------------+
```

### State Definitions
- `NOT_REQUESTED`: Record ingested before Phase 6; eligible for initial enrichment scan.
- `PENDING`: Enqueued for GitHub API enrichment.
- `IN_PROGRESS`: Currently being queried against `api.github.com`.
- `COMPLETED`: Authentic repository discovered, stars fetched, and stored.
- `NO_DATA`: Abstract/metadata verified; zero GitHub repository URLs referenced. `github_url` and `github_stars` remain `NULL`.
- `RETRYABLE_FAILURE`: Rate limit (403), transient network error, or GitHub API server issue (5xx). Eligible for backoff retry.
- `PERMANENT_FAILURE`: Repository deleted, private, or 404 Not Found. Will not be retried automatically.

---

## 3. Rate Limit & Anti-Hallucination Guarantees

1. **Anti-Hallucination:** Missing GitHub repository URLs are preserved as `NULL` in the database. Repositories are NEVER inferred from paper titles or author names.
2. **API Rate Limiting:** The enricher respects unauthenticated (60 req/hr) or token-authenticated (5,000 req/hr) GitHub API rate limits.
3. **Idempotency:** Re-running enrichment on `COMPLETED` or `NO_DATA` records is skipped unless forced, preventing redundant API calls and duplicate database writes.
