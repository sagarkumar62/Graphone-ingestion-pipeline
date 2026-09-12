import re
import httpx
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from src.sources.base import BaseSourceAdapter, ExtractionStrategy
from src.core.models import RecordType, RawPayload
from src.crawlers.extractor import html_extractor
from src.utils.time import parse_date_string, format_iso8601
from src.core.logging import logger

KNOWN_AI_ENTITIES = [
    "OpenAI", "Anthropic", "NVIDIA", "Google", "DeepMind", "Microsoft", "Meta",
    "HuggingFace", "Mistral", "Cohere", "xAI", "Apple", "Amazon", "Scale AI",
    "Stability AI", "Perplexity", "LangChain", "Llama", "ChatGPT", "Claude",
    "Gemini", "GPT-4", "GPT-4o", "DeepSeek", "Qwen", "PyTorch", "TensorFlow", "CUDA"
]

def extract_entities_mentioned(text: str) -> list[str]:
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for entity in KNOWN_AI_ENTITIES:
        pattern = r"\b" + re.escape(entity.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(entity)
    return found


class HuggingFaceDailyPapersSource(BaseSourceAdapter):
    """
    HuggingFace Daily Papers AI News Adapter.
    API endpoint: https://huggingface.co/api/daily_papers
    """

    def __init__(self):
        super().__init__(
            source_name="HuggingFaceDailyPapers",
            record_type=RecordType.NEWS,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.api_url = "https://huggingface.co/api/daily_papers"
        self._api_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                res = await client.get(self.api_url)
                if res.status_code == 200:
                    data = res.json()
                    for item in data:
                        paper = item.get("paper", {})
                        id_str = paper.get("id")
                        if id_str:
                            url = f"https://huggingface.co/papers/{id_str}"
                            submitted_date = paper.get("submittedOnDailyAt") or paper.get("publishedAt") or item.get("publishedAt")
                            pub_iso = None
                            if submitted_date:
                                dt = parse_date_string(submitted_date)
                                if dt:
                                    pub_iso = format_iso8601(dt)
                            self._api_metadata[url] = {
                                "pub_date": pub_iso,
                                "api_title": paper.get("title") or item.get("title"),
                                "api_summary": paper.get("summary") or item.get("summary"),
                            }
                            discovered.append(url)
        except Exception as e:
            logger.warning(f"HuggingFace discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        meta = self._api_metadata.get(raw_payload.url, {})
        if meta.get("pub_date"):
            return meta["pub_date"]
        raw_date = super().extract_published_at(raw_payload)
        if raw_date:
            dt = parse_date_string(raw_date)
            if dt:
                return format_iso8601(dt)
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        meta = self._api_metadata.get(raw_payload.url, {})
        pub_date = self.extract_published_at(raw_payload)

        title = meta.get("api_title") or extracted.title or "HuggingFace Daily Paper"
        summary = meta.get("api_summary") or extracted.meta_description or (extracted.main_text[:300] if extracted.main_text else "HuggingFace Daily Paper")
        full_text = extracted.main_text if extracted.main_text and len(extracted.main_text) > 0 else summary

        entities = extract_entities_mentioned(title + " " + summary + " " + full_text)

        return {
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "title": title,
                "summary": summary,
                "full_text": full_text,
                "published_date": pub_date or "",
                "entities_mentioned": entities
            },
            "collectedAt": format_iso8601()
        }


class TechCrunchAISource(BaseSourceAdapter):
    """
    TechCrunch AI News RSS Adapter.
    Feed: https://techcrunch.com/category/artificial-intelligence/feed/
    """

    def __init__(self):
        super().__init__(
            source_name="TechCrunchAI",
            record_type=RecordType.NEWS,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=1.5
        )
        self.feed_url = "https://techcrunch.com/category/artificial-intelligence/feed/"
        self._rss_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                res = await client.get(self.feed_url)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    for item in root.findall(".//item"):
                        link = item.find("link")
                        pub_date = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
                        title = item.find("title")
                        description = item.find("description")
                        if link is not None and link.text:
                            url = link.text.strip()
                            self._rss_metadata[url] = {
                                "pub_date": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                "title": title.text.strip() if title is not None and title.text else None,
                                "description": description.text.strip() if description is not None and description.text else None
                            }
                            discovered.append(url)
        except Exception as e:
            logger.warning(f"TechCrunch RSS discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        meta = self._rss_metadata.get(raw_payload.url, {})
        if meta.get("pub_date"):
            dt = parse_date_string(meta["pub_date"])
            if dt:
                return format_iso8601(dt)
        raw_date = super().extract_published_at(raw_payload)
        if raw_date:
            dt = parse_date_string(raw_date)
            if dt:
                return format_iso8601(dt)
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        meta = self._rss_metadata.get(raw_payload.url, {})
        pub_date = self.extract_published_at(raw_payload)

        title = meta.get("title") or extracted.title or "TechCrunch AI News"
        summary = meta.get("description") or extracted.meta_description or (extracted.main_text[:300] if extracted.main_text else "TechCrunch AI News article")
        full_text = extracted.main_text if extracted.main_text and len(extracted.main_text) > 0 else summary

        entities = extract_entities_mentioned(title + " " + summary + " " + full_text)

        return {
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "title": title,
                "summary": summary,
                "full_text": full_text,
                "published_date": pub_date or "",
                "entities_mentioned": entities
            },
            "collectedAt": format_iso8601()
        }


class MITTechReviewAISource(BaseSourceAdapter):
    """
    MIT Tech Review AI News RSS Adapter.
    Feed: https://www.technologyreview.com/topic/artificial-intelligence/feed
    """

    def __init__(self):
        super().__init__(
            source_name="MITTechReviewAI",
            record_type=RecordType.NEWS,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=1.5
        )
        self.feed_url = "https://www.technologyreview.com/topic/artificial-intelligence/feed"
        self._rss_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                res = await client.get(self.feed_url)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    for item in root.findall(".//item"):
                        link = item.find("link")
                        pub_date = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
                        title = item.find("title")
                        description = item.find("description")
                        if link is not None and link.text:
                            url = link.text.strip()
                            self._rss_metadata[url] = {
                                "pub_date": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                "title": title.text.strip() if title is not None and title.text else None,
                                "description": description.text.strip() if description is not None and description.text else None
                            }
                            discovered.append(url)
        except Exception as e:
            logger.warning(f"MIT Tech Review RSS discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        meta = self._rss_metadata.get(raw_payload.url, {})
        if meta.get("pub_date"):
            dt = parse_date_string(meta["pub_date"])
            if dt:
                return format_iso8601(dt)
        raw_date = super().extract_published_at(raw_payload)
        if raw_date:
            dt = parse_date_string(raw_date)
            if dt:
                return format_iso8601(dt)
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        meta = self._rss_metadata.get(raw_payload.url, {})
        pub_date = self.extract_published_at(raw_payload)

        title = meta.get("title") or extracted.title or "MIT Technology Review AI"
        summary = meta.get("description") or extracted.meta_description or (extracted.main_text[:300] if extracted.main_text else "MIT Technology Review AI article")
        full_text = extracted.main_text if extracted.main_text and len(extracted.main_text) > 0 else summary

        entities = extract_entities_mentioned(title + " " + summary + " " + full_text)

        return {
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "title": title,
                "summary": summary,
                "full_text": full_text,
                "published_date": pub_date or "",
                "entities_mentioned": entities
            },
            "collectedAt": format_iso8601()
        }


class OpenAIBlogSource(BaseSourceAdapter):
    """
    OpenAI Blog / News Adapter.
    Primary feed: https://openai.com/news/rss.xml
    """

    def __init__(self):
        super().__init__(
            source_name="OpenAIBlog",
            record_type=RecordType.NEWS,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.rss_url = "https://openai.com/news/rss.xml"
        self._rss_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                res = await client.get(self.rss_url)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    for item in root.findall(".//item"):
                        link = item.find("link")
                        pub_date = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
                        title = item.find("title")
                        description = item.find("description")
                        if link is not None and link.text:
                            url = link.text.strip()
                            self._rss_metadata[url] = {
                                "pub_date": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                "title": title.text.strip() if title is not None and title.text else None,
                                "description": description.text.strip() if description is not None and description.text else None
                            }
                            discovered.append(url)
                else:
                    logger.warning(f"OpenAI Blog RSS returned HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"OpenAI Blog RSS discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        meta = self._rss_metadata.get(raw_payload.url, {})
        if meta.get("pub_date"):
            dt = parse_date_string(meta["pub_date"])
            if dt:
                return format_iso8601(dt)
        raw_date = super().extract_published_at(raw_payload)
        if raw_date:
            dt = parse_date_string(raw_date)
            if dt:
                return format_iso8601(dt)
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        meta = self._rss_metadata.get(raw_payload.url, {})
        pub_date = self.extract_published_at(raw_payload)

        title = meta.get("title") or extracted.title or "OpenAI News Announcement"
        summary = meta.get("description") or extracted.meta_description or (extracted.main_text[:300] if extracted.main_text else "OpenAI News")
        full_text = extracted.main_text if extracted.main_text and len(extracted.main_text) > 0 else summary

        entities = extract_entities_mentioned(title + " " + summary + " " + full_text)

        return {
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "title": title,
                "summary": summary,
                "full_text": full_text,
                "published_date": pub_date or "",
                "entities_mentioned": entities
            },
            "collectedAt": format_iso8601()
        }


class HackerNewsAISource(BaseSourceAdapter):
    """
    Hacker News AI Top Stories Adapter.
    Firebase API: https://hacker-news.firebaseio.com/v0/topstories.json
    """

    def __init__(self):
        super().__init__(
            source_name="HackerNewsAI",
            record_type=RecordType.NEWS,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=3.0
        )
        self.top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        self._hn_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
                res = await client.get(self.top_stories_url)
                if res.status_code == 200:
                    story_ids = res.json()[:30]
                    for s_id in story_ids:
                        s_res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{s_id}.json")
                        if s_res.status_code == 200:
                            s_data = s_res.json()
                            url = s_data.get("url") or f"https://news.ycombinator.com/item?id={s_id}"
                            title = s_data.get("title", "")
                            title_lower = title.lower()
                            ai_pattern = r"\b(ai|llm|llms|gpt|gpt-4|gpt-4o|claude|anthropic|openai|deepseek|transformer|neural|machine learning|deep learning)\b"
                            if re.search(ai_pattern, title_lower):
                                pub_time = s_data.get("time")
                                pub_date_iso = None
                                if pub_time:
                                    dt = datetime.fromtimestamp(pub_time, tz=timezone.utc)
                                    pub_date_iso = format_iso8601(dt)
                                self._hn_metadata[url] = {
                                    "title": title,
                                    "pub_date": pub_date_iso
                                }
                                discovered.append(url)
        except Exception as e:
            logger.warning(f"Hacker News discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def extract_published_at(self, raw_payload: RawPayload) -> str | None:
        meta = self._hn_metadata.get(raw_payload.url, {})
        if meta.get("pub_date"):
            return meta["pub_date"]
        raw_date = super().extract_published_at(raw_payload)
        if raw_date:
            dt = parse_date_string(raw_date)
            if dt:
                return format_iso8601(dt)
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        extracted = html_extractor.extract(raw_payload.raw_content, raw_payload.url)
        meta = self._hn_metadata.get(raw_payload.url, {})
        pub_date = self.extract_published_at(raw_payload)

        title = meta.get("title") or extracted.title or "Hacker News AI Story"
        summary = extracted.meta_description or (extracted.main_text[:300] if extracted.main_text else title)
        full_text = extracted.main_text if extracted.main_text and len(extracted.main_text) > 0 else summary

        entities = extract_entities_mentioned(title + " " + summary + " " + full_text)

        return {
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "title": title,
                "summary": summary,
                "full_text": full_text,
                "published_date": pub_date or "",
                "entities_mentioned": entities
            },
            "collectedAt": format_iso8601()
        }
