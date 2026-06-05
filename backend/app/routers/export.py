import io
import os
import zipfile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.config import get_settings
from app.models import (
    Material, MaterialChunk, ChatHistory, ErrorBook,
    StudyPlan, ProblemRecord, ExamQuestion, ExamAttempt, OperationLog,
    AppSetting, StudySession,
)

router = APIRouter(prefix="/api/export", tags=["export"])

# Application display version (shown in Sidebar, FastAPI metadata)
APP_VERSION = "0.6.0"
# Backup JSON schema version — used by import for compatibility checks.
# Do NOT change unless the backup format is intentionally changed;
# existing backups rely on this string for import validation.
BACKUP_SCHEMA_VERSION = "0.3"


def _dt(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


@router.get("/json")
async def export_json(db: AsyncSession = Depends(get_db)):
    # Materials metadata (no content, no stored file)
    mats = (await db.execute(select(Material).order_by(Material.id))).scalars().all()
    materials = []
    for m in mats:
        materials.append({
            "id": m.id,
            "filename": m.filename,
            "file_type": m.file_type,
            "content_length": len(m.content) if m.content else 0,
            "created_at": _dt(m.created_at),
        })

    # Material chunks count
    chunks_count = (await db.execute(select(func.count()).select_from(MaterialChunk))).scalar() or 0

    # Chat history
    chats = (await db.execute(select(ChatHistory).order_by(ChatHistory.id))).scalars().all()
    chat_history = [
        {"id": c.id, "conversation_id": c.conversation_id or "", "question": c.question, "answer": c.answer, "created_at": _dt(c.created_at)}
        for c in chats
    ]

    # Error book
    errors = (await db.execute(select(ErrorBook).order_by(ErrorBook.id))).scalars().all()
    error_book = [
        {
            "id": e.id, "subject": e.subject, "chapter": e.chapter,
            "knowledge_point": e.knowledge_point, "question": e.question,
            "user_answer": e.user_answer, "correct_answer": e.correct_answer,
            "error_type": e.error_type, "error_reason": e.error_reason,
            "correct_approach": e.correct_approach, "review_suggestion": e.review_suggestion,
            "tags": e.tags, "next_review_date": e.next_review_date,
            "mastered": e.mastered, "review_count": e.review_count,
            "created_at": _dt(e.created_at),
        }
        for e in errors
    ]

    # Study plans
    plans = (await db.execute(select(StudyPlan).order_by(StudyPlan.id))).scalars().all()
    study_plans = [
        {"id": p.id, "date": p.date, "subject": p.subject, "task": p.task,
         "completed": p.completed, "created_at": _dt(p.created_at)}
        for p in plans
    ]

    # Problems
    probs = (await db.execute(select(ProblemRecord).order_by(ProblemRecord.id))).scalars().all()
    problems = [
        {"id": p.id, "question": p.question, "solution": p.solution,
         "subject": p.subject, "created_at": _dt(p.created_at)}
        for p in probs
    ]

    # Exam questions
    eqs = (await db.execute(select(ExamQuestion).order_by(ExamQuestion.id))).scalars().all()
    exam_questions = [
        {"id": q.id, "title": q.title, "subject": q.subject, "year": q.year,
         "question": q.question, "answer": q.answer, "solution": q.solution,
         "tags": q.tags, "created_at": _dt(q.created_at)}
        for q in eqs
    ]

    # Exam attempts
    eas = (await db.execute(select(ExamAttempt).order_by(ExamAttempt.id))).scalars().all()
    exam_attempts = [
        {"id": a.id, "question_id": a.question_id, "user_answer": a.user_answer,
         "is_correct": a.is_correct, "created_at": _dt(a.created_at)}
        for a in eas
    ]

    # App settings
    settings_rows = (await db.execute(select(AppSetting))).scalars().all()
    app_settings = [
        {"key": s.key, "value": s.value}
        for s in settings_rows
    ]

    # Study sessions
    sessions = (await db.execute(select(StudySession).order_by(StudySession.id))).scalars().all()
    study_sessions = [
        {
            "id": s.id, "subject": s.subject or "", "note": s.note or "",
            "started_at": _dt(s.started_at), "ended_at": _dt(s.ended_at),
            "duration_minutes": s.duration_minutes or 0,
            "created_at": _dt(s.created_at),
        }
        for s in sessions
    ]

    result = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": BACKUP_SCHEMA_VERSION,
        "materials": materials,
        "material_chunks_count": chunks_count,
        "chat_history": chat_history,
        "error_book": error_book,
        "study_plans": study_plans,
        "problems": problems,
        "exam_questions": exam_questions,
        "exam_attempts": exam_attempts,
        "app_settings": app_settings,
        "study_sessions": study_sessions,
    }

    # Log the operation
    import json as _json
    summary = {k: len(v) if isinstance(v, list) else v for k, v in result.items() if k not in ("exported_at", "version")}
    log = OperationLog(operation_type="export_json", file_type="json", result_summary=_json.dumps(summary, ensure_ascii=False))
    db.add(log)
    await db.commit()

    return JSONResponse(content=result)


# ── Allowed extensions (same set used by material upload) ──
_ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}


