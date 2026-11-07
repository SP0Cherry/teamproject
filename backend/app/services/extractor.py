"""Document text extraction: text, PDF, DOCX, and OCR for images (AI-01, AI-06).

OCR is delegated to an external adapter (model_double in tests). If OCR returns
no text or only whitespace, extraction is marked failed.
"""

from pathlib import Path

from pypdf import PdfReader
from docx import Document

from app.core.config import settings

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

MAX_IMAGE_PIXELS = settings.max_image_pixels
MAX_PDF_PAGES = settings.max_pdf_pages
MAX_TEXT_CHARS = settings.max_text_chars


def extract_text(file_path: str, mime_type: str, ocr_fn=None) -> tuple[str, str]:
    """Extract text from a file. Returns (text, error_or_empty).

    On success returns (text, ""). On failure returns ("", error_message).
    """
    path = Path(file_path)

    if mime_type == "text/plain":
        return _extract_txt(path)
    elif mime_type == "application/pdf":
        return _extract_pdf(path)
    elif mime_type.endswith("wordprocessingml.document"):
        return _extract_docx(path)
    elif mime_type in ("image/png", "image/jpeg"):
        return _extract_image(path, ocr_fn)
    else:
        return "", f"unsupported type: {mime_type}"


def _extract_txt(path: Path) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return "", f"read error: {e}"
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
    if not text.strip():
        return "", "empty text"
    return text, ""


def _extract_pdf(path: Path) -> tuple[str, str]:
    try:
        reader = PdfReader(str(path))
        if len(reader.pages) > MAX_PDF_PAGES:
            return "", f"pdf exceeds {MAX_PDF_PAGES} pages"
        text_parts = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
    except Exception as e:
        return "", f"pdf parse error: {e}"
    if not text.strip():
        return "", "no extractable text in pdf"
    return text, ""


def _extract_docx(path: Path) -> tuple[str, str]:
    try:
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return "", f"docx parse error: {e}"
    if not text.strip():
        return "", "empty docx"
    return text, ""


def _extract_image(path: Path, ocr_fn) -> tuple[str, str]:
    if ocr_fn is None:
        return "", "ocr not configured"
    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
            if w * h > MAX_IMAGE_PIXELS:
                return "", f"image exceeds {MAX_IMAGE_PIXELS} pixels"
    except Exception as e:
        return "", f"image parse error: {e}"
    try:
        text = ocr_fn(str(path))
    except Exception as e:
        return "", f"ocr error: {e}"
    if not text or not text.strip():
        return "", "ocr returned no text"
    return text, ""
