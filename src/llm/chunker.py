import re
from bs4 import BeautifulSoup
from src.core.logging import logger

class IntelligentPayloadChunker:
    """
    Intelligent payload chunker and truncator to handle HTTP 413 / context window overflow.
    Strips HTML boilerplate, scores document density, and truncates text while preserving
    semantically dense entity metadata.
    """

    def __init__(self, max_words: int = 2500):
        self.max_words = max_words

    def clean_html(self, html_content: str) -> str:
        """Strips scripts, styles, SVGs, navbars, and returns plain structured text."""
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove irrelevant non-content tags
        for tag in soup(["script", "style", "svg", "nav", "footer", "header", "iframe", "noscript"]):
            tag.decompose()

        # Extract text preserving paragraphs and headings
        text = soup.get_text(separator="\n", strip=True)

        # Collapse excess empty newlines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        return cleaned_text

    def chunk_text(self, text: str, max_words: int | None = None) -> str:
        """
        Truncates text payload to max_words bounds, retaining top high-density content
        (first 80% of window) and bottom references (last 20% of window).
        """
        target_words = max_words or self.max_words
        words = text.split()

        if len(words) <= target_words:
            return text

        logger.info(f"Payload truncated from {len(words)} words to {target_words} words to fit context window.")

        top_count = int(target_words * 0.8)
        bottom_count = target_words - top_count

        top_words = words[:top_count]
        bottom_words = words[-bottom_count:] if bottom_count > 0 else []

        truncated = " ".join(top_words) + "\n\n[... TRUNCATED FOR CONTEXT WINDOW ...]\n\n" + " ".join(bottom_words)
        return truncated

    def split_into_structural_chunks(self, text: str, max_words_per_chunk: int = 1500) -> list[str]:
        """
        Splits a large document into structural/semantic chunks along paragraph and section boundaries
        without cutting in the middle of sentences or structured entities.
        """
        if not text:
            return [""]

        words = text.split()
        if len(words) <= max_words_per_chunk:
            return [text]

        # Split by section breaks/paragraphs first
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk_paragraphs = []
        current_word_count = 0

        for para in paragraphs:
            para_word_count = len(para.split())
            if current_word_count + para_word_count > max_words_per_chunk and current_chunk_paragraphs:
                chunks.append("\n\n".join(current_chunk_paragraphs))
                current_chunk_paragraphs = [para]
                current_word_count = para_word_count
            else:
                current_chunk_paragraphs.append(para)
                current_word_count += para_word_count

        if current_chunk_paragraphs:
            chunks.append("\n\n".join(current_chunk_paragraphs))

        logger.info(f"Split document ({len(words)} words) into {len(chunks)} structural chunks.")
        return chunks

    def merge_partial_extractions(self, extractions: list[dict]) -> dict:
        """
        Merges partial structured JSON extractions from multiple chunks into a unified canonical dict.
        Combines lists (without duplicates) and preserves non-null values without fabrication.
        """
        if not extractions:
            return {}

        if len(extractions) == 1:
            return extractions[0]

        base = extractions[0].copy()
        base_content = base.get("content", {}).copy()

        for ext in extractions[1:]:
            content = ext.get("content", {})
            for key, val in content.items():
                if val is None:
                    continue
                current_val = base_content.get(key)
                if current_val is None or current_val == "" or current_val == []:
                    base_content[key] = val
                elif isinstance(current_val, list) and isinstance(val, list):
                    # Combine lists preserving order & removing duplicates
                    merged_list = list(current_val)
                    for item in val:
                        if item not in merged_list:
                            merged_list.append(item)
                    base_content[key] = merged_list
                elif isinstance(current_val, str) and isinstance(val, str) and len(val) > len(current_val):
                    # Prefer richer/longer textual descriptions (e.g. abstract/summary)
                    base_content[key] = val

        base["content"] = base_content
        return base

    def process_raw_payload(self, raw_content: str, max_words: int | None = None) -> str:
        """Full pipeline: cleans HTML and enforces word chunk bounds."""
        clean = self.clean_html(raw_content)
        return self.chunk_text(clean, max_words=max_words)

chunker = IntelligentPayloadChunker()
