import os
import pytest
from dotenv import load_dotenv
from src.core.models import RecordType, RawPayload
from src.llm.orchestrator import LLMOrchestrator
from src.llm.providers.base import BaseLLMProvider, LLMResponse
from src.llm.providers.groq import GroqProvider
from src.llm.providers.deepseek import DeepSeekProvider
from src.llm.validator import LLMProviderValidator, ProviderStatus
from src.core.exceptions import LLMServerException, LLMAuthException, LLMNotFoundException, LLMException
from src.sources.arxiv import ArXivSourceAdapter
from src.crawlers.arxiv_parser import arxiv_parser

load_dotenv('.env', override=True)

class DummySuccessProvider(BaseLLMProvider):
    def __init__(self, name: str):
        super().__init__(provider_name=name, model_name="mock-model", api_key="valid_key")

    async def extract_structured(self, prompt_text: str, target_schema: dict, system_instruction: str, timeout_seconds: float = 30.0) -> LLMResponse:
        return LLMResponse(
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response='{"title": "Test Paper", "authors": ["Alice"], "published_date": "2026-01-01", "abstract": "Test abstract"}',
            extracted_json={
                "schemaVersion": "1.0",
                "recordType": "RESEARCH_PAPER",
                "source": {"name": "ArXiv", "url": "https://arxiv.org/abs/2609.10464v1"},
                "content": {
                    "title": "Test Paper",
                    "authors": ["Alice"],
                    "paper_url": "https://arxiv.org/abs/2609.10464v1",
                    "github_url": None,
                    "github_stars": None,
                    "published_date": "2026-01-01T00:00:00Z",
                    "abstract": "Test abstract",
                    "primaryCategory": "cs.AI"
                },
                "collectedAt": "2026-09-10T00:00:00Z"
            },
            tokens_used=100,
            execution_time_seconds=0.1
        )

class DummyFailingProvider(BaseLLMProvider):
    def __init__(self, name: str, exc: Exception):
        super().__init__(provider_name=name, model_name="mock-model", api_key="valid_key")
        self.exc = exc

    async def extract_structured(self, prompt_text: str, target_schema: dict, system_instruction: str, timeout_seconds: float = 30.0) -> LLMResponse:
        raise self.exc

class DummyDisabledProvider(BaseLLMProvider):
    def __init__(self, name: str):
        super().__init__(provider_name=name, model_name="mock-model", api_key=None)

    async def extract_structured(self, prompt_text: str, target_schema: dict, system_instruction: str, timeout_seconds: float = 30.0) -> LLMResponse:
        raise LLMAuthException("API key unconfigured", provider_name=self.provider_name, http_status=401)

@pytest.mark.asyncio
async def test_provider_validator_statuses():
    p_ok = DummySuccessProvider("ProviderOK")
    p_disabled = DummyDisabledProvider("ProviderDisabled")
    p_auth_fail = DummyFailingProvider("ProviderAuthFail", LLMAuthException("401 Unauthorized", provider_name="ProviderAuthFail", http_status=401))
    p_model_fail = DummyFailingProvider("ProviderModelFail", LLMNotFoundException("404 Model Not Found", provider_name="ProviderModelFail", http_status=404))

    assert await LLMProviderValidator.validate_provider(p_ok) == ProviderStatus.AVAILABLE
    assert await LLMProviderValidator.validate_provider(p_disabled) == ProviderStatus.DISABLED
    assert await LLMProviderValidator.validate_provider(p_auth_fail) == ProviderStatus.AUTHENTICATION_FAILED
    assert await LLMProviderValidator.validate_provider(p_model_fail) == ProviderStatus.MODEL_UNAVAILABLE

