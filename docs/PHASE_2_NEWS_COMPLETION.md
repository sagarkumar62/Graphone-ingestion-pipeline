# Phase 2 — AI News Completion & 24-Hour Freshness Report

## Executive Summary

This document details the audit, ingestion architecture, 24-hour freshness engine, full-text extraction strategy, anti-bot compliance, deduplication, quality audit, test suite, and six-tab export for the **AI News** component of the GraphOne / FrontierAtlas ingestion pipeline.

---

## 1. Scope

Work was strictly confined to the **AI News** requirement:
- Monitor 5 AI news sources.
- Collect news published strictly within the **LAST 24 HOURS** ($0.0 \le \text{age\_hours} \le 24.0$).
- Perform full-text article crawling and date normalization.
- Ensure 100% legitimate source provenance (0 synthetic/fabricated records).
- Zero anti-bot / CAPTCHA bypass.
- Export submission-ready fresh news records to `data/exports/news.csv`.

---

## 2. Source Verification Matrix

| Source | Access Method | Date Evidence | Full Text Availability | Fresh Articles Count | Status |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **HuggingFace Daily Papers** | JSON API (`/api/daily_papers`) | `submittedOnDailyAt` / `publishedAt` | Full article text via HTML parser (~6k–7.4k chars) | 5 | **LIVE_VERIFIED** |
| **TechCrunch AI** | RSS XML Feed | RSS `<pubDate>` / `<dc:date>` | Full article text via HTML parser (~3.3k–6.2k chars) | 4 | **LIVE_VERIFIED** |
| **MIT Technology Review AI** | RSS XML Feed | RSS `<pubDate>` / `<dc:date>` | Full article text via HTML parser (~6.4k–11k chars) | 0 | **LIVE_VERIFIED** *(Latest item 31.8h old; 0 fresh $\le$ 24h)* |
| **OpenAI Blog** | RSS XML Feed | RSS `<pubDate>` | Feed accessible; article link GET returns HTTP 403 (Cloudflare) | 0 | **PARTIALLY_LIVE_VERIFIED** *(Article GET blocked by Cloudflare 403)* |
| **Hacker News AI** | Firebase JSON API | Submission `time` (Unix timestamp) | Full article text for accessible links (~2.3k–31k chars) | 5 | **LIVE_VERIFIED** |

---

## 3. Access Methods & Compliance

All access is strictly compliant with standard web protocols:
- **API & RSS**: Public endpoints using standard HTTP `AsyncClient` requests with honest User-Agent headers.
- **No Evasion**: Respects anti-bot protections. OpenAI Blog article page GET requests returning Cloudflare 403 are recorded as blocked without proxy rotation, headful browser spoofing, or CAPTCHA solvers.

---

## 4. Publication Date Extraction & 24-Hour Freshness

- **Formula**: `age_hours = round((now_utc - published_dt_utc).total_seconds() / 3600.0, 2)`
- **Rule**:
  - `0.0 <= age_hours <= 24.0` $\rightarrow$ `PRODUCTION_FRESH` (Accepted)
  - `age_hours > 24.0` $\rightarrow$ `PRODUCTION_STALE` (Rejected)
  - Missing or unparseable date $\rightarrow$ `UNKNOWN_DATE` (Rejected)
- **Timezone Normalization**: All timestamps are converted to aware UTC datetimes before ISO 8601 formatting (`YYYY-MM-DDTHH:MM:SSZ`).
- **Relative Dates**: Supports relative dates ("2 hours ago", "yesterday", "just now") relative to crawl UTC time.
- **No Crawl Time Substitution**: Never uses crawl time as a substitute for missing publication dates.

---

## 5. Full-Text Crawling & AI Relevance

- **Full-Text Crawling**: For every discovered article URL, article pages are fetched and parsed via `html_extractor` prioritizing `<article>` semantic containers, main text blocks, and structured JSON-LD.
- **AI Relevance**: Reassures relevance via category boundaries (HuggingFace Daily Papers, TechCrunch AI, MIT Tech Review AI, OpenAI Blog) and regex word-boundary filtering (`r"\b(ai|llm|gpt|claude|anthropic|openai|deepseek|transformer|neural|machine learning)\b"`) for community feeds.

---

## 6. Deduplication & Provenance

- **Deterministic Fingerprinting**: Deduplication enforces canonical URL identity and content-hash tracking via SHA-256 staging.
- **Provenance**: Every record stored contains `source_name`, `source_url`, `title`, `summary`, `full_text`, `published_date` (ISO UTC format), and `collectedAt`.

---

## 7. Data Quality Audit

Summary of database rows in `pipeline.db` (`news` table):
- **Total News Rows**: 28
- **Production Fresh (<= 24h)**: 14
- **Production Stale (> 24h)**: 14
- **Unknown Date**: 0
- **Test / Legacy Fixtures**: 0
- **Fabricated / Synthetic Records**: 0 (0.0%)
- **Submission-Ready Fresh News Count**: 14

---

## 8. Test Results

Unit and integration tests in `tests/unit/test_news_freshness.py`:
- 24-hour freshness boundaries (1h, 23h59m, 24h exact, 24.1h stale)
- Missing and malformed dates
- Relative date parsing & timezone conversions
- Article HTML full-text vs RSS summary distinction
- Canonical URL deduplication
- HTTP error codes & missing provenance rejection
- **Regression Suite Result**: 112 passed, 1 skipped, 0 failed.

---

## 9. Six-Tab Exporter Status

Exporter script `scripts/export_sheets.py` updated:
- `data/exports/news.csv`: Exports ONLY `PRODUCTION_FRESH` articles published within the last 24 hours (14 records).
- Preserved all other completed tabs (`startups.csv`: 1,051, `products.csv`: 1,501, `research_papers.csv`: 1,009, `jobs.csv`: 683, `entity_mappings.csv`: 863).

---

## 10. Limitations

1. **OpenAI Blog Article Pages**: While OpenAI's RSS feed is accessible (15 items), fetching individual article pages returns HTTP 403 due to Cloudflare Turnstile protection. As per compliance guidelines, these are classified as partially verified without bypassing controls.
2. **MIT Technology Review Feed Cadence**: MIT Tech Review AI RSS feed updates on a multi-day cycle; all items on the feed at audit time were published > 24 hours ago (31.8h–177h old) and correctly classified as `PRODUCTION_STALE`.
