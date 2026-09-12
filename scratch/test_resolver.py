from src.resolver.matcher import resolver

test_names = ["OpenAI", "Open AI", "OpenAI Inc.", "OpenAI, Inc."]
for n in test_names:
    res = resolver.resolve(n, "STARTUP")
    print(f"'{n}' -> '{res.canonical_value}' (method: {res.match_method}, confidence: {res.confidence}, decision: {res.decision})")
