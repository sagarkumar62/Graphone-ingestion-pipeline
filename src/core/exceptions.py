class PipelineException(Exception):
    """Base exception for all pipeline errors."""
    pass

class CrawlerException(PipelineException):
    """Raised when crawling/scraping a web page fails."""
    pass

class CrawlerTimeoutException(CrawlerException):
    """Raised when a crawler network operation times out."""
    pass

class CrawlerBlockedException(CrawlerException):
    """Raised when anti-bot or HTTP 403 blocks access."""
    pass

class CrawlerAntiBotException(CrawlerBlockedException):
    """Raised specifically when anti-bot challenges or Cloudflare/Datadome protection block access."""
    pass

class CrawlerRateLimitException(CrawlerException):
    """Raised when HTTP 429 rate limit is encountered by crawler."""
    def __init__(self, message: str, retry_after: float = 10.0):
        super().__init__(message)
        self.retry_after = retry_after

class FreshnessUnknownException(PipelineException):
    """Raised when publication timestamp cannot be established for freshness check."""
    pass

class LLMException(PipelineException):
    """Base exception for LLM provider errors."""
    def __init__(self, message: str, provider_name: str = "Unknown", http_status: int | None = None):
        super().__init__(message)
        self.provider_name = provider_name
        self.http_status = http_status

class LLMAuthException(LLMException):
    """Raised on HTTP 401/403 Authentication/Authorization failure (NON-RETRYABLE)."""
    pass

class LLMBadRequestException(LLMException):
    """Raised on HTTP 400 Bad Request (NON-RETRYABLE)."""
    pass

class LLMNotFoundException(LLMException):
    """Raised on HTTP 404 Model or Resource Not Found (NON-RETRYABLE)."""
    pass

class LLMServerException(LLMException):
    """Raised on HTTP 500, 502, 503, 504 Server Errors (RETRYABLE)."""
    pass

class LLMTimeoutException(LLMException):
    """Raised on API network request timeout (RETRYABLE)."""
    pass

class MalformedResponseException(LLMException):
    """Raised when LLM response is unparseable or malformed JSON."""
    pass

class RateLimitException(LLMException):
    """Raised when an LLM provider returns HTTP 429 Rate Limit."""
    def __init__(self, message: str, provider_name: str, retry_after: float = 0.1, http_status: int = 429):
        super().__init__(message, provider_name=provider_name, http_status=http_status)
        self.retry_after = retry_after

class ContextWindowExceededException(LLMException):
    """Raised when payload size triggers HTTP 413 or context overflow."""
    def __init__(self, message: str, provider_name: str, http_status: int = 413):
        super().__init__(message, provider_name=provider_name, http_status=http_status)

class SchemaValidationException(PipelineException):
    """Raised when JSON fails schema validation."""
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors

class EntityResolutionException(PipelineException):
    """Raised during entity mapping failures."""
    pass
