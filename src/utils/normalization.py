import re
from datetime import datetime

def normalize_whitespace(text: str | None) -> str:
    """Collapses multiple spaces, tabs, and newlines into a single space."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def normalize_title(title: str | None) -> str:
    """
    Normalizes a research paper title:
    - Trims whitespace
    - Lowercases
    - Removes trailing period/punct
    - Replaces multiple spaces with single space
    """
    if not title:
        return ""
    cleaned = normalize_whitespace(title)
    cleaned = cleaned.lower()
    cleaned = re.sub(r'[\.\,\:\;\s]+$', '', cleaned)
    return cleaned

def normalize_author_name(author: str | None) -> str:
    """Normalizes an author name by trimming and collapsing inner spaces."""
    if not author:
        return ""
    return normalize_whitespace(author)

def normalize_authors_list(authors: list[str] | None) -> list[str]:
    """Applies author normalization to a list of author names."""
    if not authors:
        return []
    result = []
    for a in authors:
        norm = normalize_author_name(a)
        if norm and norm not in result:
            result.append(norm)
    return result

def extract_arxiv_id(url_or_id: str | None) -> str | None:
    """
    Extracts canonical arXiv ID from a string, URL, or ID.
    Supports modern format (e.g. 2301.12345 or 2301.12345v2) and legacy format (e.g. cs/0112017).
    """
    if not url_or_id:
        return None

    # Modern arXiv ID: 4 digits.4 or 5 digits (optionally vN)
    match_modern = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', url_or_id)
    if match_modern:
        return match_modern.group(1)

    # Legacy arXiv ID: category/7digits (e.g., cs/0112017 or math-ph/0203001)
    match_legacy = re.search(r'([a-zA-Z\-]+/\d{7})(v\d+)?', url_or_id)
    if match_legacy:
        return match_legacy.group(1)

    return None

def normalize_arxiv_url(url: str | None) -> str | None:
    """Canonicalizes arXiv URL to https://arxiv.org/abs/{arxiv_id}."""
    arxiv_id = extract_arxiv_id(url)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    return url

def normalize_github_url(url: str | None) -> str | None:
    """
    Normalizes a GitHub repository URL to standard form:
    https://github.com/owner/repo
    Excludes non-repository URLs like /sponsors, /about, /features, etc.
    """
    if not url:
        return None
    url_clean = re.sub(r'\.git/?$', '', url).rstrip('/')
    match = re.search(r'https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)', url_clean)
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2)
    if owner.lower() in {"sponsors", "about", "features", "pricing", "security", "topics", "collections", "settings"}:
        return None
    return f"https://github.com/{owner}/{repo}"

def normalize_iso_date(date_str: str | None) -> str | None:
    """Validates and normalizes date string to ISO-8601 string YYYY-MM-DDTHH:MM:SSZ."""
    if not date_str:
        return None
    try:
        # Handle 'Z' suffix or offset
        dt_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return date_str
