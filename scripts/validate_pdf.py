import PyPDF2
import os

pdf_path = "docs/ARCHITECTURE.pdf"
abs_path = os.path.abspath(pdf_path)
file_size = os.path.getsize(pdf_path)

print(f"PATH: {abs_path}")
print(f"SIZE: {file_size} bytes")

reader = PyPDF2.PdfReader(pdf_path)
page_count = len(reader.pages)
print(f"PAGES: {page_count}")

full_text = ""
for i, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    full_text += text
    print(f"--- PAGE {i+1} TEXT LENGTH: {len(text)} ---")

print(f"TOTAL_TEXT_LEN: {len(full_text)}")

# Check for required sections and keywords
required = [
    "Kafka", "capacity", "413", "429", "dedup", "freshness",
    "storage", "fault", "vector", "graph", "PostgreSQL",
    "ASSUMPTION", "500,000", "Gemini 2.5 Flash", "Groq compound", "DeepSeek",
    "PARTIAL PASS", "87 passed"
]
print("\n--- SECTION & REQUIREMENT PRESENCE ---")
text_lower = full_text.lower()
for term in required:
    present = term.lower() in text_lower
    print(f"  {term}: {'FOUND' if present else 'MISSING'}")

# Also check for presence of image / diagram on page 1
page1_images = len(reader.pages[0].images)
print(f"\nPAGE 1 IMAGES COUNT: {page1_images}")
