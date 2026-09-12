import pytest
import json
import sqlite3
import os
from src.sources.startup_sources import GitHubOrganizationsStartupSource
from src.validators.schema_validator import validator
from src.core.models import RecordType, RawPayload, CanonicalEntity

@pytest.mark.asyncio
async def test_startup_source_parse_raw_payload():
    adapter = GitHubOrganizationsStartupSource()
    raw_data = {
        "login": "testai",
        "name": "Test AI Inc.",
        "blog": "https://testai.example.com",
        "description": "Building cutting-edge AI models.",
        "created_at": "2022-05-10T12:00:00Z",
        "location": "San Francisco, CA",
        "html_url": "https://github.com/testai"
    }

    raw_payload = RawPayload(
        source_name="GitHub Organizations",
        url="https://github.com/testai",
        raw_content=json.dumps(raw_data),
        content_type="application/json",
        fetched_at="2026-09-11T23:00:00Z"
    )

    canonical_dict = adapter.parse_raw_payload(raw_payload)

    assert canonical_dict["schemaVersion"] == "1.0"
    assert canonical_dict["recordType"] == "STARTUP"
    assert canonical_dict["source"]["name"] == "GitHub Organizations"
    assert canonical_dict["source"]["url"] == "https://github.com/testai"
    assert canonical_dict["content"]["entityName"] == "Test AI Inc."
    assert canonical_dict["content"]["website"] == "https://testai.example.com"
    assert canonical_dict["content"]["foundingYear"] == 2022
    assert canonical_dict["content"]["hqLocation"] == "San Francisco, CA"

    # Schema Validation Check
    is_valid, errors = validator.validate(canonical_dict, RecordType.STARTUP)
    assert is_valid, f"Schema validation failed: {errors}"

def test_yc_company_accepted():
    """1. YC company records are accepted when legitimate."""
    adapter = GitHubOrganizationsStartupSource()
    is_defensible, reason = adapter.is_defensible_startup({}, "https://ycombinator.com/companies/openai")
    assert is_defensible is True
    assert reason == "YC_DIRECTORY_RECORD"

def test_yc_record_identity_consistency():
    """2. YC record identity/source URL is consistent."""
    if os.path.exists("pipeline.db"):
        con = sqlite3.connect("pipeline.db")
        cur = con.cursor()
        yc_rows = cur.execute("SELECT source_url, entity_name FROM startups WHERE source_name = 'YC Directory'").fetchall()
        con.close()
        assert len(yc_rows) == 1
        assert yc_rows[0][0] == "https://ycombinator.com/companies/openai"
        assert yc_rows[0][1] == "OpenAI"

def test_github_org_strong_evidence_accepted():
    """3. GitHub organization with strong company evidence (verified domain or legal entity suffix) is accepted."""
    adapter = GitHubOrganizationsStartupSource()

    # Verified domain
    verified_org = {"name": "Acme", "is_verified": True}
    is_def, reason = adapter.is_defensible_startup(verified_org, "https://github.com/acme")
    assert is_def is True
    assert reason == "VERIFIED_COMPANY_DOMAIN"

    # Legal entity suffix
    legal_org = {"name": "Acme Inc.", "company": "Acme Corporation"}
    is_def, reason = adapter.is_defensible_startup(legal_org, "https://github.com/acme")
    assert is_def is True
    assert "EXPLICIT_LEGAL_ENTITY" in reason

def test_github_org_keyword_alone_rejected():
    """4. GitHub organization with only 'AI'/'Labs'/'Software' style keywords is NOT automatically accepted."""
    adapter = GitHubOrganizationsStartupSource()
    keyword_org = {"name": "AI Software Labs Studio", "description": "AI software tools"}
    is_def, reason = adapter.is_defensible_startup(keyword_org, "https://github.com/ailabs")
    assert is_def is False
    assert reason == "INSUFFICIENT_COMPANY_EVIDENCE"

def test_academic_research_community_rejected():
    """5. Academic/research/community organizations are rejected when evidence does not establish a company."""
    adapter = GitHubOrganizationsStartupSource()
    academic_org = {
        "name": "MIT Computer Science Lab",
        "description": "University research lab group at MIT",
        "blog": "https://csail.mit.edu"
    }
    is_def, reason = adapter.is_defensible_startup(academic_org, "https://github.com/mit-csail")
    assert is_def is False
    assert reason == "ACADEMIC_OR_NON_PROFIT"

def test_missing_weak_evidence_rejection_reason():
    """6. Missing/weak company evidence produces INSUFFICIENT_COMPANY_EVIDENCE."""
    adapter = GitHubOrganizationsStartupSource()
    weak_org = {"name": "random-project", "description": "Just an open source repo"}
    is_def, reason = adapter.is_defensible_startup(weak_org, "https://github.com/random-project")
    assert is_def is False
    assert reason == "INSUFFICIENT_COMPANY_EVIDENCE"

def test_source_urls_legitimate_non_empty():
    """7. Source URLs remain legitimate and non-empty."""
    if os.path.exists("pipeline.db"):
        con = sqlite3.connect("pipeline.db")
        cur = con.cursor()
        rows = cur.execute("SELECT source_url FROM startups").fetchall()
        con.close()
        for r in rows:
            url = r[0]
            assert url is not None and len(url) > 0
            assert url.startswith("http://") or url.startswith("https://")

def test_determinism_and_no_duplicates():
    """8, 9, 10. Repeated ingestion determinism, no duplicate source URLs, and reproducible startup count."""
    if os.path.exists("pipeline.db"):
        con = sqlite3.connect("pipeline.db")
        cur = con.cursor()
        urls = [r[0] for r in cur.execute("SELECT source_url FROM startups").fetchall()]
        con.close()
        assert len(urls) == len(set(urls)), "Duplicate source URLs found in startups table"
        assert len(urls) >= 1000, f"Expected defensible startup count >= 1000, got {len(urls)}"
        assert len(urls) == 1134, f"Expected reproducible startup count of 1134, got {len(urls)}"
