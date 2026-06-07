from pathlib import Path
from urllib.parse import urlencode
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from sqlalchemy.engine import make_url

# Anchor for resolving relative paths — always backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/app/../ = backend/

# Common placeholder values that should be treated as "not configured"
_PLACEHOLDER_KEYS = {
    "",
    "your_api_key_here",
    "your_deepseek_api_key",
    "replace_me",
    "sk-xxx",
    "sk-your-key-here",
    "your_openai_api_key",
    "xxx",
}


def _resolve_sqlite_url(raw_url: str) -> str:
    """Normalize a DATABASE_URL so that relative sqlite paths are anchored to backend/.

    Rules:
      - Non-sqlite URLs: returned unchanged.
      - sqlite:///:memory:: returned unchanged.
      - sqlite relative paths (e.g. ./data/app.db): resolved to absolute path
        under backend/ and returned as sqlite+aiosqlite:///ABS_PATH.
      - sqlite absolute paths: returned unchanged.
      - Query strings are preserved with proper URL encoding.
      - Forward slashes used everywhere (Windows + Unix compatible).

    Called by the Settings field_validator so get_settings().database_url is
    always the final usable URL regardless of CWD.
    """
    try:
        url = make_url(raw_url)
    except Exception:
        return raw_url
    if not url.drivername.startswith("sqlite"):
        return raw_url
    db_path = url.database
    if not db_path or db_path == ":memory:":
        return raw_url
    p = Path(db_path)
    if not p.is_absolute():
        p = (_BACKEND_DIR / p).resolve()
    # Use posix path (forward slashes) for URL — works on Windows and Unix
    abs_path = p.as_posix()
    # Reconstruct URL manually: sqlalchemy's sqlite URL format is driver:///path
    # (three slashes: scheme:// + empty authority + /path)
    new_url = f"{url.drivername}:///{abs_path}"
    if url.query:
        # urlencode with doseq=True handles multi-value params (?a=1&a=2) correctly.
        # Without doseq, tuples get str()-ified instead of being emitted as separate pairs.
        new_url = new_url + "?" + urlencode(url.query, doseq=True)
    return new_url


class Settings(BaseSettings):
    openai_base_url: str = "https://api.deepseek.com"
    openai_api_key: str = ""
    openai_model: str = "deepseek-v4-flash"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    upload_dir: str = "./uploads"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_timezone: str = "Asia/Shanghai"

    ocr_enabled: bool = True
    ocr_lang: str = "chi_sim+eng"
    tesseract_cmd: str = ""
    tessdata_dir: str = ""
    ocr_min_text_chars: int = 80
    ocr_max_pages: int = 30
    max_upload_mb: int = 50
    material_preview_chars: int = 5000
    material_parse_concurrency: int = 1

    class Config:
        env_file = str(_BACKEND_DIR / ".env")
        env_file_encoding = "utf-8"

    @field_validator("database_url")
    @classmethod
    def _resolve_database_url(cls, v: str) -> str:
        """Resolve relative sqlite paths against backend/, not CWD."""
        return _resolve_sqlite_url(v)

    @field_validator("upload_dir")
    @classmethod
    def _resolve_upload_dir(cls, v: str) -> str:
        """Resolve relative upload_dir against backend/, not CWD."""
        p = Path(v)
        if not p.is_absolute():
            p = (_BACKEND_DIR / p).resolve()
        return str(p)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_ai_configured() -> bool:
    """Check if a real API key is configured (not empty or a placeholder)."""
    key = get_settings().openai_api_key.strip().lower()
    return key not in _PLACEHOLDER_KEYS
