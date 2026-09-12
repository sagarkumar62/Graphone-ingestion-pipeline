from abc import ABC, abstractmethod
from src.core.models import RecordType, RawPayload, CanonicalEntity
from src.crawlers.extractor import html_extractor
from src.utils.hashing import hash_url

class ExtractionStrategy:
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"

class BaseSourceAdapter(ABC):
    """
    Abstract Source Adapter Interface.
    Each target data source implements this interface to handle discovery,
    pagination, rate limiting, and extraction strategy without hardcoded logic in core pipeline.
    """

    def __init__(
        self,
        source_name: str,
        record_type: RecordType,
        extraction_strategy: str = ExtractionStrategy.DETERMINISTIC,
        requests_per_second: float = 2.0
    ):
        self.source_name = source_name
        self.record_type = record_type
        self.extraction_strategy = extraction_strategy
        self.requests_per_second = requests_per_second

    @abstractmethod
    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        """
        Discovers candidate URLs or API endpoints for bulk ingestion.
        Supports pagination via start_offset and max_records.
        """
        pass

    @abstractmethod
    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        """
        Parses raw payload content into dictionary matching canonical entity format.
        """
        pass

    def extract_content(self, raw_payload: RawPayload) -> str:
        """Default full-text content extractor."""
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        return extracted.main_text or raw_payload.raw_content

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        """Default publication date extractor from metadata / JSON-LD."""
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        if extracted.meta_dates:
            return extracted.meta_dates[0]
        if extracted.json_ld_dates:
            return extracted.json_ld_dates[0]
        return None

    def identify_record(self, raw_payload: RawPayload) -> str:
        """Generates stable record identity string based on source name + canonical URL."""
        return f"{self.source_name.lower()}:{hash_url(raw_payload.url)}"
