import json
import pytest
from src.sources.job_sources import ArbeitnowJobSource, RemoteOKAISource, HNWhoIsHiringJobSource
from src.validators.schema_validator import validator
from src.core.models import RecordType, RawPayload

@pytest.mark.asyncio
async def test_job_source_parse_raw_payload():
    adapter = ArbeitnowJobSource()
    url = "https://www.arbeitnow.com/jobs/companies/techcorp/senior-ai-engineer-berlin-12345"
    adapter._job_cache[url] = {
        "title": "Senior AI Engineer",
        "company_name": "TechCorp",
        "created_at": "2026-09-11T12:00:00Z",
        "remote": True,
        "location": "Berlin / Remote",
        "description": "Building next-generation LLM pipelines and autonomous agents."
    }

    raw_payload = RawPayload(
        source_name="Arbeitnow",
        url=url,
        raw_content="{}",
        content_type="application/json",
        fetched_at="2026-09-11T23:00:00Z"
    )

    canonical_dict = adapter.parse_raw_payload(raw_payload)

    assert canonical_dict["schemaVersion"] == "1.0"
    assert canonical_dict["recordType"] == "JOB"
    assert canonical_dict["source"]["name"] == "Arbeitnow"
    assert canonical_dict["source"]["url"] == url
    assert canonical_dict["content"]["jobTitle"] == "Senior AI Engineer"
    assert canonical_dict["content"]["company"] == "TechCorp"
    assert canonical_dict["content"]["is_remote"] is True
    assert canonical_dict["content"]["role_family"] == "AI/ML"
    assert canonical_dict["content"]["location"] == "Berlin / Remote"

    # Schema Validation Check
    is_valid, errors = validator.validate(canonical_dict, RecordType.JOB)
    assert is_valid, f"Schema validation failed: {errors}"
