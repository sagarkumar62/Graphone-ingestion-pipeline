import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.llm.providers.base import BaseLLMProvider, LLMResponse
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.groq import GroqProvider
from src.llm.providers.deepseek import DeepSeekProvider
from src.llm.orchestrator import LLMOrchestrator
from src.llm.chunker import IntelligentPayloadChunker
from src.llm.retry import retry_with_backoff
from src.core.models import RecordType, CanonicalEntity, RawPayload
from src.core.exceptions import (
    LLMException, RateLimitException, ContextWindowExceededException,
    LLMAuthException, LLMBadRequestException, LLMTimeoutException,
    LLMServerException, MalformedResponseException, SchemaValidationException
)

class MockSuccessProvider(BaseLLMProvider):
    def __init__(self, name: str = "MockPrimary", model: str = "mock-model-v1", return_dict: dict | None = None):
        super().__init__(provider_name=name, model_name=model, api_key="dummy_key")
        self.return_dict = return_dict or {
            "schemaVersion": "1.0",
            "recordType": "STARTUP",
            "source": {"name": "MockSource", "url": "https://example.com/startup"},
            "content": {
                "entityName": "Acme AI",
                "data": {"employeeCount": 50, "fundingTotalUsd": 1000000.0}
            },
            "collectedAt": "2026-09-10T12:00:00Z"
        }
        self.extract_call_count = 0

    async def extract_structured(self, prompt_text: str, target_schema: dict, system_instruction: str, timeout_seconds: float = 30.0) -> LLMResponse:
        self.extract_call_count += 1
        return LLMResponse(
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response="{}",
            extracted_json=self.return_dict,
            tokens_used=100,
            execution_time_seconds=0.1
        )

class MockFailingProvider(BaseLLMProvider):
    def __init__(self, name: str, exception_to_raise: Exception):
        super().__init__(provider_name=name, model_name="failing-model", api_key="dummy_key")
        self.exception_to_raise = exception_to_raise
        self.extract_call_count = 0

    async def extract_structured(self, prompt_text: str, target_schema: dict, system_instruction: str, timeout_seconds: float = 30.0) -> LLMResponse:
        self.extract_call_count += 1
        raise self.exception_to_raise

# Requirement 1: Provider abstraction interface
def test_provider_abstraction_interface():
    provider = MockSuccessProvider("TestProvider", "test-model-1")
    assert provider.provider_name == "TestProvider"
    assert provider.model_name == "test-model-1"
    assert provider.supports_structured_output is True
    assert provider.estimate_tokens("Hello World") == 2

# Requirement 2: Primary provider success
@pytest.mark.asyncio
async def test_primary_provider_success():
    primary = MockSuccessProvider("GeminiFlash")
    orchestrator = LLMOrchestrator(providers=[primary])
    entity, used = await orchestrator.extract_canonical_entity(
        raw_text="Acme AI has 50 employees and $1M funding.",
        record_type=RecordType.STARTUP,
        source_name="MockSource",
        source_url="https://example.com/acme"
    )
    assert used == "GeminiFlash"
    assert entity.content["entityName"] == "Acme AI"
    assert entity.source.url == "https://example.com/acme"

# Requirement 3: Secondary Groq fallback
@pytest.mark.asyncio
async def test_secondary_groq_fallback():
    primary = MockFailingProvider("GeminiFlash", RateLimitException("429 Rate limit", "GeminiFlash", retry_after=0.01))
    secondary = MockSuccessProvider("GroqLlama")
    orchestrator = LLMOrchestrator(providers=[primary, secondary])
    
    entity, used = await orchestrator.extract_canonical_entity(
        raw_text="Acme AI has 50 employees.",
        record_type=RecordType.STARTUP,
        source_name="MockSource",
        source_url="https://example.com/acme"
    )
    assert used == "GroqLlama"

# Requirement 4: Tertiary DeepSeek fallback
@pytest.mark.asyncio
async def test_tertiary_deepseek_fallback():
    primary = MockFailingProvider("GeminiFlash", RateLimitException("429 Rate limit", "GeminiFlash", retry_after=0.01))
    secondary = MockFailingProvider("GroqLlama", LLMServerException("500 Internal error", "GroqLlama"))
    tertiary = MockSuccessProvider("DeepSeek")
    orchestrator = LLMOrchestrator(providers=[primary, secondary, tertiary])
    
    entity, used = await orchestrator.extract_canonical_entity(
        raw_text="Acme AI has 50 employees.",
        record_type=RecordType.STARTUP,
        source_name="MockSource",
        source_url="https://example.com/acme"
    )
    assert used == "DeepSeek"

