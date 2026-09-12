import sys
import os

sys.path.insert(0, os.path.abspath("."))
from src.resolver.matcher import resolver

def test_er_variants():
    test_variants = ["OpenAI", "Open AI", "OpenAI Inc.", "OpenAI, Inc."]
    print("=" * 60)
    print("ENTITY RESOLUTION VARIANT AUDIT:")
    results = {}
    for var in test_variants:
        res = resolver.resolve(var, entity_type="STARTUP", source_url="https://ycombinator.com/companies/openai")
        results[var] = (res.canonical_value, res.decision, res.match_method, res.confidence)
        print(f"  - '{var}' -> Canonical: '{res.canonical_value}' | Decision: {res.decision} | Method: {res.match_method} | Confidence: {res.confidence}")

    all_openai = all(r[0] == "OpenAI" for r in results.values())
    print(f"\nAll OpenAI variants resolved to canonical 'OpenAI': {'YES' if all_openai else 'NO'}")

    # False-merge protection test
    print("\nFalse-Merge Protection Tests:")
    unrelated_pairs = [
        ("OpenAI", "Google"),
        ("Anthropic", "Microsoft"),
        ("DeepSeek", "Meta"),
        ("Stripe", "PayPal")
    ]
    for e1, e2 in unrelated_pairs:
        res1 = resolver.resolve(e1, entity_type="STARTUP")
        res2 = resolver.resolve(e2, entity_type="STARTUP")
        is_distinct = res1.canonical_value != res2.canonical_value
        print(f"  - Pair ('{e1}', '{e2}') -> Distinct Canonical Values ('{res1.canonical_value}' vs '{res2.canonical_value}'): {'PASS' if is_distinct else 'FAIL'}")

    print("=" * 60)

if __name__ == "__main__":
    test_er_variants()
