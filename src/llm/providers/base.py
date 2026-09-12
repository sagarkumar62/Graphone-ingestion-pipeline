from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

class LLMResponse(BaseModel):
    provider_name: str
    model_name: str
    raw_response: str
    extracted_json: dict
    tokens_used: int = 0
    execution_time_seconds: float = 0.0

class BaseLLMProvider(ABC):
    """
    Abstract LLM Provider interface for structured entity extraction.
    All provider adapters (Gemini, Groq, DeepSeek) inherit from this base.
    """
    
    def __init__(self, provider_name: str, model_name: str, api_key: str | None = None, supports_structured: bool = True):
        self._provider_name = provider_name
        self._model_name = model_name
        self.api_key = api_key
        self._supports_structured_output = supports_structured

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def supports_structured_output(self) -> bool:
        return self._supports_structured_output

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count for input text (~4 chars per token rule of thumb)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    @abstractmethod
    async def extract_structured(
        self,
        prompt_text: str,
        target_schema: dict,
        system_instruction: str,
        timeout_seconds: float = 30.0
    ) -> LLMResponse:
        """
        Executes structured JSON extraction.
        Raises RateLimitException (429), ContextWindowExceededException (413), LLMAuthException, or LLMException.
        """
        pass

    async def extract(
        self,
        prompt_text: str,
        target_schema: dict,
        system_instruction: str,
        timeout_seconds: float = 30.0
    ) -> LLMResponse:
        """Alias for extract_structured for backwards compatibility."""
        return await self.extract_structured(prompt_text, target_schema, system_instruction, timeout_seconds)
