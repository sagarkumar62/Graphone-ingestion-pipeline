import time
import json
from typing import Any
from src.core.config import settings
from src.core.models import RecordType, CanonicalEntity, SourceProvenance
from src.core.exceptions import (
    LLMException, RateLimitException, ContextWindowExceededException,
    LLMAuthException, LLMBadRequestException, LLMNotFoundException,
    LLMServerException, LLMTimeoutException, MalformedResponseException,
    SchemaValidationException
)
from src.llm.providers.base import BaseLLMProvider, LLMResponse
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.groq import GroqProvider
from src.llm.providers.deepseek import DeepSeekProvider
from src.llm.chunker import IntelligentPayloadChunker
from src.llm.retry import retry_with_backoff
from src.crawlers.arxiv_parser import arxiv_parser
from src.validators.schema_validator import JSONSchemaValidator
from src.core.logging import logger

SYSTEM_INSTRUCTION = """
You are a deterministic AI data extraction engine.
Your sole task is to extract structured JSON strictly matching the provided JSON Schema.
CRITICAL RULES:
1. ONLY extract facts explicitly stated in the source text.
2. If a field is missing or ambiguous, output null.
3. NEVER fabricate, guess, or extrapolate values.
4. Output MUST be strictly valid JSON with no conversational text or markdown code fences.
"""

class LLMOrchestratorMetrics:
    """Tracks observability telemetry metrics for LLM orchestration."""

    def __init__(self):
        self.requests_total = 0
        self.success_total = 0
        self.failure_total = 0
        self.fallback_total = 0
        self.rate_limit_429_total = 0
        self.context_413_total = 0
        self.schema_validation_failure_total = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_latency_ms = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_requests_total": self.requests_total,
            "llm_success_total": self.success_total,
            "llm_failure_total": self.failure_total,
            "llm_fallback_total": self.fallback_total,
            "llm_429_total": self.rate_limit_429_total,
            "llm_413_total": self.context_413_total,
            "llm_schema_validation_failure_total": self.schema_validation_failure_total,
            "llm_total_tokens_in": self.total_tokens_in,
            "llm_total_latency_ms": round(self.total_latency_ms, 2)
        }

