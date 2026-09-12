import json
import re
import httpx
import asyncio
from datetime import datetime
from src.sources.base import BaseSourceAdapter, ExtractionStrategy
from src.core.models import RecordType, RawPayload, CanonicalEntity
from src.core.logging import logger
from src.core.config import settings

class GitHubOrganizationsStartupSource(BaseSourceAdapter):
    """
    Source adapter for fetching public tech and AI startups via the GitHub Organizations API.
    Enforces strict startup defensibility filters (verified company domain, company website,
    legal entity suffixes, or explicit company descriptions) to eliminate non-company Orgs.
    """

    def __init__(self, token: str | None = None):
        super().__init__(
            source_name="GitHub Organizations",
            record_type=RecordType.STARTUP,
            extraction_strategy=ExtractionStrategy.DETERMINISTIC,
            requests_per_second=10.0
        )
        self.token = token or getattr(settings, "GITHUB_TOKEN", None)

    def _get_headers(self) -> dict:
        headers = {
            "User-Agent": "GraphOne-Ingestion-Pipeline/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    @staticmethod
    def is_defensible_startup(org_data: dict, url: str) -> tuple[bool, str]:
        """
        Determines whether an organization record has sufficient source-backed evidence to qualify as a startup/company.
        Uses a strict evidence hierarchy: YC record, GitHub verified company domain, explicit legal entity suffix,
        or commercial website domain combined with an explicit commercial product/company description.
        Rejects academic, foundation, community, and non-profit organizations.
        """
        if not isinstance(org_data, dict):
            org_data = {}

        # Rule 1: YC Directory record
        if "ycombinator.com" in url:
            return True, "YC_DIRECTORY_RECORD"

        name = (org_data.get("name") or "").strip()
        login = (org_data.get("login") or url.strip("/").split("/")[-1] or "").strip()
        blog = (org_data.get("blog") or "").strip()
        desc = (org_data.get("description") or "").strip()
        company_field = (org_data.get("company") or "").strip()
        is_verified = bool(org_data.get("is_verified"))

        combined_text = f"{name} {login} {desc} {company_field} {blog}".strip()

        # Rule 2: Rejection of academic, university, foundation, non-profit, or community entities
        non_startup_pattern = re.compile(
            r'\b(university|univ|college|school|faculty|polytechnic|academia|institute of technology|research group|academic|lab group|foundation|open source community|developer community|personal project|awesome-|curated list|learning resource|non-profit|nonprofit|government|gov|department of|association|society)\b',
            re.IGNORECASE
        )
        if non_startup_pattern.search(combined_text):
            return False, "ACADEMIC_OR_NON_PROFIT"

        # Rule 3: Strong Evidence — Verified GitHub corporate domain
        if is_verified:
            return True, "VERIFIED_COMPANY_DOMAIN"

        # Rule 4: Strong Evidence — Explicit corporate legal entity suffix
        legal_entity_pattern = re.compile(
            r'\b(inc\.?|incorporated|corp\.?|corporation|ltd\.?|limited|gmbh|llc|c-corp|s-corp|pvt\.?\s*ltd\.?|pte\.?\s*ltd\.?|b\.?v\.?|s\.?a\.?|co\.,?\s*ltd\.?|s\.?r\.?o\.?|a/s|ab|oy|gmbh\s*&\s*co|kGaA)\b',
            re.IGNORECASE
        )
        legal_match = legal_entity_pattern.search(name) or legal_entity_pattern.search(company_field)
        if legal_match:
            return True, f"EXPLICIT_LEGAL_ENTITY({legal_match.group(0)})"

        # Rule 5: Moderate Evidence — Legitimate commercial website domain AND explicit company/commercial description
        skip_blogs = ["twitter.com", "x.com", "t.me", "discord.gg", "github.io", "wikipedia.org", "medium.com", "youtube.com"]
        has_valid_blog = bool(
            blog and not any(skip in blog.lower() for skip in skip_blogs) and
            any(ext in blog.lower() for ext in [".com", ".ai", ".io", ".co", ".org", ".net", ".dev", ".app", ".tech", ".de", ".fr", ".uk", ".ca", ".us", ".jp", ".cn", ".in", ".eu", ".sh"])
        )

        commercial_profile_pattern = re.compile(
            r'\b(company|startup|venture-backed|backed by|commercial|enterprise|platform|solution|solutions|service|services|provider|product|products|headquartered|software company|tech company|ai company|cloud platform|saas|developer tool|infrastructure|analytics|security company|data platform|automation|api|agents|build|deploy|scale|open source company|infra|database|storage)\b',
            re.IGNORECASE
        )
        has_commercial_profile = bool(commercial_profile_pattern.search(desc) or commercial_profile_pattern.search(company_field))

        if has_valid_blog and has_commercial_profile:
            return True, "COMMERCIAL_WEBSITE_AND_PROFILE"

        return False, "INSUFFICIENT_COMPANY_EVIDENCE"

    async def discover_urls(self, max_records: int, start_offset: int = 0) -> list[str]:
        """
        Discovers organization usernames via GitHub Search Users API (type:org).
        Pages across multiple query facets to discover tech & company orgs.
        """
        urls = []
        page_size = 100

        queries = [
            "type:org+followers:>50",
            "type:org+repos:>10",
            "type:org+followers:10..50",
            "type:org+repos:5..10",
            "type:org+location:San+Francisco",
            "type:org+location:San+Jose",
            "type:org+location:Palo+Alto",
            "type:org+location:Mountain+View",
            "type:org+location:Sunnyvale",
            "type:org+location:Seattle",
            "type:org+location:New+York",
            "type:org+location:Boston",
            "type:org+location:Austin",
            "type:org+location:Chicago",
            "type:org+location:Los+Angeles",
            "type:org+location:London",
            "type:org+location:Berlin",
            "type:org+location:Paris",
            "type:org+location:Toronto",
            "type:org+location:Vancouver",
            "type:org+location:Tokyo",
            "type:org+location:Singapore",
            "type:org+location:Tel+Aviv",
            "type:org+location:Stockholm",
            "type:org+location:Amsterdam",
            "type:org+topic:artificial-intelligence",
            "type:org+topic:machine-learning",
            "type:org+topic:deep-learning",
            "type:org+topic:llm",
            "type:org+topic:developer-tools",
            "type:org+topic:cloud-native",
            "type:org+topic:database",
            "type:org+created:2020-01-01..2024-12-31",
            "type:org+created:2015-01-01..2019-12-31",
            "type:org+followers:2..9"
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for q in queries:
                if len(urls) >= max_records:
                    break
                for page in range(1, 11):
                    if len(urls) >= max_records:
                        break
                    api_url = f"https://api.github.com/search/users?q={q}&per_page={page_size}&page={page}"
                    try:
                        res = await client.get(api_url, headers=self._get_headers())
                        if res.status_code == 200:
                            items = res.json().get("items", [])
                            if not items:
                                break
                            for item in items:
                                html_url = item.get("html_url")
                                if html_url and html_url not in urls:
                                    urls.append(html_url)
                                    if len(urls) >= max_records:
                                        break
                        elif res.status_code in {403, 429}:
                            logger.warning(f"GitHub Search API rate limited (HTTP {res.status_code}). Pausing brief interval...")
                            await asyncio.sleep(2.0)
                            break
                        else:
                            break
                    except Exception as e:
                        logger.warning(f"Error querying GitHub Search API: {e}")
                        break

        logger.info(f"Discovered {len(urls)} organization URLs total.")
        return urls[start_offset:start_offset + max_records]

    async def fetch_org_data(self, org_login_or_url: str, client: httpx.AsyncClient | None = None) -> dict | None:
        login = org_login_or_url.split('/')[-1]
        api_url = f"https://api.github.com/orgs/{login}"

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            close_client = True

        try:
            res = await client.get(api_url, headers=self._get_headers())
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.warning(f"Failed to fetch details for GitHub org {login}: {e}")
        finally:
            if close_client:
                await client.aclose()
        return None

    def parse_raw_payload(self, raw_payload: RawPayload) -> dict:
        try:
            data = json.loads(raw_payload.raw_content)
        except Exception:
            data = {}

        name = data.get("name") or data.get("login") or raw_payload.url.split("/")[-1]
        website = data.get("blog")
        if website and not str(website).startswith("http"):
            website = f"https://{website}"
        if website and not (str(website).startswith("http://") or str(website).startswith("https://")):
            website = None

        desc = data.get("description")
        if not desc or str(desc).strip() == "":
            desc = f"{name} technology company"

        created_at_str = data.get("created_at")
        founding_year = None
        if created_at_str:
            try:
                founding_year = int(created_at_str[:4])
            except Exception:
                pass

        hq_location = data.get("location")
        if hq_location and str(hq_location).strip() == "":
            hq_location = None

        canonical_dict = {
            "schemaVersion": "1.0",
            "recordType": "STARTUP",
            "source": {
                "name": self.source_name,
                "url": data.get("html_url") or raw_payload.url
            },
            "content": {
                "entityName": str(name).strip(),
                "description": str(desc).strip() if desc else None,
                "website": website,
                "foundingYear": founding_year,
                "hqLocation": str(hq_location).strip() if hq_location else None,
                "data": {
                    "employeeCount": None,
                    "fundingTotalUsd": None,
                    "lastFundingStage": None,
                    "industries": ["Technology", "Software & AI"]
                }
            },
            "collectedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        return canonical_dict