@pytest.mark.asyncio
async def test_all_provider_failure_routes_to_dlq():
    p_fail1 = DummyFailingProvider("Tier1Fail", LLMServerException("500 Server Error", provider_name="Tier1Fail"))
    p_fail2 = DummyFailingProvider("Tier2Fail", LLMServerException("500 Server Error", provider_name="Tier2Fail"))
    orch = LLMOrchestrator(providers=[p_fail1, p_fail2])

    with pytest.raises(LLMException) as exc_info:
        await orch.extract_canonical_entity(
            raw_text="Sample paper text",
            record_type=RecordType.RESEARCH_PAPER,
            source_name="ArXiv",
            source_url="https://arxiv.org/abs/2609.10464v1"
        )
    assert "All LLM providers exhausted" in str(exc_info.value)

@pytest.mark.asyncio
async def test_deterministic_parser_is_not_generic_llm_fallback():
    p_fail = DummyFailingProvider("Tier1Fail", LLMServerException("500 Server Error", provider_name="Tier1Fail"))
    orch = LLMOrchestrator(providers=[p_fail])

    with pytest.raises(LLMException):
        await orch.extract_canonical_entity(
            raw_text="<html><body><h1>Title: Test</h1></body></html>",
            record_type=RecordType.RESEARCH_PAPER,
            source_name="ArXiv",
            source_url="https://arxiv.org/abs/2609.10464v1"
        )

@pytest.mark.asyncio
async def test_gemini_failure_groq_live_success():
    p_gemini_fail = DummyFailingProvider("GeminiSimulatedFail", LLMServerException("500 Gemini Injected Error"))
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        pytest.skip("GROQ_API_KEY not set")
    p_groq_real = GroqProvider(api_key=groq_key)
    orch = LLMOrchestrator(providers=[p_gemini_fail, p_groq_real])

    raw_text = """
    Title: Semigroup-JEPA: Latent Dynamics Consistency for Zero-Shot Physics Generalization
    Authors: Liu, Andy Zeyi; Sun, Haoran; Baker, Lucas; Balestriero, Randall; Sous, John
    Published Date: 2026-09-09
    Abstract: Joint-Embedding Predictive Architecture (JEPA) world models learn a compact latent representation of the world that supports prediction and planning. In this work, we introduce SemiGroup-JEPA (SG-JEPA).
    URL: https://arxiv.org/abs/2609.10464v1
    Category: cs.AI
    """

    try:
        entity, used_provider = await orch.extract_canonical_entity(
            raw_text=raw_text,
            record_type=RecordType.RESEARCH_PAPER,
            source_name="ArXiv",
            source_url="https://arxiv.org/abs/2609.10464v1"
        )
        assert used_provider == "GroqLlama"
        assert "Semigroup-JEPA" in entity.content["title"]
    except LLMException as e:
        pytest.skip(f"Live Groq API quota exhausted or rate limited: {e}")

@pytest.mark.asyncio
async def test_unavailable_deepseek_does_not_create_success():
    p_gemini_fail = DummyFailingProvider("GeminiSimulatedFail", LLMServerException("500 Gemini Error"))
    p_groq_fail = DummyFailingProvider("GroqSimulatedFail", LLMServerException("500 Groq Error"))
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "invalid_key")
    p_deepseek_auth_fail = DeepSeekProvider(api_key=deepseek_key)

    orch = LLMOrchestrator(providers=[p_gemini_fail, p_groq_fail, p_deepseek_auth_fail])

    with pytest.raises(LLMException):
        await orch.extract_canonical_entity(
            raw_text="Sample raw text",
            record_type=RecordType.RESEARCH_PAPER,
            source_name="ArXiv",
            source_url="https://arxiv.org/abs/2609.10464v1"
        )

def test_source_specific_arxiv_parser_still_works():
    html_content = """
    <html>
      <head><meta name="citation_title" content="Deterministic Paper Title"/></head>
      <body>
        <div class="authors"><a>Author One</a></div>
        <blockquote class="abstract">Abstract content here</blockquote>
      </body>
    </html>
    """
    parsed = arxiv_parser.parse_arxiv_html(html_content, "https://arxiv.org/abs/2609.99999")
    assert parsed["content"]["title"] == "Deterministic Paper Title"
    assert parsed["content"]["authors"] == ["Author One"]
    assert parsed["content"]["abstract"] == "Abstract content here"
