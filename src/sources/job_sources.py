import re
import httpx
from xml.etree import ElementTree as ET
from src.sources.base import BaseSourceAdapter, ExtractionStrategy
from src.core.models import RecordType, RawPayload
from src.crawlers.extractor import html_extractor
from src.utils.time import parse_date_string, format_iso8601
from src.core.logging import logger

def _determine_role_family(title: str, description: str = "") -> str:
    combined = (title + " " + description).lower()
    if any(k in combined for k in ["data science", "data scientist", "data analyst", "analytics"]):
        return "Data Science"
    if any(k in combined for k in ["machine learning", "ml engineer", "ai engineer", "deep learning", "nlp", "cv", "computer vision", "ai/ml", "research scientist"]):
        return "AI/ML"
    if any(k in combined for k in ["product manager", "product owner", "product lead"]):
        return "Product"
    if any(k in combined for k in ["designer", "ui/ux", "ux designer", "product design"]):
        return "Design"
    if any(k in combined for k in ["engineering manager", "cto", "vp engineering", "lead engineer"]):
        return "Management"
    return "Engineering"

class RemoteOKAISource(BaseSourceAdapter):
    """RemoteOK Job API Adapter."""

    def __init__(self):
        super().__init__(
            source_name="RemoteOKAI",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.api_url = "https://remoteok.com/api"
        self._job_cache: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                res = await client.get(self.api_url)
                if res.status_code == 200:
                    jobs = res.json()
                    if isinstance(jobs, list):
                        for job in jobs[1:]:  # skip notice header
                            if isinstance(job, dict):
                                url = job.get("url") or f"https://remoteok.com/remote-jobs/{job.get('id')}"
                                self._job_cache[url] = job
                                discovered.append(url)
                                if len(discovered) >= max_records + start_offset:
                                    break
        except Exception as e:
            logger.warning(f"RemoteOK discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("position") or "Software Engineer"
        company = job.get("company") or "Remote OK Client"
        raw_date = job.get("date")
        parsed_dt = parse_date_string(str(raw_date)) if raw_date else None
        date_iso = format_iso8601(parsed_dt) if parsed_dt else None
        location = job.get("location") or "Worldwide Remote"
        desc = job.get("description") or title

        return {
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "jobTitle": title,
                "company": company,
                "date": date_iso,
                "is_remote": True,
                "role_family": _determine_role_family(title, desc),
                "location": location,
                "descriptionSnippet": desc[:500] if desc else None
            },
            "collectedAt": format_iso8601()
        }

class ArbeitnowJobSource(BaseSourceAdapter):
    """Arbeitnow Public Job API Adapter."""

    def __init__(self):
        super().__init__(
            source_name="Arbeitnow",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.api_url = "https://www.arbeitnow.com/api/job-board-api"
        self._job_cache: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        page = 1
        max_pages = min(40, (max_records // 25) + 2)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                while len(discovered) < max_records and page <= max_pages:
                    res = await client.get(f"{self.api_url}?page={page}")
                    if res.status_code != 200:
                        break
                    data = res.json().get("data", [])
                    if not data:
                        break
                    for job in data:
                        url = job.get("url") or f"https://www.arbeitnow.com/view/{job.get('slug')}"
                        self._job_cache[url] = job
                        discovered.append(url)
                        if len(discovered) >= max_records + start_offset:
                            break
                    page += 1
        except Exception as e:
            logger.warning(f"Arbeitnow discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("title") or "Software Engineer"
        company = job.get("company_name") or "Arbeitnow Employer"
        raw_date = job.get("created_at")
        parsed_dt = parse_date_string(str(raw_date)) if raw_date else None
        date_iso = format_iso8601(parsed_dt) if parsed_dt else None
        is_remote = bool(job.get("remote", False))
        location = job.get("location") or ("Remote" if is_remote else "Europe")
        desc = job.get("description") or title

        clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else None

        return {
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "jobTitle": title,
                "company": company,
                "date": date_iso,
                "is_remote": is_remote,
                "role_family": _determine_role_family(title, clean_desc or ""),
                "location": location,
                "descriptionSnippet": clean_desc[:500] if clean_desc else None
            },
            "collectedAt": format_iso8601()
        }

class JobicyAISource(BaseSourceAdapter):
    """Jobicy Remote Job API Adapter."""

    def __init__(self):
        super().__init__(
            source_name="Jobicy",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.api_url = "https://jobicy.com/api/v2/remote-jobs?count=100"
        self._job_cache: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get(self.api_url)
                if res.status_code == 200:
                    jobs = res.json().get("jobs", [])
                    for job in jobs:
                        url = job.get("url") or f"https://jobicy.com/jobs/{job.get('id')}"
                        self._job_cache[url] = job
                        discovered.append(url)
                        if len(discovered) >= max_records + start_offset:
                            break
        except Exception as e:
            logger.warning(f"Jobicy discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("jobTitle") or "Remote Specialist"
        company = job.get("companyName") or "Jobicy Employer"
        raw_date = job.get("pubDate")
        parsed_dt = parse_date_string(str(raw_date)) if raw_date else None
        date_iso = format_iso8601(parsed_dt) if parsed_dt else None
        location = job.get("jobGeo") or "Remote"
        desc = job.get("jobDescription") or title
        clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else None

        return {
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "jobTitle": title,
                "company": company,
                "date": date_iso,
                "is_remote": True,
                "role_family": _determine_role_family(title, clean_desc or ""),
                "location": location,
                "descriptionSnippet": clean_desc[:500] if clean_desc else None
            },
            "collectedAt": format_iso8601()
        }

class HNWhoIsHiringJobSource(BaseSourceAdapter):
    """HackerNews 'Who is Hiring?' Algolia API Adapter."""

    def __init__(self):
        super().__init__(
            source_name="HNWhoIsHiring",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self._job_cache: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get("https://hn.algolia.com/api/v1/search?tags=author_whoishiring&hitsPerPage=4")
                if res.status_code == 200:
                    stories = res.json().get("hits", [])
                    for story in stories:
                        if len(discovered) >= max_records + start_offset:
                            break
                        story_id = story.get("objectID")
                        if not story_id:
                            continue
                        for page in range(3):
                            if len(discovered) >= max_records + start_offset:
                                break
                            r_comments = await client.get(f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=500&page={page}")
                            if r_comments.status_code == 200:
                                comments = r_comments.json().get("hits", [])
                                if not comments:
                                    break
                                for c in comments:
                                    text = c.get("comment_text") or ""
                                    if len(text) < 30:
                                        continue
                                    url = f"https://news.ycombinator.com/item?id={c.get('objectID')}"
                                    self._job_cache[url] = c
                                    discovered.append(url)
                                    if len(discovered) >= max_records + start_offset:
                                        break
        except Exception as e:
            logger.warning(f"HNWhoIsHiring discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        c = self._job_cache.get(raw_payload.url, {})
        text = c.get("comment_text") or ""
        clean_text = re.sub(r'<[^>]+>', ' ', text).strip()

        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        first_line = lines[0] if lines else "HN Tech Company"
        parts = [p.strip() for p in first_line.split("|")]

        company = parts[0] if len(parts) > 0 and len(parts[0]) <= 50 else "HN Tech Company"
        title = parts[1] if len(parts) > 1 and len(parts[1]) <= 80 else "Software Engineer"
        location = parts[2] if len(parts) > 2 and len(parts[2]) <= 80 else "Remote / Onsite"

        is_remote = "remote" in clean_text.lower()
        created_at = c.get("created_at")
        parsed_dt = parse_date_string(str(created_at)) if created_at else None
        date_iso = format_iso8601(parsed_dt) if parsed_dt else None

        return {
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "jobTitle": title,
                "company": company,
                "date": date_iso,
                "is_remote": is_remote,
                "role_family": _determine_role_family(title, clean_text),
                "location": location,
                "descriptionSnippet": clean_text[:500] if clean_text else None
            },
            "collectedAt": format_iso8601()
        }

class WeWorkRemotelyAISource(BaseSourceAdapter):
    """WeWorkRemotely RSS Adapter."""

    def __init__(self):
        super().__init__(
            source_name="WeWorkRemotelyAI",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=1.5
        )
        self.feed_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        self._rss_metadata: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            ) as client:
                res = await client.get(self.feed_url)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    for item in root.findall(".//item"):
                        link = item.find("link")
                        pub_date = item.find("pubDate")
                        title = item.find("title")
                        description = item.find("description")
                        url = link.text.strip() if link is not None and link.text else None
                        if url:
                            self._rss_metadata[url] = {
                                "title": title.text.strip() if title is not None and title.text else None,
                                "pub_date": pub_date.text.strip() if pub_date is not None and pub_date.text else None,
                                "description": description.text.strip() if description is not None and description.text else None,
                            }
                            discovered.append(url)
                            if len(discovered) >= max_records + start_offset:
                                break
        except Exception as e:
            logger.warning(f"WeWorkRemotely RSS discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        meta = self._rss_metadata.get(raw_payload.url, {})
        title_str = meta.get("title") or "WeWorkRemotely Position"
        company = "WeWorkRemotely Client"
        if ":" in title_str:
            parts = title_str.split(":", 1)
            company = parts[0].strip()
            title_str = parts[1].strip()

        pub_date = meta.get("pub_date")
        parsed_dt = parse_date_string(str(pub_date)) if pub_date else None
        date_iso = format_iso8601(parsed_dt) if parsed_dt else None
        desc = meta.get("description") or ""
        clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else None

        return {
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {
                "name": self.source_name,
                "url": raw_payload.url
            },
            "content": {
                "jobTitle": title_str,
                "company": company,
                "date": date_iso,
                "is_remote": True,
                "role_family": _determine_role_family(title_str, clean_desc or ""),
                "location": "Worldwide Remote",
                "descriptionSnippet": clean_desc[:500] if clean_desc else None
            },
            "collectedAt": format_iso8601()
        }

# Aliases for backward compatibility
AIJobsNetSource = RemoteOKAISource
YCWorkAtAStartupSource = ArbeitnowJobSource
CryptoJobsAISource = JobicyAISource