# Requirement 5: All-provider failure triggers exception
@pytest.mark.asyncio
async def test_all_provider_failure_raises_exception():
    p1 = MockFailingProvider("GeminiFlash", RateLimitException("429 Rate limit", "GeminiFlash", retry_after=0.01))
    p2 = MockFailingProvider("GroqLlama", LLMServerException("500 Internal error", "GroqLlama"))
    orchestrator = LLMOrchestrator(providers=[p1, p2])
    
    with pytest.raises(LLMException) as exc_info:
        await orchestrator.extract_canonical_entity(
            raw_text="Raw startup data",
            record_type=RecordType.STARTUP,
            source_name="MockSource",
            source_url="https://example.com/unsupported_domain_test"
        )
    assert "All LLM providers exhausted" in str(exc_info.value)

# Requirement 6: 429 with Retry-After header parsing
@pytest.mark.asyncio
async def test_429_with_retry_after_parsing():
    rate_limit_err = RateLimitException("Rate limit 429", provider_name="GeminiFlash", retry_after=0.1)
    assert rate_limit_err.retry_after == 0.1

    mock_func = AsyncMock(side_effect=[rate_limit_err, "Success"])
    res = await retry_with_backoff(mock_func, max_retries=2, base_delay=0.05, max_delay=0.2)
    assert res == "Success"
    assert mock_func.call_count == 2

# Requirement 7 & 8: 429 without Retry-After (jittered exponential backoff & bounded retry count)
@pytest.mark.asyncio
async def test_429_bounded_retry_exhaustion():
    rate_limit_err = RateLimitException("Rate limit 429", provider_name="GeminiFlash", retry_after=0.0)
    mock_func = AsyncMock(side_effect=rate_limit_err)
    
    with pytest.raises(RateLimitException):
        await retry_with_backoff(mock_func, max_retries=3, base_delay=0.01, max_delay=0.05)
    assert mock_func.call_count == 3

# Requirement 9 & 10: 413 detection and structural chunking
def test_structural_chunking():
    chunker = IntelligentPayloadChunker()
    paragraphs = [f"Paragraph {i}: " + "word " * 300 for i in range(10)]
    large_text = "\n\n".join(paragraphs)
    
    chunks = chunker.split_into_structural_chunks(large_text, max_words_per_chunk=800)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 1000 for c in chunks)

# Requirement 11: Chunk merge logic
def test_chunk_merge_logic():
    chunker = IntelligentPayloadChunker()
    e1 = {
        "schemaVersion": "1.0",
        "recordType": "RESEARCH_PAPER",
        "content": {
            "title": "Deep Learning Paper",
            "authors": ["Author A"],
            "abstract": "Short abstract"
        }
    }
    e2 = {
        "schemaVersion": "1.0",
        "recordType": "RESEARCH_PAPER",
        "content": {
            "title": "Deep Learning Paper",
            "authors": ["Author B"],
            "abstract": "Longer and more detailed paper abstract describing deep learning innovations."
        }
    }
    merged = chunker.merge_partial_extractions([e1, e2])
    assert merged["content"]["authors"] == ["Author A", "Author B"]
    assert "innovations" in merged["content"]["abstract"]

# Requirement 12: Malformed JSON handling
@pytest.mark.asyncio
async def test_malformed_json_handling():
    malformed_provider = MockFailingProvider("MalformedProvider", MalformedResponseException("Invalid JSON", provider_name="MalformedProvider"))
    
    orchestrator = LLMOrchestrator(providers=[malformed_provider])
    with pytest.raises(LLMException):
        await orchestrator.extract_canonical_entity(
            raw_text="Content",
            record_type=RecordType.STARTUP,
            source_name="Src",
            source_url="https://example.com/startup_test_malformed"
        )

# Requirement 13: Schema validation failure handling
@pytest.mark.asyncio
async def test_schema_validation_failure_handling():
    invalid_schema_dict = {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",
        "source": {"name": "Src", "url": "https://example.com/invalid"},
        "content": {
            "entityName": "Acme",
            "data": {"employeeCount": "INVALID_STRING_INSTEAD_OF_INT"}
        }
    }
    provider = MockSuccessProvider("GeminiFlash", return_dict=invalid_schema_dict)
    orchestrator = LLMOrchestrator(providers=[provider])
    
    with pytest.raises(LLMException):
        await orchestrator.extract_canonical_entity(
            raw_text="Content",
            record_type=RecordType.STARTUP,
            source_name="Src",
            source_url="https://example.com/test_schema_fail"
        )

# Requirement 14: Provider timeout handling
@pytest.mark.asyncio
async def test_provider_timeout_handling():
    timeout_err = LLMTimeoutException("Timeout", provider_name="GeminiFlash")
    p1 = MockFailingProvider("GeminiFlash", timeout_err)
    p2 = MockSuccessProvider("GroqLlama")
    orchestrator = LLMOrchestrator(providers=[p1, p2])
    
    entity, used = await orchestrator.extract_canonical_entity(
        raw_text="Acme data",
        record_type=RecordType.STARTUP,
        source_name="Src",
        source_url="https://example.com/acme"
    )
    assert used == "GroqLlama"

