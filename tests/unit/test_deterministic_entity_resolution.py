import pytest
import asyncio
import pytest_asyncio
from src.resolver.matcher import DeterministicEntityResolver, ResolutionResult
from src.resolver.normalizer import normalizer
from src.resolver.seed import CANONICAL_SEED_RECORDS, generate_seed_entity_id
from src.core.models import ResolutionDecision, CanonicalEntityRecord
from src.storage.database import db_manager
from src.storage.repositories import CanonicalEntityRepository

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await db_manager.init_db()

@pytest.fixture
def custom_resolver():
    return DeterministicEntityResolver()

# -----------------------------------------------------------------------------
# 1. Pure Name-Normalization Tests (No domain or external ID)
# -----------------------------------------------------------------------------

def test_pure_name_normalization_without_domain_or_external_id(custom_resolver):
    openai_rec = next(r for r in CANONICAL_SEED_RECORDS if r.canonical_name == "OpenAI")
    
    # Test "OpenAI Inc." with no domain / external ID
    res1 = custom_resolver.resolve("OpenAI Inc.", entity_type="STARTUP", domain=None, external_ids=None)
    assert res1.canonical_entity_id == openai_rec.canonical_entity_id
    assert res1.canonical_value == "OpenAI"
    assert res1.decision in {ResolutionDecision.EXACT_NAME_MATCH.value, ResolutionDecision.ALIAS_MATCH.value}
    assert res1.confidence == 1.0

    # Test "Open AI" with no domain / external ID
    res2 = custom_resolver.resolve("Open AI", entity_type="STARTUP", domain=None, external_ids=None)
    assert res2.canonical_entity_id == openai_rec.canonical_entity_id
    assert res2.canonical_value == "OpenAI"
    assert res2.decision == ResolutionDecision.ALIAS_MATCH.value
    assert res2.confidence == 1.0

    # Test "OpenAI, Inc." with no domain / external ID
    res3 = custom_resolver.resolve("OpenAI, Inc.", entity_type="STARTUP", domain=None, external_ids=None)
    assert res3.canonical_entity_id == openai_rec.canonical_entity_id
    assert res3.canonical_value == "OpenAI"
    assert res3.decision in {ResolutionDecision.EXACT_NAME_MATCH.value, ResolutionDecision.ALIAS_MATCH.value}
    assert res3.confidence == 1.0

# -----------------------------------------------------------------------------
# 2. Positive Multi-Tier Matching Tests
# -----------------------------------------------------------------------------

def test_exact_name_match(custom_resolver):
    res = custom_resolver.resolve("OpenAI", entity_type="STARTUP")
    assert res.canonical_value == "OpenAI"
    assert res.decision == ResolutionDecision.EXACT_NAME_MATCH.value
    assert res.confidence == 1.0

def test_alias_match_space_variant(custom_resolver):
    res = custom_resolver.resolve("Open AI", entity_type="STARTUP")
    assert res.canonical_value == "OpenAI"
    assert res.decision == ResolutionDecision.ALIAS_MATCH.value
    assert res.confidence == 1.0

def test_canonical_domain_match(custom_resolver):
    res = custom_resolver.resolve("random string", domain="https://openai.com/about?src=1")
    assert res.canonical_value == "OpenAI"
    assert res.decision == ResolutionDecision.DOMAIN_MATCH.value
    assert res.confidence == 1.0

def test_exact_external_id_match(custom_resolver):
    res = custom_resolver.resolve(
        raw_name="Some Entity",
        external_ids={"crunchbase": "openai"}
    )
    assert res.canonical_value == "OpenAI"
    assert res.decision == ResolutionDecision.EXACT_EXTERNAL_ID_MATCH.value
    assert res.confidence == 1.0

def test_anthropic_alias_match(custom_resolver):
    res = custom_resolver.resolve("Anthropic PBC", entity_type="STARTUP")
    assert res.canonical_value == "Anthropic"
    assert res.decision in {ResolutionDecision.EXACT_NAME_MATCH.value, ResolutionDecision.ALIAS_MATCH.value}

# -----------------------------------------------------------------------------
# 3. False-Merge Protection (Negative Safeguard Tests)
# -----------------------------------------------------------------------------

def test_negative_openai_labs_no_merge(custom_resolver):
    res = custom_resolver.resolve("OpenAI Labs", entity_type="STARTUP")
    assert res.canonical_value != "OpenAI"
    assert res.decision == ResolutionDecision.CREATE_NEW_CANONICAL.value
    assert res.evidence["existing_match_found"] is False

def test_negative_apple_records_no_merge(custom_resolver):
    res = custom_resolver.resolve("Apple Records", entity_type="STARTUP")
    assert res.canonical_value != "Apple"
    assert res.decision == ResolutionDecision.CREATE_NEW_CANONICAL.value
    assert res.evidence["existing_match_found"] is False