@router.get("/zip")
async def export_zip(db: AsyncSession = Depends(get_db)):
    """Export a complete backup ZIP containing backup.json, manifest.json,
    and all uploaded files referenced by materials."""
    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)
    exported_at = datetime.now(timezone.utc).isoformat()

    # ── Collect backup.json content (reuse the same query logic) ──
    # NOTE: ZIP backup.json includes stored_filename/status/error_message
    # so that import_zip can restore files and track material state.
    # This differs from the lightweight JSON export which omits these.
    mats = (await db.execute(select(Material).order_by(Material.id))).scalars().all()
    materials = []
    files_to_pack: list[tuple[str, str]] = []  # (stored_filename, archive_path)
    for m in mats:
        materials.append({
            "id": m.id,
            "filename": m.filename,
            "file_type": m.file_type,
            "stored_filename": m.stored_filename or "",
            "status": m.status or "ready",
            "error_message": m.error_message or "",
            "content_length": len(m.content) if m.content else 0,
            "created_at": _dt(m.created_at),
        })
        if m.stored_filename:
            ext = os.path.splitext(m.stored_filename)[1].lower()
            if ext in _ALLOWED_EXTS:
                src = os.path.join(upload_dir, m.stored_filename)
                if os.path.isfile(src):
                    files_to_pack.append((m.stored_filename, f"uploads/{m.stored_filename}"))

    chunks_count = (await db.execute(select(func.count()).select_from(MaterialChunk))).scalar() or 0

    chats = (await db.execute(select(ChatHistory).order_by(ChatHistory.id))).scalars().all()
    chat_history = [
        {"id": c.id, "conversation_id": c.conversation_id or "", "question": c.question, "answer": c.answer, "created_at": _dt(c.created_at)}
        for c in chats
    ]

    errors = (await db.execute(select(ErrorBook).order_by(ErrorBook.id))).scalars().all()
    error_book = [
        {
            "id": e.id, "subject": e.subject, "chapter": e.chapter,
            "knowledge_point": e.knowledge_point, "question": e.question,
            "user_answer": e.user_answer, "correct_answer": e.correct_answer,
            "error_type": e.error_type, "error_reason": e.error_reason,
            "correct_approach": e.correct_approach, "review_suggestion": e.review_suggestion,
            "tags": e.tags, "next_review_date": e.next_review_date,
            "mastered": e.mastered, "review_count": e.review_count,
            "created_at": _dt(e.created_at),
        }
        for e in errors
    ]

    plans = (await db.execute(select(StudyPlan).order_by(StudyPlan.id))).scalars().all()
    study_plans = [
        {"id": p.id, "date": p.date, "subject": p.subject, "task": p.task,
         "completed": p.completed, "created_at": _dt(p.created_at)}
        for p in plans
    ]

    probs = (await db.execute(select(ProblemRecord).order_by(ProblemRecord.id))).scalars().all()
    problems = [
        {"id": p.id, "question": p.question, "solution": p.solution,
         "subject": p.subject, "created_at": _dt(p.created_at)}
        for p in probs
    ]

    eqs = (await db.execute(select(ExamQuestion).order_by(ExamQuestion.id))).scalars().all()
    exam_questions = [
        {"id": q.id, "title": q.title, "subject": q.subject, "year": q.year,
         "question": q.question, "answer": q.answer, "solution": q.solution,
         "tags": q.tags, "created_at": _dt(q.created_at)}
        for q in eqs
    ]

    eas = (await db.execute(select(ExamAttempt).order_by(ExamAttempt.id))).scalars().all()
    exam_attempts = [
        {"id": a.id, "question_id": a.question_id, "user_answer": a.user_answer,
         "is_correct": a.is_correct, "created_at": _dt(a.created_at)}
        for a in eas
    ]

    # App settings (review intervals, etc.)
    settings_rows = (await db.execute(select(AppSetting))).scalars().all()
    app_settings = [
        {"key": s.key, "value": s.value}
        for s in settings_rows
    ]

    # Study sessions
    sessions = (await db.execute(select(StudySession).order_by(StudySession.id))).scalars().all()
    study_sessions = [
        {
            "id": s.id, "subject": s.subject or "", "note": s.note or "",
            "started_at": _dt(s.started_at), "ended_at": _dt(s.ended_at),
            "duration_minutes": s.duration_minutes or 0,
            "created_at": _dt(s.created_at),
        }
        for s in sessions
    ]

    backup_json = {
        "exported_at": exported_at,
        "version": BACKUP_SCHEMA_VERSION,
        "materials": materials,
        "material_chunks_count": chunks_count,
        "chat_history": chat_history,
        "error_book": error_book,
        "study_plans": study_plans,
        "problems": problems,
        "exam_questions": exam_questions,
        "exam_attempts": exam_attempts,
        "app_settings": app_settings,
        "study_sessions": study_sessions,
    }

    # ── Build manifest ──
    import json as _json
    file_manifest = []
    for stored, arc_path in files_to_pack:
        src = os.path.join(upload_dir, stored)
        try:
            size = os.path.getsize(src)
        except OSError:
            size = 0
        # Find original filename from materials list
        orig = next((m.filename for m in mats if m.stored_filename == stored), stored)
        file_manifest.append({
            "stored_filename": stored,
            "original_filename": orig,
            "size": size,
        })

    manifest = {
        "version": BACKUP_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "exported_at": exported_at,
        "backup_type": "full_zip",
        "file_count": len(file_manifest),
        "files": file_manifest,
    }

    # ── Build ZIP in memory ──
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("backup.json", _json.dumps(backup_json, ensure_ascii=False, indent=2))
        for stored, arc_path in files_to_pack:
            src = os.path.join(upload_dir, stored)
            zf.write(src, arc_path)
    buf.seek(0)

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Log the operation
    import json as _json
    log_summary = {"materials": len(materials), "files": len(file_manifest), "total_size": sum(f["size"] for f in file_manifest)}
    log = OperationLog(operation_type="export_zip", file_type="zip", result_summary=_json.dumps(log_summary, ensure_ascii=False))
    db.add(log)
    await db.commit()

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="math_agent_backup_{date_str}.zip"'},
    )
