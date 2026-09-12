import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.enrichment.github import GitHubEnricher, EnrichmentStatus

@pytest.mark.asyncio
async def test_github_enrichment_no_data():
    enricher = GitHubEnricher()
    res = await enricher.fetch_repo_details(None)
    assert res.status == EnrichmentStatus.NO_DATA
    assert res.stars is None

@pytest.mark.asyncio
async def test_github_enrichment_success():
    enricher = GitHubEnricher()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"stargazers_count": 1250}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client
        res = await enricher.fetch_repo_details("https://github.com/huggingface/transformers")
        assert res.status == EnrichmentStatus.COMPLETED
        assert res.stars == 1250

@pytest.mark.asyncio
async def test_github_enrichment_404():
    enricher = GitHubEnricher()
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client
        res = await enricher.fetch_repo_details("https://github.com/nonexistent/repo123")
        assert res.status == EnrichmentStatus.PERMANENT_FAILURE
        assert res.stars is None

@pytest.mark.asyncio
async def test_github_enrichment_rate_limit():
    enricher = GitHubEnricher()
    mock_response = MagicMock()
    mock_response.status_code = 403

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client
        res = await enricher.fetch_repo_details("https://github.com/owner/repo")
        assert res.status == EnrichmentStatus.RETRYABLE_FAILURE
        assert res.stars is None
