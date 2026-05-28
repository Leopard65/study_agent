from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import (
    Material, MaterialChunk, ChatHistory, ErrorBook,
    StudyPlan, ProblemRecord, ExamQuestion, ExamAttempt,
)
from app.utils.date import local_today

router = APIRouter(prefix="/api/export", tags=["export"])


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
        {"id": c.id, "question": c.question, "answer": c.answer, "created_at": _dt(c.created_at)}
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

    return JSONResponse(content={
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "version": "0.2",
        "materials": materials,
        "material_chunks_count": chunks_count,
        "chat_history": chat_history,
        "error_book": error_book,
        "study_plans": study_plans,
        "problems": problems,
        "exam_questions": exam_questions,
        "exam_attempts": exam_attempts,
    })
