import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import init_db, async_session
from app.config import get_settings, is_ai_configured
from app.routers import chat, materials, problems, errors, plan, dashboard, exam, export, settings as settings_router, import_data, search, sessions, review, maintenance

# Resolve frontend/dist relative to project root (backend/../frontend/dist)
_BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent
_DIST_DIR = _PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    await init_db()
    from app.services.parse_worker import start_worker, stop_worker
    await start_worker()
    yield
    await stop_worker()


app = FastAPI(title="考研学习助手", version="0.7.0", lifespan=lifespan)

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
app.include_router(exam.router)
app.include_router(export.router)
app.include_router(settings_router.router)
app.include_router(import_data.router)
app.include_router(search.router)
app.include_router(sessions.router)
app.include_router(review.router)
app.include_router(maintenance.router)


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
        if not os.path.isdir(settings.upload_dir):
            upload_status = "error"
            detail_parts.append("upload_dir: directory does not exist")
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
        "ai_configured": is_ai_configured(),
        "model": settings.openai_model,
        "ocr_available": ocr_available,
    }
    if detail_parts:
        result["detail"] = "; ".join(detail_parts)
    if ocr_detail:
        result["ocr_detail"] = ocr_detail
    return result


# ── Production mode: serve frontend/dist if present ──
if _DIST_DIR.is_dir():
    # Serve static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="static-assets")

    # Serve other static files from dist (favicon, manifest, sw.js, etc.)
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Serve frontend files. Non-/api routes fall back to index.html for SPA routing."""
        # /api/* that didn't match any registered route → 404 JSON, not HTML
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": f"未找到 API 端点: /{full_path}"})
        # Serve static file if it exists
        file_path = _DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # SPA fallback: serve index.html for client-side routing
        return FileResponse(str(_DIST_DIR / "index.html"))
