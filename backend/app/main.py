import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import init_db, async_session
from app.config import get_settings
from app.routers import chat, materials, problems, errors, plan, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="考研学习助手", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(materials.router)
app.include_router(problems.router)
app.include_router(errors.router)
app.include_router(plan.router)
app.include_router(dashboard.router)


@app.get("/api/health")
async def health():
    settings = get_settings()
    db_status = "ok"
    upload_status = "ok"
    detail_parts: list[str] = []

    # database check
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        detail_parts.append(f"database: {e}")

    # upload_dir check
    try:
        os.makedirs(settings.upload_dir, exist_ok=True)
    except Exception as e:
        upload_status = "error"
        detail_parts.append(f"upload_dir: {e}")

    # OCR availability check
    ocr_available = False
    ocr_detail = ""
    try:
        from app.services.ocr import get_available_languages

        available_languages = set(get_available_languages(settings))
        required_languages = set(settings.ocr_lang.split("+"))
        ocr_available = required_languages.issubset(available_languages)
        if not ocr_available:
            missing = required_languages - available_languages
            ocr_detail = f"missing languages: {', '.join(missing)}"
    except Exception as e:
        ocr_detail = str(e)

    overall = "ok" if db_status == "ok" and upload_status == "ok" else "degraded"

    result = {
        "status": overall,
        "database": db_status,
        "upload_dir": upload_status,
        "ai_configured": bool(settings.openai_api_key.strip()),
        "model": settings.openai_model,
        "ocr_available": ocr_available,
    }
    if detail_parts:
        result["detail"] = "; ".join(detail_parts)
    if ocr_detail:
        result["ocr_detail"] = ocr_detail
    return result