# Requirement 15: Provider authentication failure (401/403) non-retryable behavior
@pytest.mark.asyncio
async def test_non_retryable_auth_failure():
    auth_err = LLMAuthException("401 Unauthorized", provider_name="GeminiFlash", http_status=401)
    mock_func = AsyncMock(side_effect=auth_err)
    
    with pytest.raises(LLMAuthException):
        await retry_with_backoff(mock_func, max_retries=3)
    assert mock_func.call_count == 1

# Requirement 16: Provenance preservation
@pytest.mark.asyncio
async def test_provenance_preservation():
    provider = MockSuccessProvider("GeminiFlash")
    orchestrator = LLMOrchestrator(providers=[provider])
    url = "https://example.com/provenance_test_url"
    
    entity, _ = await orchestrator.extract_canonical_entity(
        raw_text="Company info",
        record_type=RecordType.STARTUP,
        source_name="OfficialSource",
        source_url=url
    )
    assert entity.source.url == url
    assert entity.source.name == "OfficialSource"

# Requirement 17: No fabricated fallback values
@pytest.mark.asyncio
async def test_no_fabricated_values():
    dict_with_nulls = {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",
        "source": {"name": "Src", "url": "https://example.com/acme"},
        "content": {
            "entityName": "Acme AI",
            "data": {"employeeCount": None, "fundingTotalUsd": None}
        },
        "collectedAt": "2026-09-10T12:00:00Z"
    }
    provider = MockSuccessProvider("GeminiFlash", return_dict=dict_with_nulls)
    orchestrator = LLMOrchestrator(providers=[provider])
    
    entity, _ = await orchestrator.extract_canonical_entity(
        raw_text="Acme AI is an AI startup.",
        record_type=RecordType.STARTUP,
        source_name="Src",
        source_url="https://example.com/acme"
    )
    assert entity.content["data"]["employeeCount"] is None

# Requirement 18: Deterministic extraction path preserved for ArXiv source adapter
@pytest.mark.asyncio
async def test_deterministic_arxiv_extraction_path():
    from src.sources.arxiv import ArXivSourceAdapter
    adapter = ArXivSourceAdapter()
    arxiv_html = '<html><head><title>Attention Is All You Need</title><meta name="citation_author" content="Ashish Vaswani"/></head><body><h1 class="title mathjax"><span class="descriptor">Title:</span>Attention Is All You Need</h1><div class="authors"><a href="#">Ashish Vaswani</a></div><blockquote class="abstract mathjax"><span class="descriptor">Abstract:</span>Transformer architecture model.</blockquote></body></html>'
    payload = RawPayload(url="https://arxiv.org/abs/1706.03762", source_name="ArXiv", raw_content=arxiv_html, content_type="text/html", fetched_at="2026-09-10T00:00:00Z")
    
    parsed = adapter.parse_raw_payload(payload)
    assert "Attention Is All You Need" in parsed["content"]["title"]
    assert parsed["content"]["authors"] == ["Ashish Vaswani"]

    # Verify LLMOrchestrator raises LLMException when providers are empty
    orchestrator = LLMOrchestrator(providers=[])
    with pytest.raises(LLMException):
        await orchestrator.extract_canonical_entity(
            raw_text=arxiv_html,
            record_type=RecordType.RESEARCH_PAPER,
            source_name="ArXiv",
            source_url="https://arxiv.org/abs/1706.03762"
        )

# Requirement 19: LLM extraction for messy content
@pytest.mark.asyncio
async def test_llm_extraction_messy_content():
    provider = MockSuccessProvider("GeminiFlash")
    orchestrator = LLMOrchestrator(providers=[provider])
    messy_text = "RANDOM HTML NOISE\nNav Navbar Home\nAcme AI is a leading AI startup with 50 employees."
    
    entity, used = await orchestrator.extract_canonical_entity(
        raw_text=messy_text,
        record_type=RecordType.STARTUP,
        source_name="WebScraper",
        source_url="https://example.com/messy"
    )
    assert used == "GeminiFlash"
    assert entity.content["entityName"] == "Acme AI"

# Requirement 20: Telemetry & metric tracking
@pytest.mark.asyncio
async def test_telemetry_metrics_tracking():
    provider = MockSuccessProvider("GeminiFlash")
    orchestrator = LLMOrchestrator(providers=[provider])
    
    await orchestrator.extract_canonical_entity(
        raw_text="Company info",
        record_type=RecordType.STARTUP,
        source_name="Src",
        source_url="https://example.com/test_metrics"
    )
    metrics_dict = orchestrator.metrics.to_dict()
    assert metrics_dict["llm_requests_total"] == 1
    assert metrics_dict["llm_success_total"] == 1
    assert metrics_dict["llm_failure_total"] == 0
