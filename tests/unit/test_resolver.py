from src.resolver.matcher import resolver
from src.resolver.normalizer import normalizer

def test_string_normalization():
    assert normalizer.normalize("  OpenAI, Inc.  ") == "openai"
    assert normalizer.normalize("ANTHROPIC PBC") == "anthropic"
    assert normalizer.normalize("Hugging Face Co.") == "hugging face"

def test_seed_alias_resolution():
    res1 = resolver.resolve("Open AI, Inc.")
    assert res1.canonical_value == "OpenAI"
    assert res1.decision in {"ALIAS_MATCH", "EXACT_NAME_MATCH"}

    res2 = resolver.resolve("anthropic pbc")
    assert res2.canonical_value == "Anthropic"

def test_deterministic_matching_resolution():
    res = resolver.resolve("OpenAI Inc")
    assert res.canonical_value == "OpenAI"
    assert res.confidence == 1.0
