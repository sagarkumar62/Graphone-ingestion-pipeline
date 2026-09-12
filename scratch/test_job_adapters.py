import re
import httpx
from xml.etree import ElementTree as ET
from src.sources.base import BaseSourceAdapter, ExtractionStrategy
from src.core.models import RecordType, RawPayload
from src.crawlers.extractor import html_extractor
from src.utils.time import parse_date_string, format_iso8601, get_utc_now
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
        except Exception as e:
            logger.warning(f"RemoteOK discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("position") or "Software Engineer"
        company = job.get("company") or "Remote OK Client"
        raw_date = job.get("date") or raw_payload.fetched_at
        parsed_dt = parse_date_string(str(raw_date)) or get_utc_now()
        date_iso = format_iso8601(parsed_dt)
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
        max_pages = min(10, (max_records // 25) + 2)
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
                    page += 1
        except Exception as e:
            logger.warning(f"Arbeitnow discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("title") or "Software Engineer"
        company = job.get("company_name") or "Arbeitnow Employer"
        raw_date = job.get("created_at") or raw_payload.fetched_at
        parsed_dt = parse_date_string(str(raw_date)) or get_utc_now()
        date_iso = format_iso8601(parsed_dt)
        is_remote = bool(job.get("remote", False))
        location = job.get("location") or ("Remote" if is_remote else "Germany / Europe")
        desc = job.get("description") or title

        # Strip HTML tags from description
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
        except Exception as e:
            logger.warning(f"Jobicy discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        job = self._job_cache.get(raw_payload.url, {})
        title = job.get("jobTitle") or "Remote Specialist"
        company = job.get("companyName") or "Jobicy Employer"
        raw_date = job.get("pubDate") or raw_payload.fetched_at
        parsed_dt = parse_date_string(str(raw_date)) or get_utc_now()
        date_iso = format_iso8601(parsed_dt)
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
                # 1. Fetch top WhoIsHiring stories
                res = await client.get("https://hn.algolia.com/api/v1/search?tags=author_whoishiring&hitsPerPage=4")
                if res.status_code == 200:
                    stories = res.json().get("hits", [])
                    for story in stories:
                        story_id = story.get("objectID")
                        if not story_id:
                            continue
                        # Fetch comments for this story across pages
                        for page in range(2):
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
                            if len(discovered) >= max_records + start_offset:
                                break
        except Exception as e:
            logger.warning(f"HNWhoIsHiring discovery error: {e}")

        return discovered[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        c = self._job_cache.get(raw_payload.url, {})
        text = c.get("comment_text") or ""
        clean_text = re.sub(r'<[^>]+>', ' ', text).strip()

        # HN WhoIsHiring format is typically: Company Name | Job Title | Location | Remote/ONSITE | Salary | ...
        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        first_line = lines[0] if lines else "HN Startup"
        parts = [p.strip() for p in first_line.split("|")]

        company = parts[0] if len(parts) > 0 and len(parts[0]) <= 50 else "HN Startup"
        title = parts[1] if len(parts) > 1 and len(parts[1]) <= 80 else "Software Engineer"
        location = parts[2] if len(parts) > 2 and len(parts[2]) <= 80 else "Remote / Onsite"

        is_remote = "remote" in clean_text.lower()
        created_at = c.get("created_at") or raw_payload.fetched_at
        parsed_dt = parse_date_string(str(created_at)) or get_utc_now()
        date_iso = format_iso8601(parsed_dt)

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

        pub_date = meta.get("pub_date") or raw_payload.fetched_at
        parsed_dt = parse_date_string(str(pub_date)) or get_utc_now()
        date_iso = format_iso8601(parsed_dt)
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

class GitHubTechJobsSource(BaseSourceAdapter):
    """GitHub Tech Job Listings Repository Adapter (pittcsc)."""

    def __init__(self):
        super().__init__(
            source_name="GitHubTechJobs",
            record_type=RecordType.JOB,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=2.0
        )
        self.raw_url = "https://raw.githubusercontent.com/pittcsc/Summer2025-Internships/master/README.md"
        self._job_cache: dict[str, dict] = {}

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        discovered = []
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get(self.raw_url)
                if res.status_code == 200:
                    # Parse markdown table lines: | Company | Role | Location | Application Link | Age |
                    lines = res.text.split("\n")
                    for line in lines:
                        if "|" in line and "http" in line and not line.startswith("| Name"):
                            cols = [c.strip() for c in line.split("|")]
                            if len(cols) >= 5:
                                company_col = cols[1]
                                role_col = cols[2]
                                loc_col = cols[3]
                                app_col = cols[4]

                                # Clean markdown link: [Company](url)
                                comp_match = re.search(r'\[([^\]]+)\]', company_col)
                                company = comp_match.group(1) if comp_match else re.sub(r'[\*\_]', '', company_col).strip()

                                # Clean application URL
                                url_match = re.search(r'href="([^"]+)"', app_col) or re.search(r'\((https?://[^\)]+)\)', app_col)
                                url = url_match.group(1) if url_match else None

                                if company and url and url.startswith("http"):
                                    role = re.sub(r'[\*\_]', '', role_col).strip() or "Software Engineer Intern"
                                    loc = re.sub(r'<[^>]+>', ' ', loc_col).strip() or "United States / Remote"

                                    item = {
                                        "company": company,
                                        "role": role,
                                        "location": loc,
                                        "url": url
                                    }
                                    self._job_cache[url] = item
                                    discovered.append(url)
        except Exception as e:
            logger.warning(f"GitHubTechJobs discovery error: {e}")

        # Deduplicate discovered URLs while preserving order
        unique_urls = list(dict.fromkeys(discovered))
        return unique_urls[start_offset:start_offset + max_records]

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        item = self._job_cache.get(raw_payload.url, {})
        company = item.get("company") or "Tech Company"
        title = item.get("role") or "Software Engineering Position"
        location = item.get("location") or "Remote / Onsite"
        is_remote = "remote" in location.lower() or "worldwide" in location.lower()
        date_iso = format_iso8601()

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
                "role_family": _determine_role_family(title, location),
                "location": location,
                "descriptionSnippet": f"{title} at {company} ({location})"
            },
            "collectedAt": format_iso8601()
        }

# Legacy aliases for backward compatibility
AIJobsNetSource = RemoteOKAISource
YCWorkAtAStartupSource = ArbeitnowJobSource
CryptoJobsAISource = JobicyAISource
