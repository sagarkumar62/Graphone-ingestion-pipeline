import os

def scan_contamination():
    keywords = ["Phase 7", "PHASE7", "Gemini Journal", "journal coach", "Firestore", "research_papers_fts", "paper_embeddings", "src.embedding", "src.search"]
    ignore_dirs = {".git", "__pycache__", "scratch", ".venv", "venv", "node_modules", ".pytest_cache", ".idea", "brain"}

    findings = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    for kw in keywords:
                        if kw.lower() in content.lower():
                            findings.append((filepath, kw))
            except Exception:
                pass

    print(f"Total contamination matches found: {len(findings)}")
    for fp, kw in findings:
        print(f"  {fp}: match for '{kw}'")

if __name__ == "__main__":
    scan_contamination()
