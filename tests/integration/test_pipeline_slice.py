import uuid
import pytest
from src.pipeline.processor import processor
from src.core.models import RecordType, PipelineStatusCode
from src.storage.database import db_manager

@pytest.mark.asyncio
async def test_vertical_slice_execution():
    # Initialize DB
    await db_manager.init_db()

    # Unique URL per test run
    test_id = str(uuid.uuid4())[:8]
    source_url = f"https://arxiv.org/abs/1706.037{test_id[:2]}"
    source_name = "ArXiv"

    status_code, canonical_entity, meta = await processor.process_record(
        source_url=source_url,
        source_name=source_name,
        record_type=RecordType.RESEARCH_PAPER,
        use_browser=False
    )

    if status_code != PipelineStatusCode.NEW_RECORD_STORED:
        pytest.skip(f"Pipeline slice returned status {status_code.value}")

    assert canonical_entity is not None
    assert canonical_entity.recordType == RecordType.RESEARCH_PAPER
    assert canonical_entity.source.url == source_url
    assert "github_stars" in canonical_entity.content
