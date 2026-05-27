import os
from pathlib import Path


def configure_tesseract(settings) -> str:
    """Configure pytesseract executable and tessdata directory.

    Sets TESSDATA_PREFIX env var for language data lookup (avoids
    --tessdata-dir flag issues with paths containing spaces).
    Returns an empty string — callers should not pass config to pytesseract.
    """
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    if settings.tessdata_dir:
        tessdata_dir = Path(settings.tessdata_dir).expanduser()
        if not tessdata_dir.is_absolute():
            tessdata_dir = Path(__file__).resolve().parents[2] / tessdata_dir
        tessdata_dir = tessdata_dir.resolve()
        if tessdata_dir.is_dir():
            os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)

    return ""


def get_available_languages(settings) -> list[str]:
    import pytesseract

    configure_tesseract(settings)
    return pytesseract.get_languages()
