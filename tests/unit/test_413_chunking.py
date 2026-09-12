from src.llm.chunker import IntelligentPayloadChunker

def test_payload_cleaning():
    chunker = IntelligentPayloadChunker()
    raw_html = "<html><head><script>alert('nav')</script></head><body><nav>Links</nav><h1>Paper Title</h1><p>Main body content paragraph.</p></body></html>"
    cleaned = chunker.clean_html(raw_html)
    
    assert "Paper Title" in cleaned
    assert "Main body content paragraph." in cleaned
    assert "alert" not in cleaned
    assert "Links" not in cleaned

def test_payload_truncation_for_413():
    chunker = IntelligentPayloadChunker(max_words=100)
    large_text = " ".join([f"word_{i}" for i in range(500)])
    
    truncated = chunker.chunk_text(large_text, max_words=100)
    assert len(truncated.split()) <= 110
    assert "[... TRUNCATED FOR CONTEXT WINDOW ...]" in truncated
