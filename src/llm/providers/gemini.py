import json
import time
import asyncio
from src.core.config import settings
from src.llm.providers.base import BaseLLMProvider, LLMResponse
from src.core.exceptions import (
    LLMException, RateLimitException, ContextWindowExceededException,
    LLMAuthException, LLMBadRequestException, LLMNotFoundException,
    LLMServerException, LLMTimeoutException, MalformedResponseException
)
from src.core.logging import logger

class GeminiProvider(BaseLLMProvider):
    """
    Tier 1 Primary LLM Provider: Gemini Flash.
    Fast, cost-effective context window with structured output capabilities.
    """

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        model = model_name or settings.LLM_PRIMARY_MODEL
        super().__init__(provider_name="GeminiFlash", model_name=model, api_key=api_key)

    async def extract_structured(
        self,
        prompt_text: str,
        target_schema: dict,
        system_instruction: str,
        timeout_seconds: float = 30.0
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMAuthException("Gemini API key is not configured.", provider_name=self.provider_name, http_status=401)

        start_time = time.time()
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config={"response_mime_type": "application/json"}
            )
            
            prompt = f"Schema:\n{json.dumps(target_schema, indent=2)}\n\nInput Content:\n{prompt_text}"
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: model.generate_content(prompt)),
                timeout=timeout_seconds
            )

            raw_text = response.text
            try:
                extracted_json = json.loads(raw_text)
            except json.JSONDecodeError as je:
                raise MalformedResponseException(f"Gemini response was invalid JSON: {je}", provider_name=self.provider_name) from je
            
            return LLMResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                raw_response=raw_text,
                extracted_json=extracted_json,
                tokens_used=getattr(response, "usage_metadata", None).total_token_count if hasattr(response, "usage_metadata") and response.usage_metadata else self.estimate_tokens(prompt_text),
                execution_time_seconds=time.time() - start_time
            )

        except asyncio.TimeoutError as e:
            raise LLMTimeoutException(f"Gemini API request timed out (> {timeout_seconds}s)", provider_name=self.provider_name) from e
        except Exception as e:
            if isinstance(e, (LLMException, RateLimitException, ContextWindowExceededException, MalformedResponseException, LLMAuthException)):
                raise e
            err_msg = str(e)
            err_lower = err_msg.lower()

            if "401" in err_msg or "403" in err_msg or "invalid api key" in err_lower or "unauthorized" in err_lower:
                raise LLMAuthException(f"Gemini Auth failure: {err_msg}", provider_name=self.provider_name, http_status=401) from e
            elif "400" in err_msg or "bad request" in err_lower:
                raise LLMBadRequestException(f"Gemini Bad Request: {err_msg}", provider_name=self.provider_name, http_status=400) from e
            elif "404" in err_msg or "not found" in err_lower:
                raise LLMNotFoundException(f"Gemini Model Not Found: {err_msg}", provider_name=self.provider_name, http_status=404) from e
            elif "429" in err_msg or "resourceexhausted" in err_lower or "quota" in err_lower:
                retry_after = 10.0
                raise RateLimitException(f"Gemini Rate Limit hit: {err_msg}", provider_name=self.provider_name, retry_after=retry_after) from e
            elif "413" in err_msg or "contextwindow" in err_lower or "too large" in err_lower:
                raise ContextWindowExceededException(f"Gemini Context Exceeded: {err_msg}", provider_name=self.provider_name) from e
            elif any(code in err_msg for code in ["500", "502", "503", "504"]):
                raise LLMServerException(f"Gemini Server Error: {err_msg}", provider_name=self.provider_name, http_status=500) from e
            else:
                raise LLMException(f"Gemini execution error: {err_msg}", provider_name=self.provider_name) from e
