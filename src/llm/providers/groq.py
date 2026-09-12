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

class GroqProvider(BaseLLMProvider):
    """
    Tier 2 Secondary LLM Provider: Groq Llama.
    Ultra-low latency fallback for 429 rate limit or outage on primary provider.
    """

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        model = model_name or settings.LLM_SECONDARY_MODEL
        super().__init__(provider_name="GroqLlama", model_name=model, api_key=api_key)

    async def extract_structured(
        self,
        prompt_text: str,
        target_schema: dict,
        system_instruction: str,
        timeout_seconds: float = 30.0
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMAuthException("Groq API key is not configured.", provider_name=self.provider_name, http_status=401)

        start_time = time.time()
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.api_key)

            sys_instruct = system_instruction if "json" in system_instruction.lower() else f"{system_instruction} Respond in valid JSON format."
            messages = [
                {"role": "system", "content": sys_instruct},
                {"role": "user", "content": f"Schema:\n{json.dumps(target_schema, indent=2)}\n\nInput Content:\n{prompt_text}"}
            ]

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=1000
                ),
                timeout=timeout_seconds
            )

            raw_text = response.choices[0].message.content
            try:
                extracted_json = json.loads(raw_text)
            except json.JSONDecodeError as je:
                raise MalformedResponseException(f"Groq response was invalid JSON: {je}", provider_name=self.provider_name) from je

            return LLMResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                raw_response=raw_text,
                extracted_json=extracted_json,
                tokens_used=response.usage.total_tokens if response and getattr(response, "usage", None) else self.estimate_tokens(prompt_text),
                execution_time_seconds=time.time() - start_time
            )

        except asyncio.TimeoutError as e:
            raise LLMTimeoutException(f"Groq API request timed out (> {timeout_seconds}s)", provider_name=self.provider_name) from e
        except Exception as e:
            if isinstance(e, (LLMException, RateLimitException, ContextWindowExceededException, MalformedResponseException, LLMAuthException)):
                raise e
            err_msg = str(e)
            err_lower = err_msg.lower()

            if "401" in err_msg or "403" in err_msg or "invalid api key" in err_lower or "unauthorized" in err_lower:
                raise LLMAuthException(f"Groq Auth failure: {err_msg}", provider_name=self.provider_name, http_status=401) from e
            elif "400" in err_msg or "bad_request" in err_lower:
                raise LLMBadRequestException(f"Groq Bad Request: {err_msg}", provider_name=self.provider_name, http_status=400) from e
            elif "404" in err_msg or "not_found" in err_lower:
                raise LLMNotFoundException(f"Groq Model Not Found: {err_msg}", provider_name=self.provider_name, http_status=404) from e
            elif "429" in err_msg or "rate_limit" in err_lower:
                retry_after = 10.0
                raise RateLimitException(f"Groq Rate Limit hit: {err_msg}", provider_name=self.provider_name, retry_after=retry_after) from e
            elif "413" in err_msg or "too_large" in err_lower:
                raise ContextWindowExceededException(f"Groq Context Exceeded: {err_msg}", provider_name=self.provider_name) from e
            elif any(code in err_msg for code in ["500", "502", "503", "504"]):
                raise LLMServerException(f"Groq Server Error: {err_msg}", provider_name=self.provider_name, http_status=500) from e
            else:
                raise LLMException(f"Groq execution error: {err_msg}", provider_name=self.provider_name) from e
