from pydantic_settings import BaseSettings
from functools import lru_cache


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
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_ai_configured() -> bool:
    """Check if a real API key is configured (not empty or a placeholder)."""
    key = get_settings().openai_api_key.strip().lower()
    return key not in _PLACEHOLDER_KEYS
