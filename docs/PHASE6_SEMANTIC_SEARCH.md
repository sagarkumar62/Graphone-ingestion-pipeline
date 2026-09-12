# PHASE 6 SEMANTIC SEARCH PREPARATION

**Date:** September 11, 2026  
**Pipeline Codebase:** `graphone-ingestion-pipeline`  
**Status:** **READY FOR VECTOR DB INTEGRATION**

---

## 1. Executive Summary

Phase 6 introduces a clean, provider-agnostic vector embedding abstraction layer (`BaseEmbeddingProvider` in `src/embedding/base.py`). This architecture allows the pipeline to prepare paper titles and abstracts for vector index storage (e.g. pgvector, Qdrant, Chroma) without coupling ingestion to third-party paid cloud LLM APIs or fabricating fake production vectors.

---

## 2. Abstraction Design

```python
class BaseEmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: pass

    @property
    @abstractmethod
    def dimension(self) -> int: pass

    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResult: pass
```

---

## 3. Implementations

1. **`DeterministicLocalEmbeddingProvider` (`src/embedding/provider.py`):**
   - Seed-based SHA-256 digest generator producing 1,536-dimensional L2-unit-normalized vectors.
   - Ideal for offline unit testing, CI/CD pipelines, and local benchmarking without network API keys.
2. **Production Cloud Provider (Target Interface):**
   - Supports plug-and-play replacement with OpenAI (`text-embedding-3-small`), Cohere, or local HuggingFace sentence-transformers.

---

## 4. Source Text & Embedding Strategy

- **Source Text:** `title + "\n" + abstract`
- **Regeneration Policy:** Re-compute embedding vectors only when `content_hash` changes.
- **Storage Policy:** Store embedding metadata (`model_name`, `dimension`, `text_hash`) alongside vectors in vector database collections.
