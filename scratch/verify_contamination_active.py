import os

keywords = ["Phase 7", "PHASE7", "Gemini Journal", "journal coach", "Firestore", "research_papers_fts", "paper_embeddings", "src.embedding", "src.search"]
target_dirs = ["src", "scripts", "tests", "docs"]

found = []

for d in target_dirs:
    if not os.path.exists(d):
        continue
    for root, _, files in os.walk(d):
        for fname in files:
            path = os.path.join(root, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    for kw in keywords:
                        if kw.lower() in content.lower():
                            found.append((path, kw))
            except Exception:
                pass

print("Contamination search in active project directories (src, scripts, tests, docs):")
if found:
    print(f"FOUND {len(found)} CONTAMINATION MATCHES:")
    for path, kw in found:
        print(f"  - {path}: {kw}")
else:
    print("CLEAN! Zero contamination terms found in active project code and docs!")
