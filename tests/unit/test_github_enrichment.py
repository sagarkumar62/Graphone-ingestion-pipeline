import pytest
from src.enrichment.github import github_enricher

def test_missing_github_url_returns_none():
    text_without_github = "This paper introduces Transformer architectures for natural language processing."
    url = github_enricher.extract_github_url(text_without_github)
    assert url is None

def test_github_url_extraction():
    text_with_github = "Official implementation available at https://github.com/google-research/tensor2tensor for training."
    url = github_enricher.extract_github_url(text_with_github)
    assert url == "https://github.com/google-research/tensor2tensor"

@pytest.mark.asyncio
async def test_no_star_fabrication_on_null_repo():
    stars = await github_enricher.fetch_repo_stars(None)
    assert stars is None
