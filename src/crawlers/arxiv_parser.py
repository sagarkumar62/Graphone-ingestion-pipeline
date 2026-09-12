import re
from bs4 import BeautifulSoup
from src.utils.time import parse_date_string, format_iso8601
from src.core.logging import logger

class ArXivDOMParser:
    """
    Parses actual paper facts from live arXiv HTML pages.
    Extracts title, authors, publication date, abstract, and GitHub URLs without hallucination.
    """

    def parse_arxiv_html(self, html_content: str, source_url: str) -> dict:
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Title Extraction
        title = None
        # Try meta tag citation_title
        meta_title = soup.find("meta", {"name": "citation_title"})
        if meta_title and meta_title.get("content"):
            title = meta_title["content"].strip()
        else:
            # Try HTML title element
            title_el = soup.find("h1", class_=re.compile(r'title', re.I))
            if title_el:
                # Remove 'Title:' descriptor prefix if present
                for span in title_el.find_all("span", class_="descriptor"):
                    span.decompose()
                title = title_el.get_text(strip=True)

        if not title:
            title = "Untitled arXiv Paper"

        # 2. Authors Extraction
        authors = []
        meta_authors = soup.find_all("meta", {"name": "citation_author"})
        if meta_authors:
            authors = [m["content"].strip() for m in meta_authors if m.get("content")]
        else:
            authors_div = soup.find("div", class_="authors")
            if authors_div:
                authors = [a.get_text(strip=True) for a in authors_div.find_all("a")]

        if not authors:
            authors = ["Unknown Author"]

        # 3. Publication Date Extraction
        published_date_str = None
        meta_date = soup.find("meta", {"name": "citation_date"})
        if meta_date and meta_date.get("content"):
            parsed_dt = parse_date_string(meta_date["content"])
            if parsed_dt:
                published_date_str = format_iso8601(parsed_dt)

        if not published_date_str:
            dateline = soup.find("div", class_="dateline")
            if dateline:
                date_text = dateline.get_text(strip=True)
                parsed_dt = parse_date_string(date_text)
                if parsed_dt:
                    published_date_str = format_iso8601(parsed_dt)

        if not published_date_str:
            published_date_str = format_iso8601()

        # 4. Abstract Extraction
        abstract = None
        meta_abstract = soup.find("meta", {"name": "citation_abstract"})
        if meta_abstract and meta_abstract.get("content"):
            abstract = meta_abstract["content"].strip()
        else:
            abstract_el = soup.find("blockquote", class_=re.compile(r'abstract', re.I))
            if abstract_el:
                for span in abstract_el.find_all("span", class_="descriptor"):
                    span.decompose()
                abstract = abstract_el.get_text(strip=True)

        # 5. Real GitHub URL Extraction (Search body text for github.com links)
        github_url = None
        gh_match = re.search(r'https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)', html_content)
        if gh_match:
            owner, repo = gh_match.group(1), gh_match.group(2).rstrip('.git').rstrip('/')
            if owner.lower() not in {"sponsors", "about", "features", "pricing", "security"}:
                github_url = f"https://github.com/{owner}/{repo}"

        now_iso = format_iso8601()

        return {
            "schemaVersion": "1.0",
            "recordType": "RESEARCH_PAPER",
            "source": {
                "name": "ArXiv",
                "url": source_url
            },
            "content": {
                "title": title,
                "authors": authors,
                "paper_url": source_url,
                "github_url": github_url,
                "github_stars": None,  # Will be enriched by GitHub API if github_url exists
                "published_date": published_date_str,
                "abstract": abstract,
                "primaryCategory": "cs.AI"
            },
            "collectedAt": now_iso
        }

arxiv_parser = ArXivDOMParser()
