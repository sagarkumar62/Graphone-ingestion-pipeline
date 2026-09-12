import hashlib
from src.core.models import CanonicalEntityRecord

def generate_seed_entity_id(entity_type: str, canonical_name: str) -> str:
    key = f"{entity_type.lower()}:{canonical_name.lower().strip()}"
    h = hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]
    return f"cent_{h}"

CANONICAL_SEED_RECORDS = [
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "OpenAI"),
        entity_type="STARTUP",
        canonical_name="OpenAI",
        normalized_name="openai",
        aliases=["Open AI", "OpenAI Inc.", "OpenAI, Inc.", "OpenAI LLC", "Open AI Inc"],
        domains=["openai.com"],
        external_ids={"crunchbase": "openai", "wikidata": "Q21708200"},
        source_urls=["https://openai.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Anthropic"),
        entity_type="STARTUP",
        canonical_name="Anthropic",
        normalized_name="anthropic",
        aliases=["Anthropic PBC", "Anthropic AI"],
        domains=["anthropic.com"],
        external_ids={"crunchbase": "anthropic", "wikidata": "Q111167389"},
        source_urls=["https://anthropic.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Google"),
        entity_type="STARTUP",
        canonical_name="Google",
        normalized_name="google",
        aliases=["Google LLC", "Google Inc."],
        domains=["google.com"],
        external_ids={"crunchbase": "google", "wikidata": "Q95"},
        source_urls=["https://google.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Microsoft"),
        entity_type="STARTUP",
        canonical_name="Microsoft",
        normalized_name="microsoft",
        aliases=["Microsoft Corporation", "Microsoft Corp"],
        domains=["microsoft.com"],
        external_ids={"crunchbase": "microsoft", "wikidata": "Q2283"},
        source_urls=["https://microsoft.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Meta"),
        entity_type="STARTUP",
        canonical_name="Meta",
        normalized_name="meta",
        aliases=["Meta Inc.", "Meta Platforms", "Facebook Inc."],
        domains=["meta.com"],
        external_ids={"crunchbase": "meta", "wikidata": "Q380"},
        source_urls=["https://meta.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "NVIDIA"),
        entity_type="STARTUP",
        canonical_name="NVIDIA",
        normalized_name="nvidia",
        aliases=["Nvidia Corp", "NVIDIA Corporation"],
        domains=["nvidia.com"],
        external_ids={"crunchbase": "nvidia", "wikidata": "Q182638"},
        source_urls=["https://nvidia.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Apple"),
        entity_type="STARTUP",
        canonical_name="Apple",
        normalized_name="apple",
        aliases=["Apple Inc.", "Apple Computer"],
        domains=["apple.com"],
        external_ids={"crunchbase": "apple", "wikidata": "Q312"},
        source_urls=["https://apple.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Amazon"),
        entity_type="STARTUP",
        canonical_name="Amazon",
        normalized_name="amazon",
        aliases=["Amazon.com Inc.", "Amazon Inc."],
        domains=["amazon.com"],
        external_ids={"crunchbase": "amazon", "wikidata": "Q3884"},
        source_urls=["https://amazon.com"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Mistral AI"),
        entity_type="STARTUP",
        canonical_name="Mistral AI",
        normalized_name="mistral ai",
        aliases=["Mistral", "Mistral AI SAS"],
        domains=["mistral.ai"],
        external_ids={"crunchbase": "mistral-ai"},
        source_urls=["https://mistral.ai"]
    ),
    CanonicalEntityRecord(
        canonical_entity_id=generate_seed_entity_id("STARTUP", "Hugging Face"),
        entity_type="STARTUP",
        canonical_name="Hugging Face",
        normalized_name="hugging face",
        aliases=["HuggingFace", "HuggingFace Inc."],
        domains=["huggingface.co"],
        external_ids={"crunchbase": "hugging-face"},
        source_urls=["https://huggingface.co"]
    )
]

CANONICAL_SEED_ENTITIES = {r.canonical_name for r in CANONICAL_SEED_RECORDS}

SEED_ALIAS_MAP = {}
for rec in CANONICAL_SEED_RECORDS:
    for alias in rec.aliases:
        SEED_ALIAS_MAP[alias.lower()] = rec.canonical_name