class LLMOrchestrator:
    """
    Production Multi-Tier LLM Orchestrator managing deterministic provider fallback:
    Primary (Gemini Flash) -> Secondary (Groq Llama) -> Tertiary (DeepSeek) -> DLQ / DOM extractor.
    Enforces strict zero-fabrication, schema validation, 413 section chunking, 429 Retry-After handling,
    and telemetry instrumentation.
    """

    def __init__(
        self,
        providers: list[BaseLLMProvider] | None = None,
        schemas_dir: str | None = None
    ):
        self.chunker = IntelligentPayloadChunker()
        self.validator = JSONSchemaValidator(schemas_dir=schemas_dir)
        self.metrics = LLMOrchestratorMetrics()

        if providers is not None:
            self.providers = providers
        else:
            self.providers = []
            if settings.GEMINI_API_KEY:
                self.providers.append(GeminiProvider(api_key=settings.GEMINI_API_KEY))
            if settings.GROQ_API_KEY:
                self.providers.append(GroqProvider(api_key=settings.GROQ_API_KEY))
            if settings.DEEPSEEK_API_KEY:
                self.providers.append(DeepSeekProvider(api_key=settings.DEEPSEEK_API_KEY))

    def _create_provider_instance(self, name: str) -> BaseLLMProvider | None:
        name_lower = name.lower()
        if "gemini" in name_lower:
            key = settings.GEMINI_API_KEY
            return GeminiProvider(api_key=key) if key else None
        elif "groq" in name_lower:
            key = settings.GROQ_API_KEY
            return GroqProvider(api_key=key) if key else None
        elif "deepseek" in name_lower:
            key = settings.DEEPSEEK_API_KEY
            return DeepSeekProvider(api_key=key) if key else None
        return None

    async def extract_canonical_entity(
        self,
        raw_text: str,
        record_type: RecordType,
        source_name: str,
        source_url: str
    ) -> tuple[CanonicalEntity, str]:
        """
        Extracts structured canonical entity JSON from raw text using multi-tier fallback chain.
        Returns (canonical_entity, used_provider_name).
        Raises LLMException / SchemaValidationException for DLQ routing if extraction fails completely.
        """
        self.metrics.requests_total += 1
        cleaned_text = self.chunker.process_raw_payload(raw_text)
        target_schema = self.validator._schemas.get(record_type.value, {})
        
        extracted_dict = None
        used_provider_name = None
        attempt_logs = []

        # Iterate through configured provider fallback tiers
        for tier_idx, provider in enumerate(self.providers):
            start_attempt_time = time.time()
            if tier_idx > 0:
                self.metrics.fallback_total += 1

            logger.info(
                f"Attempting LLM extraction tier {tier_idx + 1}/{len(self.providers)}: '{provider.provider_name}' ({provider.model_name})",
                extra={"record_type": record_type.value, "url": source_url}
            )

            try:
                # Wrap execution in bounded retry for transient errors
                async def execute_attempt():
                    return await provider.extract_structured(
                        prompt_text=cleaned_text,
                        target_schema=target_schema,
                        system_instruction=SYSTEM_INSTRUCTION
                    )

                try:
                    response: LLMResponse = await retry_with_backoff(
                        execute_attempt,
                        max_retries=settings.MAX_LLM_RETRIES,
                        base_delay=settings.LLM_RETRY_BASE_DELAY,
                        max_delay=15.0,
                        retryable_exceptions=(RateLimitException, LLMServerException, LLMTimeoutException)
                    )
                except ContextWindowExceededException:
                    self.metrics.context_413_total += 1
                    logger.warning(f"Context 413 on {provider.provider_name}. Executing structural chunking & partial extraction merging...")
                    
                    # 413 Chunking: split document into section chunks, extract per chunk, and merge
                    chunks = self.chunker.split_into_structural_chunks(cleaned_text, max_words_per_chunk=1200)
                    chunk_responses = []
                    
                    for sub_chunk in chunks:
                        chunk_res = await provider.extract_structured(
                            prompt_text=sub_chunk,
                            target_schema=target_schema,
                            system_instruction=SYSTEM_INSTRUCTION
                        )
                        chunk_responses.append(chunk_res.extracted_json)

                    merged_json = self.chunker.merge_partial_extractions(chunk_responses)
                    response = LLMResponse(
                        provider_name=provider.provider_name,
                        model_name=provider.model_name,
                        raw_response=json.dumps(merged_json),
                        extracted_json=merged_json,
                        tokens_used=sum(provider.estimate_tokens(c) for c in chunks),
                        execution_time_seconds=time.time() - start_attempt_time
                    )

                # Track token and latency metrics
                self.metrics.total_tokens_in += response.tokens_used
                latency_ms = round((time.time() - start_attempt_time) * 1000, 2)
                self.metrics.total_latency_ms += latency_ms

                # Schema Validation
                is_valid, errors = self.validator.validate(response.extracted_json, record_type)
                if is_valid:
                    extracted_dict = response.extracted_json
                    used_provider_name = provider.provider_name
                    self.metrics.success_total += 1

                    attempt_log = {
                        "provider": provider.provider_name,
                        "model": provider.model_name,
                        "attempt": tier_idx + 1,
                        "error_class": None,
                        "http_status": 200,
                        "latency_ms": latency_ms,
                        "fallback_reason": None,
                        "final_status": "SUCCESS"
                    }
                    attempt_logs.append(attempt_log)
                    logger.info(f"LLM extraction successful via {provider.provider_name}", extra=attempt_log)
                    break
                else:
                    self.metrics.schema_validation_failure_total += 1
                    attempt_log = {
                        "provider": provider.provider_name,
                        "model": provider.model_name,
                        "attempt": tier_idx + 1,
                        "error_class": "SchemaValidationException",
                        "http_status": 422,
                        "latency_ms": latency_ms,
                        "fallback_reason": f"Schema validation failed: {errors[:2]}",
                        "final_status": "VALIDATION_FAILED"
                    }
                    attempt_logs.append(attempt_log)
                    logger.warning(f"Schema validation failed on provider {provider.provider_name}", extra=attempt_log)

            except RateLimitException as e:
                self.metrics.rate_limit_429_total += 1
                attempt_logs.append({
                    "provider": provider.provider_name,
                    "model": provider.model_name,
                    "attempt": tier_idx + 1,
                    "error_class": "RateLimitException",
                    "http_status": 429,
                    "latency_ms": round((time.time() - start_attempt_time) * 1000, 2),
                    "fallback_reason": str(e),
                    "final_status": "FALLBACK"
                })
                logger.warning(f"RateLimit 429 on {provider.provider_name}. Falling back to next tier...")

            except LLMAuthException as e:
                attempt_logs.append({
                    "provider": provider.provider_name,
                    "model": provider.model_name,
                    "attempt": tier_idx + 1,
                    "error_class": "LLMAuthException",
                    "http_status": 401,
                    "latency_ms": round((time.time() - start_attempt_time) * 1000, 2),
                    "fallback_reason": str(e),
                    "final_status": "FALLBACK"
                })
                logger.warning(f"Auth failure (401/403) on {provider.provider_name}. Falling back to next tier...")

            except Exception as e:
                attempt_logs.append({
                    "provider": provider.provider_name,
                    "model": provider.model_name,
                    "attempt": tier_idx + 1,
                    "error_class": e.__class__.__name__,
                    "http_status": getattr(e, "http_status", 500),
                    "latency_ms": round((time.time() - start_attempt_time) * 1000, 2),
                    "fallback_reason": str(e),
                    "final_status": "FALLBACK"
                })
                logger.warning(f"Provider {provider.provider_name} failed: {e}. Falling back to next tier...")

        # If all configured LLM provider tiers failed or were unconfigured, fail extraction for DLQ routing
        if extracted_dict is None:
            self.metrics.failure_total += 1
            raise LLMException(
                f"All LLM providers exhausted ({len(self.providers)} tiers tried) for {source_url}",
                provider_name="MultiTierOrchestrator"
            )

        # Validate final output structure against JSON Schema
        self.validator.validate_or_raise(extracted_dict, record_type)

        # Build canonical entity with preserved provenance
        canonical_entity = CanonicalEntity(
            schemaVersion=extracted_dict.get("schemaVersion", "1.0"),
            recordType=record_type,
            source=SourceProvenance(name=source_name, url=source_url),
            content=extracted_dict.get("content", {}),
            collectedAt=extracted_dict.get("collectedAt", "")
        )

        return canonical_entity, used_provider_name or "UnknownProvider"

orchestrator = LLMOrchestrator()
