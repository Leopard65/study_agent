from pathlib import Path


def configure_tesseract(settings) -> str:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    if not settings.tessdata_dir:
        return ""

    tessdata_dir = Path(settings.tessdata_dir).expanduser()
    if not tessdata_dir.is_absolute():
        tessdata_dir = Path(__file__).resolve().parents[2] / tessdata_dir
    tessdata_dir = tessdata_dir.resolve()
    return f'--tessdata-dir "{tessdata_dir}"'


def get_available_languages(settings) -> list[str]:
    import pytesseract

    config = configure_tesseract(settings)
    return pytesseract.get_languages(config=config)
