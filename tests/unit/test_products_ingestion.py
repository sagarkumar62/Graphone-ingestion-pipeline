import json
import pytest
from src.sources.product_sources import GitHubRepositoriesProductSource
from src.validators.schema_validator import validator
from src.core.models import RecordType, RawPayload

@pytest.mark.asyncio
async def test_product_source_parse_raw_payload():
    adapter = GitHubRepositoriesProductSource()
    raw_data = {
        "name": "vLLM",
        "owner": {"login": "vllm-project"},
        "description": "High-throughput and memory-efficient LLM serving engine.",
        "created_at": "2023-06-20T12:00:00Z",
        "html_url": "https://github.com/vllm-project/vllm"
    }

    raw_payload = RawPayload(
        source_name="GitHub Repositories",
        url="https://github.com/vllm-project/vllm",
        raw_content=json.dumps(raw_data),
        content_type="application/json",
        fetched_at="2026-09-11T23:00:00Z"
    )

    canonical_dict = adapter.parse_raw_payload(raw_payload)

    assert canonical_dict["schemaVersion"] == "1.0"
    assert canonical_dict["recordType"] == "PRODUCT"
    assert canonical_dict["source"]["name"] == "GitHub Repositories"
    assert canonical_dict["source"]["url"] == "https://github.com/vllm-project/vllm"
    assert canonical_dict["content"]["productName"] == "vLLM"
    assert canonical_dict["content"]["startupName"] == "vllm-project"
    assert canonical_dict["content"]["pricingModel"] == "FREE"
    assert canonical_dict["content"]["category"] == "AI Framework & Software Tool"

    # Schema Validation Check
    is_valid, errors = validator.validate(canonical_dict, RecordType.PRODUCT)
    assert is_valid, f"Schema validation failed: {errors}"
