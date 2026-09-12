import re
import json
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from src.core.logging import logger

class ExtractedHTMLContent(BaseModel):
    title: str = ""
    main_text: str = ""
    meta_dates: list[str] = Field(default_factory=list)
    json_ld_dates: list[str] = Field(default_factory=list)
    meta_description: str = ""
    canonical_url: str | None = None
    structured_json_ld: list[dict] = Field(default_factory=list)

class HTMLExtractor:
    """
    Robust HTML full-text and metadata extraction layer.
    Extracts main readable text while preserving titles, publication dates, and JSON-LD schema objects.
    """

    @staticmethod
    def extract(html_content: str, source_url: str = "") -> ExtractedHTMLContent:
        if not html_content or not html_content.strip():
            return ExtractedHTMLContent()

        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Extract JSON-LD scripts before removing script tags
        json_ld_objects = []
        json_ld_dates = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    data = json.loads(script.string.strip())
                    if isinstance(data, dict):
                        json_ld_objects.append(data)
                    elif isinstance(data, list):
                        json_ld_objects.extend([d for d in data if isinstance(d, dict)])
                except Exception:
                    pass

        for item in json_ld_objects:
            # Recursively check for date keys
            for key in ["datePublished", "dateCreated", "dateModified", "datePosted"]:
                if key in item and isinstance(item[key], str):
                    json_ld_dates.append(item[key])

        # 2. Extract title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        # 3. Extract Canonical URL
        canonical_url = source_url
        canonical_tag = soup.find("link", rel="canonical")
        if canonical_tag and canonical_tag.get("href"):
            canonical_url = canonical_tag["href"]

        # 4. Meta Description
        meta_desc = ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
        if meta_desc_tag and meta_desc_tag.get("content"):
            meta_desc = meta_desc_tag["content"].strip()

        # 5. Extract meta publication dates
        meta_dates = []
        date_meta_attrs = [
            {"property": "article:published_time"},
            {"property": "og:published_time"},
            {"name": "date"},
            {"name": "pubdate"},
            {"name": "publication_date"},
            {"name": "DC.date.issued"},
            {"itemprop": "datePublished"},
        ]
        for attrs in date_meta_attrs:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                meta_dates.append(tag["content"].strip())

        # 6. De-noise body HTML
        for noise in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]):
            noise.decompose()

        # Prefer <main> or <article> if available
        main_container = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|post|article|body|entry", re.I)) or soup.body or soup

        # Extract text paragraphs and headers
        text_blocks = []
        for el in main_container.find_all(["p", "h1", "h2", "h3", "h4", "li", "section"]):
            text = el.get_text().strip()
            if text and len(text) > 10:
                text_blocks.append(text)

        main_text = "\n\n".join(text_blocks) if text_blocks else main_container.get_text(separator="\n", strip=True)

        return ExtractedHTMLContent(
            title=title,
            main_text=main_text,
            meta_dates=meta_dates,
            json_ld_dates=json_ld_dates,
            meta_description=meta_desc,
            canonical_url=canonical_url,
            structured_json_ld=json_ld_objects
        )

html_extractor = HTMLExtractor()