def test_negative_amazon_web_services_no_merge(custom_resolver):
    res = custom_resolver.resolve("Amazon Web Services", entity_type="STARTUP")
    assert res.canonical_value != "Amazon"
    assert res.decision == ResolutionDecision.CREATE_NEW_CANONICAL.value
    assert res.evidence["existing_match_found"] is False

def test_unrelated_similar_name_no_merge(custom_resolver):
    res = custom_resolver.resolve("OpenAI Capital Partners", entity_type="STARTUP")
    assert res.canonical_value != "OpenAI"
    assert res.decision == ResolutionDecision.CREATE_NEW_CANONICAL.value
    assert res.evidence["existing_match_found"] is False

# -----------------------------------------------------------------------------
# 4. Explicit Distinction: Matching vs New Entity Creation
# -----------------------------------------------------------------------------

def test_new_entity_creation_is_explicitly_distinguishable(custom_resolver):
    res_match = custom_resolver.resolve("OpenAI Inc.")
    res_new = custom_resolver.resolve("OpenAI Labs")

    # Match explicitly reports matching decision
    assert res_match.decision in {ResolutionDecision.EXACT_NAME_MATCH.value, ResolutionDecision.ALIAS_MATCH.value}
    assert res_match.confidence == 1.0

    # New entity explicitly reports CREATE_NEW_CANONICAL decision
    assert res_new.decision == ResolutionDecision.CREATE_NEW_CANONICAL.value
    assert res_new.match_method == "CREATE_NEW_CANONICAL_ENTITY"
    assert res_new.evidence["created_new_canonical"] is True
    assert res_new.evidence["existing_match_found"] is False

# -----------------------------------------------------------------------------
# 5. Resolver Invariant Tests
# -----------------------------------------------------------------------------

def test_invariant_same_normalized_name_yields_stable_id(custom_resolver):
    res1 = custom_resolver.resolve("OpenAI", entity_type="STARTUP")
    res2 = custom_resolver.resolve("  openai  ", entity_type="STARTUP")
    assert res1.canonical_entity_id == res2.canonical_entity_id

def test_invariant_same_alias_yields_stable_id(custom_resolver):
    res1 = custom_resolver.resolve("Open AI", entity_type="STARTUP")
    res2 = custom_resolver.resolve("Open AI Inc.", entity_type="STARTUP")
    assert res1.canonical_entity_id == res2.canonical_entity_id

def test_invariant_same_domain_yields_stable_id(custom_resolver):
    res1 = custom_resolver.resolve("Any Name 1", domain="https://openai.com/a")
    res2 = custom_resolver.resolve("Any Name 2", domain="https://www.openai.com/b")
    assert res1.canonical_entity_id == res2.canonical_entity_id

def test_invariant_same_external_id_yields_stable_id(custom_resolver):
    res1 = custom_resolver.resolve("Entity 1", external_ids={"crunchbase": "openai"})
    res2 = custom_resolver.resolve("Entity 2", external_ids={"crunchbase": "openai"})
    assert res1.canonical_entity_id == res2.canonical_entity_id

def test_invariant_empty_input_returns_no_match(custom_resolver):
    res = custom_resolver.resolve("")
    assert res.decision == ResolutionDecision.NO_MATCH.value
    assert res.canonical_entity_id is None
    assert res.confidence == 0.0

# -----------------------------------------------------------------------------
# 6. Idempotency & Concurrency Tests
# -----------------------------------------------------------------------------

def test_resolution_idempotency(custom_resolver):
    res1 = custom_resolver.resolve("Open AI Inc.", entity_type="STARTUP")
    res2 = custom_resolver.resolve("Open AI Inc.", entity_type="STARTUP")
    assert res1.canonical_entity_id == res2.canonical_entity_id
    assert res1.canonical_value == res2.canonical_value == "OpenAI"

@pytest.mark.asyncio
async def test_seed_database_idempotency():
    repo = CanonicalEntityRepository(db=db_manager)
    for rec in CANONICAL_SEED_RECORDS:
        await repo.save_canonical_entity_record(rec)
    
    entities1 = await repo.get_all_canonical_entities()

    # Re-run seed operation
    for rec in CANONICAL_SEED_RECORDS:
        await repo.save_canonical_entity_record(rec)
    
    entities2 = await repo.get_all_canonical_entities()
    assert len(entities1) == len(entities2)
    assert len(entities2) >= len(CANONICAL_SEED_RECORDS)

@pytest.mark.asyncio
async def test_concurrent_entity_resolution_upsert():
    repo = CanonicalEntityRepository(db=db_manager)
    test_rec = CanonicalEntityRecord(
        canonical_entity_id="cent_concurrent_test_123",
        entity_type="STARTUP",
        canonical_name="Concurrent Test Inc",
        normalized_name="concurrent test",
        aliases=["Concurrent Test"],
        domains=["concurrent.io"]
    )

    async def worker():
        await repo.save_canonical_entity_record(test_rec)

    await asyncio.gather(worker(), worker())

    all_recs = await repo.get_all_canonical_entities()
    matches = [r for r in all_recs if r["canonical_entity_id"] == "cent_concurrent_test_123"]
    assert len(matches) == 1
