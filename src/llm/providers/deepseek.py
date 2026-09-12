import json
import time
import asyncio
import httpx
from src.core.config import settings
from src.llm.providers.base import BaseLLMProvider, LLMResponse
from src.core.exceptions import (
    LLMException, RateLimitException, ContextWindowExceededException,
    LLMAuthException, LLMBadRequestException, LLMNotFoundException,
    LLMServerException, LLMTimeoutException, MalformedResponseException
)
from src.core.logging import logger

class DeepSeekProvider(BaseLLMProvider):
    """
    Tier 3 Tertiary LLM Provider: DeepSeek.
    High-reasoning extraction fallback when Primary and Secondary tiers are unavailable.
    """

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        model = model_name or settings.LLM_TERTIARY_MODEL
        super().__init__(provider_name="DeepSeek", model_name=model, api_key=api_key)

    async def extract_structured(
        self,
        prompt_text: str,
        target_schema: dict,
        system_instruction: str,
        timeout_seconds: float = 30.0
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMAuthException("DeepSeek API key is not configured.", provider_name=self.provider_name, http_status=401)

        start_time = time.time()
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Schema:\n{json.dumps(target_schema, indent=2)}\n\nInput Content:\n{prompt_text}"}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code in (401, 403):
                    raise LLMAuthException(f"DeepSeek Auth Error {response.status_code}: {response.text}", provider_name=self.provider_name, http_status=response.status_code)
                elif response.status_code == 400:
                    raise LLMBadRequestException(f"DeepSeek Bad Request: {response.text}", provider_name=self.provider_name, http_status=400)
                elif response.status_code == 404:
                    raise LLMNotFoundException(f"DeepSeek Model/Resource Not Found: {response.text}", provider_name=self.provider_name, http_status=404)
                elif response.status_code == 429:
                    retry_after = float(response.headers.get("retry-after", 10.0))
                    raise RateLimitException(f"DeepSeek Rate Limit: {response.text}", provider_name=self.provider_name, retry_after=retry_after, http_status=429)
                elif response.status_code == 413:
                    raise ContextWindowExceededException(f"DeepSeek Context Exceeded: {response.text}", provider_name=self.provider_name, http_status=413)
                elif response.status_code >= 500:
                    raise LLMServerException(f"DeepSeek Server Error {response.status_code}: {response.text}", provider_name=self.provider_name, http_status=response.status_code)
                elif response.status_code >= 400:
                    raise LLMException(f"DeepSeek HTTP {response.status_code}: {response.text}", provider_name=self.provider_name, http_status=response.status_code)

                res_json = response.json()
                raw_text = res_json["choices"][0]["message"]["content"]
                try:
                    extracted_json = json.loads(raw_text)
                except json.JSONDecodeError as je:
                    raise MalformedResponseException(f"DeepSeek response was invalid JSON: {je}", provider_name=self.provider_name) from je

                return LLMResponse(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    raw_response=raw_text,
                    extracted_json=extracted_json,
                    tokens_used=res_json.get("usage", {}).get("total_tokens", self.estimate_tokens(prompt_text)),
                    execution_time_seconds=time.time() - start_time
                )

        except httpx.TimeoutException as e:
            raise LLMTimeoutException(f"DeepSeek API request timed out (> {timeout_seconds}s)", provider_name=self.provider_name) from e
        except Exception as e:
            if isinstance(e, (LLMException, RateLimitException, ContextWindowExceededException, MalformedResponseException)):
                raise e
            raise LLMException(f"DeepSeek execution error: {e}", provider_name=self.provider_name) from e
