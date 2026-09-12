from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Storage
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./pipeline.db")
    RAW_STORAGE_DIR: str = Field(default="./data/raw")
    SCHEMAS_DIR: str = Field(default="./schemas")

    # Bulk Extraction Parameters
    MAX_RECORDS: int = Field(default=10)
    START_OFFSET: int = Field(default=0)
    VERIFICATION_MODE: bool = Field(default=False)
    BULK_BATCH_SIZE: int = Field(default=50)
    CRAWL_CONCURRENCY: int = Field(default=10)
    PER_SOURCE_CONCURRENCY: int = Field(default=3)
    RATE_LIMIT_PER_SECOND: float = Field(default=2.0)
    BACKOFF_BASE: float = Field(default=1.5)
    BACKOFF_MAX: float = Field(default=30.0)
    
    # Environment-Driven LLM Provider & Model Configurations
    LLM_PRIMARY_PROVIDER: str = Field(default="GeminiFlash")
    LLM_PRIMARY_MODEL: str = Field(default="gemini-2.5-flash")
    LLM_SECONDARY_PROVIDER: str = Field(default="GroqCompound")
    LLM_SECONDARY_MODEL: str = Field(default="groq/compound")
    LLM_TERTIARY_PROVIDER: str = Field(default="DeepSeek")
    LLM_TERTIARY_MODEL: str = Field(default="deepseek-chat")

    # LLM API Keys (Loaded from .env / environment)
    GEMINI_API_KEY: str | None = Field(default=None)
    GROQ_API_KEY: str | None = Field(default=None)
    DEEPSEEK_API_KEY: str | None = Field(default=None)
    
    # External APIs
    GITHUB_TOKEN: str | None = Field(default=None)
    
    # Timeouts & Retries
    CRAWLER_TIMEOUT_SECONDS: float = Field(default=15.0)
    MAX_CRAWLER_RETRIES: int = Field(default=3)
    LLM_TIMEOUT_SECONDS: float = Field(default=30.0)
    MAX_LLM_RETRIES: int = Field(default=3)
    LLM_RETRY_BASE_DELAY: float = Field(default=0.05)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()
