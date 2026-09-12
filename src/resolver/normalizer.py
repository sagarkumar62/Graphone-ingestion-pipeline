import unicodedata
import re

SAFE_LEGAL_SUFFIXES = [
    r'\binc\.?\b', r'\bllc\.?\b', r'\bcorp\.?\b', r'\bcorporation\b', r'\bltd\.?\b',
    r'\blimited\b', r'\bgmbh\b', r'\bco\.?\b', r'\bcompany\b', r'\bpbc\b', r'\bplc\b',
    r'\bs\.a\.s\.?\b', r'\bs\.a\.?\b'
]

class EntityNormalizer:
    """
    Multi-stage conservative deterministic string & domain normalization pipeline:
    Stage 1: Unicode Normalization (NFKC)
    Stage 2: Case Normalization (Lowercase)
    Stage 3: Normalization of '&' vs 'and'
    Stage 4: Punctuation Stripping (Keep alphanumeric and spaces)
    Stage 5: Conservative Corporate Legal Suffix Stripping (Inc, LLC, Corp, Ltd, GmbH, PBC, PLC)
             - Does NOT strip meaningful words like 'Labs', 'Research', 'Capital', 'Records', 'Systems', 'Technologies', 'AI'
    Stage 6: Whitespace Collapsing & Trimming
    """

    def normalize(self, raw_name: str) -> str:
        if not raw_name:
            return ""

        # Stage 1: Unicode NFKC
        text = unicodedata.normalize("NFKC", raw_name)

        # Stage 2: Case Normalization
        text = text.lower()

        # Stage 3: Normalize '&' to 'and'
        text = re.sub(r'\b&\b', 'and', text)

        # Stage 4: Punctuation Stripping (Keep alphanumeric and spaces)
        text = re.sub(r'[^\w\s]', ' ', text)

        # Stage 5: Conservative Corporate Legal Suffix Stripping
        for pattern in SAFE_LEGAL_SUFFIXES:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Stage 6: Whitespace Collapsing & Trimming
        text = ' '.join(text.split())

        return text

    def normalize_domain(self, raw_url_or_domain: str) -> str:
        """
        Normalizes URLs and hostnames to clean canonical domain format (e.g., 'openai.com').
        Strips schemes (http://, https://), 'www.', paths, ports, and query parameters.
        """
        if not raw_url_or_domain:
            return ""

        domain = raw_url_or_domain.strip().lower()
        # Remove scheme
        domain = re.sub(r'^https?://', '', domain)
        # Remove trailing path and query string
        domain = domain.split('/')[0].split('?')[0].split('#')[0].split(':')[0]
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]

        return domain.strip()

normalizer = EntityNormalizer()
