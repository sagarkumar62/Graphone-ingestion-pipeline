import pytest
from src.utils.normalization import (
    normalize_whitespace,
    normalize_title,
    normalize_author_name,
    normalize_authors_list,
    extract_arxiv_id,
    normalize_arxiv_url,
    normalize_github_url,
    normalize_iso_date
)

def test_normalize_whitespace():
    assert normalize_whitespace("  Hello   World \n\t ") == "Hello World"
    assert normalize_whitespace(None) == ""

def test_normalize_title():
    assert normalize_title("  Attention Is   All You Need. ") == "attention is all you need"
    assert normalize_title("Deep Learning: A Survey,") == "deep learning: a survey"
    assert normalize_title("") == ""

def test_normalize_authors():
    assert normalize_author_name("  Ashish   Vaswani ") == "Ashish Vaswani"
    assert normalize_authors_list(["  Ashish   Vaswani ", "Noam Shazeer", "Ashish Vaswani"]) == ["Ashish Vaswani", "Noam Shazeer"]

def test_extract_arxiv_id():
    assert extract_arxiv_id("https://arxiv.org/abs/2301.12345v2") == "2301.12345"
    assert extract_arxiv_id("http://arxiv.org/pdf/2106.01234.pdf") == "2106.01234"
    assert extract_arxiv_id("cs/0112017") == "cs/0112017"
    assert extract_arxiv_id("invalid-string") is None

def test_normalize_arxiv_url():
    assert normalize_arxiv_url("https://arxiv.org/abs/2301.12345v1") == "https://arxiv.org/abs/2301.12345"
    assert normalize_arxiv_url("http://export.arxiv.org/api/query?id=2301.12345") == "https://arxiv.org/abs/2301.12345"

def test_normalize_github_url():
    assert normalize_github_url("https://github.com/google-research/bert.git/") == "https://github.com/google-research/bert"
    assert normalize_github_url("http://github.com/sponsors/user") is None

def test_normalize_iso_date():
    assert normalize_iso_date("2026-09-11T12:00:00Z") == "2026-09-11T12:00:00Z"
    assert normalize_iso_date("2026-09-11T12:00:00+00:00") == "2026-09-11T12:00:00Z"
