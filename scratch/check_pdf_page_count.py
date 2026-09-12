import os
import re
import sys

def check_pdf():
    pdf_path = "docs/ARCHITECTURE.pdf"
    if not os.path.exists(pdf_path):
        print(f"PDF not found at {pdf_path}")
        return

    size_bytes = os.path.getsize(pdf_path)
    print(f"ARCHITECTURE.pdf exists! File size: {size_bytes} bytes ({size_bytes / 1024:.2f} KB)")

    reader = None
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        print("Using library: PyPDF2")
    except ImportError:
        pass

    if reader is not None:
        print(f"Page Count: {len(reader.pages)}")
        for idx, p in enumerate(reader.pages):
            text = p.extract_text() or ""
            print(f"  - Page {idx+1} character count: {len(text)}")
    else:
        # Fallback raw PDF parsing
        with open(pdf_path, "rb") as f:
            content = f.read()
        matches = re.findall(rb"/Type\s*/Page\b", content)
        print(f"Fallback Regex Page Count (/Type /Page): {len(matches)}")

if __name__ == "__main__":
    check_pdf()

