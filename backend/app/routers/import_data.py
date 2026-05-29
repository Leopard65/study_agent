import re
from fastapi import APIRouter, Depends, HTTPException, Query
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

VALID_STRATEGIES = {"skip", "overwrite", "keep_both"}


def _validate(data: dict):
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise HTTPException(422, f"备份文件缺少字段: {', '.join(sorted(missing))}")


async def _exists(db: AsyncSession, model, *filters) -> object | None:
    """Return existing record or None."""
    stmt = select(model).where(*filters).limit(1)
    r = await db.execute(stmt)
    return r.scalars().first()


def _make_copy_name(base: str, suffix: str = "(副本)", max_len: int = 200) -> str:
    """Generate a copy name like 'name (副本)' or 'name (副本2)'."""
    # If already has (副本N), increment
    m = re.match(r"^(.*?)\s*\(副本(\d*)\)\s*$", base)
    if m:
        core = m.group(1)
        n = int(m.group(2)) + 1 if m.group(2) else 2
    else:
        core = base
        n = 0
    result = f"{core} (副本)" if n == 0 else f"{core} (副本{n})"
    return result[:max_len]


_MAX_COPY_ITERATIONS = 1000


async def _next_copy_question(db: AsyncSession, base: str) -> str:
    """Generate a unique question text for keep_both."""
    candidate = _make_copy_name(base)
    for _ in range(_MAX_COPY_ITERATIONS):
        if not await _exists(db, ErrorBook, ErrorBook.question == candidate):
            return candidate
        candidate = _make_copy_name(candidate)
    return candidate


async def _next_copy_title(db: AsyncSession, base: str) -> str:
    """Generate a unique title for keep_both."""
    candidate = _make_copy_name(base)
    for _ in range(_MAX_COPY_ITERATIONS):
        if not await _exists(db, ExamQuestion, ExamQuestion.title == candidate):
            return candidate
        candidate = _make_copy_name(candidate)
    return candidate


@router.post("/preview")
async def import_preview(
    data: dict,
    strategy: str = Query(default="skip", description="冲突策略: skip / overwrite / keep_both"),
    db: AsyncSession = Depends(get_db),
):
    _validate(data)
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(422, f"无效的冲突策略 '{strategy}'，支持: skip, overwrite, keep_both")

    modules = [
        ("materials", Material, data.get("materials", []),
         lambda m: (Material.filename == m.get("filename", ""), Material.file_type == m.get("file_type", ""))),
        ("error_book", ErrorBook, data.get("error_book", []),
         lambda e: (ErrorBook.question == e.get("question", ""), ErrorBook.error_type == e.get("error_type", ""))),
        ("study_plans", StudyPlan, data.get("study_plans", []),
         lambda p: (StudyPlan.date == p.get("date", ""), StudyPlan.subject == p.get("subject", ""), StudyPlan.task == p.get("task", ""))),
        ("problems", ProblemRecord, data.get("problems", []),
         lambda p: (ProblemRecord.question == p.get("question", ""),)),
        ("chat_history", ChatHistory, data.get("chat_history", []),
         lambda c: (ChatHistory.question == c.get("question", ""), ChatHistory.answer == c.get("answer", ""))),
    ]

    stats: dict[str, dict] = {}
    conflict_samples: dict[str, list[str]] = {}

    for mod_name, model, items, filter_fn in modules:
        total = 0
        new_count = 0
        conflict_count = 0
        samples: list[str] = []
        for item in items:
            if mod_name == "error_book" and not item.get("question"):
                continue
            if mod_name == "study_plans" and (not item.get("date") or not item.get("subject") or not item.get("task")):
                continue
            if mod_name == "problems" and not item.get("question"):
                continue
            if mod_name == "chat_history" and (not item.get("question") or not item.get("answer")):
                continue
            total += 1
            filters = filter_fn(item)
            existing = await _exists(db, model, *filters)
            if existing:
                conflict_count += 1
                if len(samples) < 3:
                    label = item.get("question") or item.get("filename") or item.get("task") or ""
                    if label:
                        samples.append(label[:50])
            else:
                new_count += 1

        # Chat history is immutable: overwrite behaves like skip
        effective_strategy = strategy
        if mod_name == "chat_history" and strategy == "overwrite":
            effective_strategy = "skip"

        if effective_strategy == "skip":
            would_skip = conflict_count
            would_insert = new_count
            would_overwrite = 0
            would_keep_both = 0
        elif effective_strategy == "overwrite":
            would_skip = 0
            would_insert = new_count
            would_overwrite = conflict_count
            would_keep_both = 0
        else:  # keep_both
            would_skip = 0
            would_insert = new_count
            would_overwrite = 0
            would_keep_both = conflict_count

        stats[mod_name] = {
            "total": total,
            "new_count": new_count,
            "conflict_count": conflict_count,
            "would_insert": would_insert,
            "would_skip": would_skip,
            "would_overwrite": would_overwrite,
            "would_keep_both": would_keep_both,
        }
        if samples:
            conflict_samples[mod_name] = samples

    # Exam questions (special: title+question combo)
    eq_items = data.get("exam_questions", [])
    eq_total = 0
    eq_new = 0
    eq_conflict = 0
    eq_samples: list[str] = []
    for eq in eq_items:
        title = eq.get("title", "")
        question = eq.get("question", "")
        if not title or not question:
            continue
        eq_total += 1
        dup = await db.execute(
            select(ExamQuestion.id).where(
                ExamQuestion.title == title, ExamQuestion.question == question
            ).limit(1)
        )
        if dup.scalars().first() is not None:
            eq_conflict += 1
            if len(eq_samples) < 3:
                eq_samples.append(title[:50])
        else:
            eq_new += 1

    if strategy == "skip":
        eq_would_skip, eq_would_ow, eq_would_kb = eq_conflict, 0, 0
    elif strategy == "overwrite":
        eq_would_skip, eq_would_ow, eq_would_kb = 0, eq_conflict, 0
    else:
        eq_would_skip, eq_would_ow, eq_would_kb = 0, 0, eq_conflict

    stats["exam_questions"] = {
        "total": eq_total, "new_count": eq_new, "conflict_count": eq_conflict,
        "would_insert": eq_new, "would_skip": eq_would_skip,
        "would_overwrite": eq_would_ow, "would_keep_both": eq_would_kb,
    }
    if eq_samples:
        conflict_samples["exam_questions"] = eq_samples

    # Exam attempts: just count (no conflict detection, depends on question mapping)
    stats["exam_attempts"] = {
        "total": len(data.get("exam_attempts", [])),
        "new_count": len(data.get("exam_attempts", [])),
        "conflict_count": 0,
        "would_insert": len(data.get("exam_attempts", [])),
        "would_skip": 0, "would_overwrite": 0, "would_keep_both": 0,
    }

    total_conflicts = sum(s["conflict_count"] for s in stats.values())

    return {
        "version": data.get("version"),
        "exported_at": data.get("exported_at"),
        "strategy": strategy,
        "total_conflicts": total_conflicts,
        "modules": stats,
        "conflict_samples": conflict_samples,
        # Backward compat: keep old flat fields
        "materials_count": stats["materials"]["total"],
        "error_book_count": stats["error_book"]["total"],
        "study_plans_count": stats["study_plans"]["total"],
        "problems_count": stats["problems"]["total"],
        "chat_history_count": stats["chat_history"]["total"],
        "exam_questions_count": stats["exam_questions"]["total"],
        "exam_attempts_count": stats["exam_attempts"]["total"],
    }


