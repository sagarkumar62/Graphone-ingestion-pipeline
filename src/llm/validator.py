from enum import Enum
from typing import Dict, List, Optional
from src.llm.providers.base import BaseLLMProvider
from src.core.exceptions import (
    LLMAuthException, LLMNotFoundException, LLMBadRequestException, LLMException
)
from src.core.logging import logger

class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    DISABLED = "DISABLED"

class LLMProviderValidator:
    """
    Lightweight startup and runtime provider/model validator.
    Determines availability status for each configured LLM provider tier
    without blocking application startup if secondary/tertiary providers are unavailable.
    """

    @staticmethod
    async def validate_provider(provider: BaseLLMProvider) -> ProviderStatus:
        """Validates a single provider's key and model availability."""
        if not provider.api_key or not provider.api_key.strip():
            return ProviderStatus.DISABLED

        test_schema = {
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "required": ["status"]
        }
        test_prompt = "Extract status. Input text: The system status is ok."
        test_instruction = "You are a precise data extractor. Extract the status field and return as json."

        try:
            res = await provider.extract_structured(
                prompt_text=test_prompt,
                target_schema=test_schema,
                system_instruction=test_instruction,
                timeout_seconds=10.0
            )
            if res and res.extracted_json:
                return ProviderStatus.AVAILABLE
            return ProviderStatus.CONFIGURATION_ERROR
        except LLMAuthException:
            return ProviderStatus.AUTHENTICATION_FAILED
        except (LLMNotFoundException, LLMBadRequestException) as e:
            err_str = str(e).lower()
            if "decommissioned" in err_str or "not found" in err_str or "404" in err_str or "model" in err_str:
                return ProviderStatus.MODEL_UNAVAILABLE
            return ProviderStatus.CONFIGURATION_ERROR
        except Exception as e:
            logger.warning(f"Provider validation check failed for {provider.provider_name}: {e}")
            return ProviderStatus.CONFIGURATION_ERROR

    @classmethod
    async def validate_all_providers(cls, providers: List[BaseLLMProvider]) -> Dict[str, ProviderStatus]:
        """Validates all configured providers and returns a status mapping."""
        statuses = {}
        for p in providers:
            status = await cls.validate_provider(p)
            statuses[p.provider_name] = status
            logger.info(f"Provider status check: {p.provider_name} ({p.model_name}) -> {status.value}")
        return statuses
