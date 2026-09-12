# PHASE 6 CONTENT HASHING POLICY

**Date:** September 11, 2026  
**Pipeline Codebase:** `graphone-ingestion-pipeline`  
**Status:** **ACTIVE**

---

## 1. Overview & Objectives

In Phase 6, deterministic content hashing is implemented to detect whether a research paper's underlying facts have changed across ingestion runs.

### Key Policy Rule
> **"Timestamps (`collected_at`) must NEVER contribute to content identity. Only actual source domain facts determine record state changes."**

---

## 2. Hash Specification

The function `compute_research_paper_hash` in `src/utils/hashing.py` generates a standard 64-character hex SHA-256 string from a JSON payload consisting of normalized fields:

```python
payload = {
    "arxiv_id": extract_arxiv_id(source_url) or source_url,
    "title": normalize_title(title),
    "authors": sorted(normalize_authors_list(authors)),
    "abstract": normalize_whitespace(abstract),
    "date": normalize_iso_date(published_date),
    "category": normalize_whitespace(primary_category).lower()
}
```

---

## 3. Normalization Invariants

1. **Title Equivalence:** `"Attention Is All You Need."` and `"attention is all you need"` produce the identical hash.
2. **Author Permutations:** Author order variations from source parsing are eliminated by sorting the normalized author names alphabetically prior to hashing.
3. **URL Version Stability:** `https://arxiv.org/abs/2301.12345v1` and `https://arxiv.org/abs/2301.12345v2` extract the base arXiv ID `2301.12345`, ensuring version tags do not distort entity identity.
4. **Abstract Whitespace:** Newline, tab, and multi-space formatting differences in arXiv abstract HTML/XML are collapsed to single spaces.

---

## 4. Verification & Testing

Unit test coverage in `tests/unit/test_content_hashing.py` verifies that:
- Equivalent records produce identical SHA-256 hashes.
- Modifications to title, authors, abstract, or publication date change the hash.
- Author order shuffling does not alter the hash.
