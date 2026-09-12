import re
import httpx
from enum import Enum
from pydantic import BaseModel
from src.core.config import settings
from src.core.logging import logger
from src.utils.normalization import normalize_github_url

class EnrichmentStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_DATA = "NO_DATA"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"

class GitHubEnrichmentResult(BaseModel):
    github_url: str | None = None
    stars: int | None = None
    status: EnrichmentStatus
    error_message: str | None = None

class GitHubEnricher:
    """
    Enriches research paper records by parsing GitHub repository URLs
    and fetching current star counts via the GitHub REST API without hallucination.
    Handles rate limits, 404s, retries, and strict state transitions.
    """

    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN

    def extract_github_url(self, text: str | None) -> str | None:
        """Parses the first legitimate GitHub repository URL from paper text/HTML."""
        if not text:
            return None
        return normalize_github_url(text)

    async def fetch_repo_details(self, github_url: str | None) -> GitHubEnrichmentResult:
        """
        Queries GitHub API to fetch live star count and status for a repository URL.
        Returns GitHubEnrichmentResult with explicit status.
        """
        if not github_url or str(github_url).strip() == "":
            return GitHubEnrichmentResult(status=EnrichmentStatus.NO_DATA)

        norm_url = normalize_github_url(github_url)
        if not norm_url:
            return GitHubEnrichmentResult(
                github_url=github_url,
                status=EnrichmentStatus.PERMANENT_FAILURE,
                error_message="Invalid repository URL structure"
            )

        match = re.search(r'github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)', norm_url)
        if not match:
            return GitHubEnrichmentResult(
                github_url=norm_url,
                status=EnrichmentStatus.PERMANENT_FAILURE,
                error_message="Could not parse owner/repo from URL"
            )

        owner, repo = match.group(1), match.group(2)
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        headers = {
            "User-Agent": "GraphOne-Ingestion-Pipeline/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(api_url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    stars = data.get("stargazers_count")
                    logger.info(f"Fetched live GitHub stars: {stars}", extra={"repo": f"{owner}/{repo}"})
                    return GitHubEnrichmentResult(
                        github_url=norm_url,
                        stars=stars,
                        status=EnrichmentStatus.COMPLETED
                    )
                elif res.status_code == 404:
                    logger.warning(f"GitHub repository not found (404): {owner}/{repo}")
                    return GitHubEnrichmentResult(
                        github_url=norm_url,
                        status=EnrichmentStatus.PERMANENT_FAILURE,
                        error_message="Repository 404 Not Found"
                    )
                elif res.status_code in {403, 429}:
                    logger.warning(f"GitHub API rate limited ({res.status_code}) for {owner}/{repo}")
                    return GitHubEnrichmentResult(
                        github_url=norm_url,
                        status=EnrichmentStatus.RETRYABLE_FAILURE,
                        error_message=f"Rate limited HTTP {res.status_code}"
                    )
                elif res.status_code >= 500:
                    logger.warning(f"GitHub API server error ({res.status_code}) for {owner}/{repo}")
                    return GitHubEnrichmentResult(
                        github_url=norm_url,
                        status=EnrichmentStatus.RETRYABLE_FAILURE,
                        error_message=f"Server error HTTP {res.status_code}"
                    )
                else:
                    return GitHubEnrichmentResult(
                        github_url=norm_url,
                        status=EnrichmentStatus.PERMANENT_FAILURE,
                        error_message=f"Unexpected status code HTTP {res.status_code}"
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch GitHub stars for {norm_url}: {e}")
            return GitHubEnrichmentResult(
                github_url=norm_url,
                status=EnrichmentStatus.RETRYABLE_FAILURE,
                error_message=str(e)
            )

    async def fetch_repo_stars(self, github_url: str | None) -> int | None:
        """Backward compatible helper returning star count or None."""
        res = await self.fetch_repo_details(github_url)
        return res.stars

github_enricher = GitHubEnricher()
