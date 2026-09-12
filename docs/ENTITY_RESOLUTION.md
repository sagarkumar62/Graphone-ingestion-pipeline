# Deterministic Entity Resolution Architecture

## System Overview
Entity Resolution resolves messy, inconsistent raw organization and product names extracted from web pages into canonical entities.

**Example Mapping:**
- `"OpenAI"` $\rightarrow$ `OpenAI`
- `"Open AI"` $\rightarrow$ `OpenAI`
- `"OpenAI, Inc."` $\rightarrow$ `OpenAI`
- `"OpenAI Inc"` $\rightarrow$ `OpenAI`
- `"OPENAI LLC"` $\rightarrow$ `OpenAI`

---

## E2E Resolution Pipeline

```mermaid
flowchart TD
    Raw[Raw Entity String\ne.g., ' OpenAI, Inc. '] --> S1[1. Unicode Normalization\nNFKC Form]
    S1 --> S2[2. Case Normalization\nLowercase]
    S2 --> S3[3. Punctuation Removal\nStrip commas, dots, hyphens]
    S3 --> S4[4. Legal Suffix Normalization\nStrip Inc, LLC, Corp, Ltd, Co]
    S4 --> S5[5. Whitespace Normalization\nTrim & collapse internal spaces]
    
    S5 --> Direct[Normalized String\ne.g., 'openai']
    
    Direct --> M1{6. Seed Alias Lookup}
    M1 -->|Hit| C1[Canonical Entity: OpenAI\nMethod: ALIAS_LOOKUP, Confidence: 1.0]
    
    M1 -->|Miss| M2{7. Canonical Seed Exact Match}
    M2 -->|Hit| C2[Canonical Entity: OpenAI\nMethod: SEED_EXACT, Confidence: 1.0]
    
    M2 -->|Miss| M3{8. Controlled Fuzzy Match\nJaro-Winkler >= 0.92}
    M3 -->|Hit| C3[Canonical Entity: Candidate\nMethod: FUZZY_JARO_WINKLER, Confidence: 0.95]
    
    M3 -->|Miss| M4[9. Register New Canonical Seed]
    M4 --> C4[Canonical Entity: TitleCase(Normalized)\nMethod: NEW_CANONICAL_SEED, Confidence: 0.80]

    C1 & C2 & C3 & C4 --> AuditLog[Write Entity Mapping Log Record\nschemas/entity-mapping.schema.json]
```

---

## Stage-by-Stage Transformation Matrix

| Stage | Operation | Input Example | Output Example | Technical Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Unicode Normalization** | `"O𝑝enAI"` | `"OpenAI"` | `unicodedata.normalize('NFKC', text)` |
| **2** | **Case Normalization** | `"OpenAI"` | `"openai"` | `text.lower()` |
| **3** | **Punctuation Stripping**| `"open-ai, inc."` | `"open ai inc"` | `re.sub(r'[^\w\s]', ' ', text)` |
| **4** | **Legal Suffix Strip** | `"openai inc"` | `"openai"` | Regex match legal term list (`inc`, `llc`, `corp`, `ltd`, `gmbh`, `co`, `solutions`, `technologies`, `labs`, `ai`) |
| **5** | **Whitespace Collapse** | `" open  ai "` | `"openai"` | `' '.join(text.split())` |
| **6** | **Alias Match** | `"the open ai corp"`| `"OpenAI"` | Hash map lookup against alias dictionary |
| **7** | **Exact Canonical Match**| `"openai"` | `"OpenAI"` | Direct key match in canonical seed set |
| **8** | **Fuzzy Metric Match** | `"openaii"` | `"OpenAI"` | Jaro-Winkler similarity algorithm ($S_{\text{JW}} \ge 0.92$) |

---

## Controlled Fuzzy Matching Mathematics

When exact seed and alias lookups miss, controlled metric fuzzy matching computes similarity against candidate seed entities using **Jaro-Winkler Distance**:

$$d_j = \frac{1}{3} \left( \frac{m}{|s_1|} + \frac{m}{|s_2|} + \frac{m - t}{m} \right)$$

$$d_w = d_j + \ell p (1 - d_j)$$

- **Threshold Constraint:** Similarity $d_w \ge 0.92$ required for automated match.
- **Prefix Scale ($p$):** $0.1$
- **Max Prefix Length ($\ell$):** $4$ characters.
- **Safety Boundary:** Matches below $0.92$ threshold do NOT merge entities—they automatically register as a new candidate canonical entity to prevent false positive entity merging.

---

## Auditable Mapping Log Schema & Persistence

Every resolution operation produces a permanent audit record stored in `entity_mapping_log` and exported to Google Sheets:

```json
{
  "schemaVersion": "1.0",
  "recordType": "ENTITY_MAPPING",
  "mappingId": "map_98234ab-1234-5678-90ab-cdef12345678",
  "entityType": "STARTUP",
  "rawValue": "Open AI, Inc.",
  "normalizedValue": "openai",
  "canonicalValue": "OpenAI",
  "matchMethod": "ALIAS_LOOKUP",
  "confidence": 1.00,
  "timestamp": "2026-09-10T14:00:00Z",
  "sourceUrl": "https://news.ycombinator.com/item?id=100",
  "resolverVersion": "1.0.0"
}
```
