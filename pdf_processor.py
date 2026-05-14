import fitz  # PyMuPDF


def extract_pages_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """Returns list of {page_num, text} for each page."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append({"page_num": i, "text": page.get_text()})
    return pages


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Full document text (legacy helper)."""
    return "\n".join(p["text"] for p in extract_pages_from_pdf(pdf_bytes))