@router.post("/json")
async def import_json(
    data: dict,
    strategy: str = Query(default="skip", description="冲突策略: skip / overwrite / keep_both"),
    db: AsyncSession = Depends(get_db),
):
    _validate(data)
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(422, f"无效的冲突策略 '{strategy}'，支持: skip, overwrite, keep_both")

    inserted = {"materials": 0, "error_book": 0, "study_plans": 0,
                "problems": 0, "chat_history": 0, "exam_questions": 0,
                "exam_attempts": 0}
    skipped = dict(inserted)
    overwritten = dict(inserted)
    kept_both = dict(inserted)

    # ── Materials (metadata only, no content) ──
    for m in data.get("materials", []):
        fn = m.get("filename", "")
        ft = m.get("file_type", "")
        existing = await _exists(db, Material, Material.filename == fn, Material.file_type == ft)
        if existing:
            if strategy == "skip":
                skipped["materials"] += 1
            elif strategy == "overwrite":
                existing.content = ""
                existing.stored_filename = ""
                overwritten["materials"] += 1
            else:  # keep_both
                rec = Material(filename=_make_copy_name(fn), file_type=ft, content="", stored_filename="")
                db.add(rec)
                kept_both["materials"] += 1
        else:
            rec = Material(filename=fn, file_type=ft, content="", stored_filename="")
            db.add(rec)
            inserted["materials"] += 1
    await db.flush()

    # ── Error book ──
    for e in data.get("error_book", []):
        q = e.get("question", "")
        et = e.get("error_type", "")
        if not q:
            skipped["error_book"] += 1
            continue
        existing = await _exists(db, ErrorBook, ErrorBook.question == q, ErrorBook.error_type == et)
        if existing:
            if strategy == "skip":
                skipped["error_book"] += 1
            elif strategy == "overwrite":
                existing.subject = e.get("subject", "")
                existing.chapter = e.get("chapter", "")
                existing.knowledge_point = e.get("knowledge_point", "")
                existing.user_answer = e.get("user_answer", "")
                existing.correct_answer = e.get("correct_answer", "")
                existing.error_reason = e.get("error_reason", "")
                existing.correct_approach = e.get("correct_approach", "")
                existing.review_suggestion = e.get("review_suggestion", "")
                existing.tags = e.get("tags", "")
                existing.next_review_date = e.get("next_review_date", "")
                existing.mastered = e.get("mastered", False)
                existing.review_count = e.get("review_count", 0)
                overwritten["error_book"] += 1
            else:  # keep_both
                new_q = await _next_copy_question(db, q)
                rec = ErrorBook(
                    subject=e.get("subject", ""), chapter=e.get("chapter", ""),
                    knowledge_point=e.get("knowledge_point", ""), question=new_q,
                    user_answer=e.get("user_answer", ""), correct_answer=e.get("correct_answer", ""),
                    error_type=et, error_reason=e.get("error_reason", ""),
                    correct_approach=e.get("correct_approach", ""),
                    review_suggestion=e.get("review_suggestion", ""),
                    tags=e.get("tags", ""), next_review_date=e.get("next_review_date", ""),
                    mastered=e.get("mastered", False), review_count=e.get("review_count", 0),
                )
                db.add(rec)
                kept_both["error_book"] += 1
        else:
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
        existing = await _exists(db, StudyPlan, StudyPlan.date == d, StudyPlan.subject == s, StudyPlan.task == t)
        if existing:
            if strategy == "skip":
                skipped["study_plans"] += 1
            elif strategy == "overwrite":
                existing.completed = p.get("completed", False)
                overwritten["study_plans"] += 1
            else:  # keep_both
                rec = StudyPlan(date=d, subject=s, task=_make_copy_name(t, max_len=5000),
                                completed=p.get("completed", False))
                db.add(rec)
                kept_both["study_plans"] += 1
        else:
            rec = StudyPlan(date=d, subject=s, task=t, completed=p.get("completed", False))
            db.add(rec)
            inserted["study_plans"] += 1

    # ── Problems ──
    for p in data.get("problems", []):
        q = p.get("question", "")
        if not q:
            skipped["problems"] += 1
            continue
        existing = await _exists(db, ProblemRecord, ProblemRecord.question == q)
        if existing:
            if strategy == "skip":
                skipped["problems"] += 1
            elif strategy == "overwrite":
                existing.solution = p.get("solution", "")
                existing.subject = p.get("subject", "")
                overwritten["problems"] += 1
            else:  # keep_both
                rec = ProblemRecord(question=_make_copy_name(q, max_len=10000),
                                    solution=p.get("solution", ""), subject=p.get("subject", ""))
                db.add(rec)
                kept_both["problems"] += 1
        else:
            rec = ProblemRecord(question=q, solution=p.get("solution", ""), subject=p.get("subject", ""))
            db.add(rec)
            inserted["problems"] += 1

    # ── Chat history ──
    for c in data.get("chat_history", []):
        q, a = c.get("question", ""), c.get("answer", "")
        if not q or not a:
            skipped["chat_history"] += 1
            continue
        existing = await _exists(db, ChatHistory, ChatHistory.question == q, ChatHistory.answer == a)
        if existing:
            if strategy == "skip":
                skipped["chat_history"] += 1
            elif strategy == "overwrite":
                # Chat history is immutable, skip on overwrite
                skipped["chat_history"] += 1
            else:  # keep_both
                rec = ChatHistory(question=_make_copy_name(q), answer=a)
                db.add(rec)
                kept_both["chat_history"] += 1
        else:
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
        dup = await db.execute(
            select(ExamQuestion.id).where(
                ExamQuestion.title == title, ExamQuestion.question == question
            ).limit(1)
        )
        existing_id = dup.scalars().first()
        if existing_id is not None:
            if strategy == "skip":
                skipped["exam_questions"] += 1
            elif strategy == "overwrite":
                existing_rec = await db.get(ExamQuestion, existing_id)
                if existing_rec:
                    existing_rec.subject = eq.get("subject", "")
                    existing_rec.year = eq.get("year", "")
                    existing_rec.answer = eq.get("answer", "")
                    existing_rec.solution = eq.get("solution", "")
                    existing_rec.tags = eq.get("tags", "")
                    overwritten["exam_questions"] += 1
            else:  # keep_both
                new_title = await _next_copy_title(db, title)
                rec = ExamQuestion(
                    title=new_title, subject=eq.get("subject", ""), year=eq.get("year", ""),
                    question=question, answer=eq.get("answer", ""), solution=eq.get("solution", ""),
                    tags=eq.get("tags", ""),
                )
                db.add(rec)
                await db.flush()
                kept_both["exam_questions"] += 1
                if eq.get("id"):
                    old_id_to_new[eq["id"]] = rec.id
                continue
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
    return {
        "inserted": inserted,
        "skipped": skipped,
        "overwritten": overwritten,
        "kept_both": kept_both,
    }
