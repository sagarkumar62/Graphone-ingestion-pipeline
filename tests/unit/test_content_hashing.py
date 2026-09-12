import pytest
from src.utils.hashing import compute_research_paper_hash

def test_same_content_same_hash():
    h1 = compute_research_paper_hash(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        abstract="The dominant sequence transduction models...",
        published_date="2017-06-12T00:00:00Z",
        source_url="https://arxiv.org/abs/1706.03762",
        primary_category="cs.CL"
    )
    h2 = compute_research_paper_hash(
        title=" Attention Is  All You Need. ",
        authors=["Noam Shazeer", "Ashish Vaswani"],  # Different order
        abstract="The dominant sequence transduction models...",
        published_date="2017-06-12T00:00:00Z",
        source_url="https://arxiv.org/abs/1706.03762v1",
        primary_category="cs.CL"
    )
    assert h1 == h2

def test_changed_content_changed_hash():
    h1 = compute_research_paper_hash(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        abstract="Abstract A",
        published_date="2017-06-12T00:00:00Z",
        source_url="https://arxiv.org/abs/1706.03762"
    )
    h2 = compute_research_paper_hash(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        abstract="Abstract B",  # Changed abstract
        published_date="2017-06-12T00:00:00Z",
        source_url="https://arxiv.org/abs/1706.03762"
    )
    assert h1 != h2
