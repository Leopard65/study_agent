from pathlib import Path

import chardet
from docx import Document
from PyPDF2 import PdfReader


def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext in (".docx", ".doc"):
        return _extract_docx(file_path)
    if ext in (".txt", ".md", ".markdown"):
        return _extract_text(file_path)
    return ""


def _extract_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
    except Exception:
        text = ""

    from app.config import get_settings

    settings = get_settings()
    if len(text.strip()) >= settings.ocr_min_text_chars or not settings.ocr_enabled:
        return text

    try:
        return _ocr_pdf(file_path, settings)
    except Exception as e:
        print(f"[OCR] failed, falling back to PyPDF2 result: {e}")
        return text


def _ocr_pdf(file_path: str, settings) -> str:
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image

    from app.services.ocr import configure_tesseract

    configure_tesseract(settings)

    with fitz.open(file_path) as doc:
        pages_to_process = min(len(doc), settings.ocr_max_pages)
        texts = []
        for i in range(pages_to_process):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_text = pytesseract.image_to_string(
                img,
                lang=settings.ocr_lang,
            )
            if page_text.strip():
                texts.append(page_text.strip())
    return "\n".join(texts)


def _extract_docx(file_path: str) -> str:
    try:
        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception:
        return ""


def _extract_text(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
        return raw.decode(encoding, errors="replace")
    except Exception:
        return ""
