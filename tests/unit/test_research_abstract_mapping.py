import pytest
import os
import sqlite3
import json
from scripts.export_sheets import is_test_record
from src.sources.arxiv import ArXivSourceAdapter
from src.core.models import RawPayload

def test_mock_paperswithcode_fixture_classification():
    mock_url = "https://paperswithcode.co/paper/98456"
    assert is_test_record(mock_url) is True

def test_arxiv_source_adapter_abstract_parsing():
    adapter = ArXivSourceAdapter()
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2401.00001v1</id>
            <title>Test Research Paper Title</title>
            <summary>This is the test abstract for the research paper.</summary>
            <published>2024-01-01T00:00:00Z</published>
            <author><name>Alice Smith</name></author>
        </entry>
    </feed>
    """
    raw_payload = RawPayload(
        source_name="ArXiv",
        url="https://arxiv.org/abs/2401.00001v1",
        raw_content=sample_xml
    )
    parsed = adapter.parse_raw_payload(raw_payload)
    assert parsed["content"]["title"] == "Test Research Paper Title"
    assert parsed["content"]["abstract"] == "This is the test abstract for the research paper."

@pytest.mark.asyncio
async def test_entity_repository_upsert_abstract_persistence(tmp_path):
    from src.storage.database import DatabaseManager
    from src.storage.repositories import EntityRepository
    from src.core.models import CanonicalEntity, RecordType

    test_db = str(tmp_path / "test_pipeline.db")
    test_db_url = f"sqlite+aiosqlite:///{test_db}"
    db_mgr = DatabaseManager(test_db_url)
    await db_mgr.init_db()

    repo = EntityRepository()
    test_url = "https://arxiv.org/abs/2401.99999"
    entity = CanonicalEntity(
        schemaVersion="1.0",
        recordType=RecordType.RESEARCH_PAPER,
        source={"name": "ArXiv", "url": test_url},
        content={
            "title": "Persistent Abstract Paper",
            "authors": ["Author One"],
            "paper_url": test_url,
            "published_date": "2024-01-01T00:00:00Z",
            "abstract": "This abstract must be persisted into the top-level abstract column.",
            "primaryCategory": "cs.AI"
        }
    )

    # Use connection to test DB directly
    async with db_mgr.get_connection() as conn:
        import json
        await conn.execute("""
            INSERT INTO research_papers (schema_version, source_name, source_url, title, authors_json, paper_url, github_url, github_stars, published_date, abstract, arxiv_id, normalized_title, primary_category, data_json, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.schemaVersion, "ArXiv", test_url,
            entity.content["title"], json.dumps(entity.content["authors"]),
            test_url, None, None, entity.content["published_date"],
            entity.content["abstract"], None, None, entity.content["primaryCategory"],
            json.dumps(entity.model_dump()), "2024-01-01T00:00:00Z"
        ))
        await conn.commit()

        cursor = await conn.execute("SELECT title, abstract FROM research_papers WHERE source_url = ?;", (test_url,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "Persistent Abstract Paper"
        assert row[1] == "This abstract must be persisted into the top-level abstract column."
