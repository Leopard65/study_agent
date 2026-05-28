from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import (
    Material, ErrorBook, StudyPlan, ProblemRecord,
    ChatHistory, ExamQuestion, ExamAttempt,
)

router = APIRouter(prefix="/api/import", tags=["import"])

REQUIRED_KEYS = {"exported_at", "version", "materials", "error_book",
                 "study_plans", "problems", "exam_questions", "exam_attempts",
                 "chat_history", "material_chunks_count"}


def _validate(data: dict):
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise HTTPException(422, f"备份文件缺少字段: {', '.join(sorted(missing))}")


async def _exists(db: AsyncSession, model, *filters) -> bool:
    stmt = select(model.id).where(*filters).limit(1)
    r = await db.execute(stmt)
    return r.scalars().first() is not None


@router.post("/preview")
async def import_preview(data: dict, db: AsyncSession = Depends(get_db)):
    _validate(data)
    return {
        "version": data.get("version"),
        "exported_at": data.get("exported_at"),
        "materials_count": len(data.get("materials", [])),
        "error_book_count": len(data.get("error_book", [])),
        "study_plans_count": len(data.get("study_plans", [])),
        "problems_count": len(data.get("problems", [])),
        "chat_history_count": len(data.get("chat_history", [])),
        "exam_questions_count": len(data.get("exam_questions", [])),
        "exam_attempts_count": len(data.get("exam_attempts", [])),
    }


@router.post("/json")
async def import_json(data: dict, db: AsyncSession = Depends(get_db)):
    _validate(data)

    inserted = {"materials": 0, "error_book": 0, "study_plans": 0,
                "problems": 0, "chat_history": 0, "exam_questions": 0,
                "exam_attempts": 0}
    skipped = dict(inserted)

    # ── Materials (metadata only, no content) ──
    for m in data.get("materials", []):
        fn = m.get("filename", "")
        ft = m.get("file_type", "")
        if await _exists(db, Material, Material.filename == fn, Material.file_type == ft):
            skipped["materials"] += 1
            continue
        rec = Material(filename=fn, file_type=ft, content="", stored_filename="")
        db.add(rec)
        await db.flush()
        inserted["materials"] += 1

    # ── Error book ──
    for e in data.get("error_book", []):
        q = e.get("question", "")
        et = e.get("error_type", "")
        if not q:
            skipped["error_book"] += 1
            continue
        if await _exists(db, ErrorBook, ErrorBook.question == q, ErrorBook.error_type == et):
            skipped["error_book"] += 1
            continue
        rec = ErrorBook(
            subject=e.get("subject", ""), chapter=e.get("chapter", ""),
            knowledge_point=e.get("knowledge_point", ""), question=q,
            user_answer=e.get("user_answer", ""), correct_answer=e.get("correct_answer", ""),
            error_type=et, error_reason=e.get("error_reason", ""),
            correct_approach=e.get("correct_approach", ""),
            review_suggestion=e.get("review_suggestion", ""),
            tags=e.get("tags", ""), next_review_date=e.get("next_review_date", ""),
            mastered=e.get("mastered", False), review_count=e.get("review_count", 0),
        )
        db.add(rec)
        inserted["error_book"] += 1

    # ── Study plans ──
    for p in data.get("study_plans", []):
        d, s, t = p.get("date", ""), p.get("subject", ""), p.get("task", "")
        if not d or not s or not t:
            skipped["study_plans"] += 1
            continue
        if await _exists(db, StudyPlan, StudyPlan.date == d, StudyPlan.subject == s, StudyPlan.task == t):
            skipped["study_plans"] += 1
            continue
        rec = StudyPlan(date=d, subject=s, task=t, completed=p.get("completed", False))
        db.add(rec)
        inserted["study_plans"] += 1

    # ── Problems ──
    for p in data.get("problems", []):
        q = p.get("question", "")
        if not q:
            skipped["problems"] += 1
            continue
        if await _exists(db, ProblemRecord, ProblemRecord.question == q):
            skipped["problems"] += 1
            continue
        rec = ProblemRecord(question=q, solution=p.get("solution", ""), subject=p.get("subject", ""))
        db.add(rec)
        inserted["problems"] += 1

    # ── Chat history ──
    for c in data.get("chat_history", []):
        q, a = c.get("question", ""), c.get("answer", "")
        if not q or not a:
            skipped["chat_history"] += 1
            continue
        if await _exists(db, ChatHistory, ChatHistory.question == q, ChatHistory.answer == a):
            skipped["chat_history"] += 1
            continue
        rec = ChatHistory(question=q, answer=a)
        db.add(rec)
        inserted["chat_history"] += 1

    # ── Exam questions (must flush to get IDs for attempt mapping) ──
    old_id_to_new: dict[int, int] = {}
    for eq in data.get("exam_questions", []):
        title = eq.get("title", "")
        question = eq.get("question", "")
        if not title or not question:
            skipped["exam_questions"] += 1
            continue
        # Check duplicate by title + question
        dup = await db.execute(
            select(ExamQuestion.id).where(
                ExamQuestion.title == title, ExamQuestion.question == question
            ).limit(1)
        )
        existing_id = dup.scalars().first()
        if existing_id is not None:
            skipped["exam_questions"] += 1
            if eq.get("id"):
                old_id_to_new[eq["id"]] = existing_id
            continue
        rec = ExamQuestion(
            title=title, subject=eq.get("subject", ""), year=eq.get("year", ""),
            question=question, answer=eq.get("answer", ""), solution=eq.get("solution", ""),
            tags=eq.get("tags", ""),
        )
        db.add(rec)
        await db.flush()
        inserted["exam_questions"] += 1
        if eq.get("id"):
            old_id_to_new[eq["id"]] = rec.id

    # ── Exam attempts (map question_id) ──
    for ea in data.get("exam_attempts", []):
        old_qid = ea.get("question_id")
        new_qid = old_id_to_new.get(old_qid) if old_qid else None
        if new_qid is None:
            # Try to find existing question by ID directly
            if old_qid and await _exists(db, ExamQuestion, ExamQuestion.id == old_qid):
                new_qid = old_qid
            else:
                skipped["exam_attempts"] += 1
                continue
        rec = ExamAttempt(
            question_id=new_qid,
            user_answer=ea.get("user_answer", ""),
            is_correct=ea.get("is_correct", False),
        )
        db.add(rec)
        inserted["exam_attempts"] += 1

    await db.commit()
    return {"inserted": inserted, "skipped": skipped}
