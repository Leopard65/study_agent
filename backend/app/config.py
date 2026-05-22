from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_base_url: str = "https://api.deepseek.com"
    openai_api_key: str = ""
    openai_model: str = "deepseek-v4-flash"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    upload_dir: str = "./uploads"

    ocr_enabled: bool = True
    ocr_lang: str = "chi_sim+eng"
    tesseract_cmd: str = ""
    tessdata_dir: str = ""
    ocr_min_text_chars: int = 80
    ocr_max_pages: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
