import uuid
import pytest
from src.pipeline.processor import processor
from src.core.models import RecordType, PipelineStatusCode
from src.storage.database import db_manager

@pytest.mark.asyncio
async def test_real_ingestion_and_deduplication():
    # Initialize DB
    await db_manager.init_db()

    real_paper_url = f"https://arxiv.org/abs/1706.03762?test_id={uuid.uuid4()}"
    source_name = "ArXiv"

    # Run 1: First Ingestion -> NEW_RECORD_STORED
    status_1, entity_1, meta_1 = await processor.process_record(
        source_url=real_paper_url,
        source_name=source_name,
        record_type=RecordType.RESEARCH_PAPER,
        use_browser=False
    )

    assert status_1 == PipelineStatusCode.NEW_RECORD_STORED
    assert entity_1 is not None
    assert entity_1.recordType == RecordType.RESEARCH_PAPER
    assert "Attention" in entity_1.content["title"]
    assert len(entity_1.content["authors"]) > 0

    # Run 2: Exact Duplicate URL -> DUPLICATE_ALREADY_PROCESSED
    status_2, entity_2, meta_2 = await processor.process_record(
        source_url=real_paper_url,
        source_name=source_name,
        record_type=RecordType.RESEARCH_PAPER,
        use_browser=False
    )

    assert status_2 == PipelineStatusCode.DUPLICATE_ALREADY_PROCESSED
    assert entity_2 is None
