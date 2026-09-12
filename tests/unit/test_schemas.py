from src.validators.schema_validator import validator
from src.core.models import RecordType
from src.utils.time import format_iso8601

def test_startup_schema_valid():
    payload = {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",
        "source": {"name": "YC Directory", "url": "https://ycombinator.com/companies/openai"},
        "content": {
            "entityName": "OpenAI",
            "description": "AI research company",
            "website": "https://openai.com",
            "foundingYear": 2015,
            "hqLocation": "San Francisco, CA",
            "data": {
                "employeeCount": 1200,
                "fundingTotalUsd": 11000000000.0,
                "lastFundingStage": "Series B",
                "industries": ["AI"]
            }
        },
        "collectedAt": format_iso8601()
    }
    is_valid, errors = validator.validate(payload, RecordType.STARTUP)
    assert is_valid, f"Validation failed: {errors}"

def test_startup_schema_invalid_employee_count():
    payload = {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",
        "source": {"name": "YC Directory", "url": "https://ycombinator.com/companies/openai"},
        "content": {
            "entityName": "OpenAI",
            "data": {
                "employeeCount": "invalid_string_instead_of_int"
            }
        },
        "collectedAt": format_iso8601()
    }
    is_valid, errors = validator.validate(payload, RecordType.STARTUP)
    assert not is_valid
    assert len(errors) > 0
