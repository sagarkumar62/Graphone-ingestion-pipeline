import hashlib
import json
import re
from src.utils.normalization import (
    normalize_title,
    normalize_authors_list,
    normalize_whitespace,
    normalize_iso_date,
    extract_arxiv_id
)

def hash_url(url: str) -> str:
    """Generates SHA-256 hash for a canonical URL."""
    if not url:
        return ""
    clean_url = url.strip().lower().rstrip('/')
    return hashlib.sha256(clean_url.encode('utf-8')).hexdigest()

def compute_simhash(text: str, hashbits: int = 64) -> int:
    """Calculates 64-bit SimHash for near-duplicate text detection."""
    if not text:
        return 0
    words = re.findall(r'\w+', text.lower())
    if not words:
        return 0

    v = [0] * hashbits
    for word in words:
        w_hash = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if w_hash & bitmask:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hashbits):
        if v[i] >= 0:
            fingerprint |= (1 << i)
    return fingerprint

def hamming_distance(simhash1: int, simhash2: int) -> int:
    """Calculates Hamming distance between two SimHash integers."""
    x = simhash1 ^ simhash2
    return bin(x).count('1')

def compute_research_paper_hash(
    title: str | None,
    authors: list[str] | None,
    abstract: str | None,
    published_date: str | None,
    source_url: str | None,
    primary_category: str | None = None
) -> str:
    """
    Computes a deterministic SHA-256 hash for a research paper record.
    Ensures field order and formatting variations produce identical hashes for equivalent data,
    while meaningful source changes produce a changed hash.
    Does NOT use timestamps (collected_at) as content identity.
    """
    norm_title = normalize_title(title)
    norm_authors = sorted(normalize_authors_list(authors))
    norm_abstract = normalize_whitespace(abstract)
    norm_date = normalize_iso_date(published_date) or ""
    arxiv_id = extract_arxiv_id(source_url) or source_url or ""
    category = normalize_whitespace(primary_category).lower()

    payload = {
        "title": norm_title,
        "authors": norm_authors,
        "abstract": norm_abstract,
        "date": norm_date,
        "arxiv_id": arxiv_id,
        "category": category
    }

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
