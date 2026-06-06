import json
import os
import re
import zipfile
import io
from datetime import datetime as _dt_mod, timezone as _tz
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.config import get_settings
from app.models import (
    Material, ErrorBook, StudyPlan, ProblemRecord,
    ChatHistory, ExamQuestion, ExamAttempt, MaterialParseJob, OperationLog,
    AppSetting, StudySession,
)
from app.routers.settings import validate_review_intervals, SETTING_KEY

router = APIRouter(prefix="/api/import", tags=["import"])

REQUIRED_KEYS = {"exported_at", "version", "materials", "error_book",
                 "study_plans", "problems", "exam_questions", "exam_attempts",
                 "chat_history", "material_chunks_count"}

VALID_STRATEGIES = {"skip", "overwrite", "keep_both"}

# Whitelist of app_settings keys that can be imported
_SETTINGS_WHITELIST = {"review_intervals"}


def _validate(data: dict):
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise HTTPException(422, f"备份文件缺少字段: {', '.join(sorted(missing))}")


async def _exists(db: AsyncSession, model, *filters) -> object | None:
    """Return existing record or None."""
    stmt = select(model).where(*filters).limit(1)
    r = await db.execute(stmt)
    return r.scalars().first()


def _make_copy_name(base: str, suffix: str = "(副本)", max_len: int | None = None) -> str:
    """Generate a copy name like 'name (副本)' or 'name (副本2)'."""
    # If already has (副本N), increment
    m = re.match(rf"^(.*?)\s*{re.escape(suffix[:-1])}(\d*)\)\s*$", base)
    if m:
        core = m.group(1)
        n = int(m.group(2)) + 1 if m.group(2) else 2
    else:
        core = base
        n = 0
    result = f"{core} {suffix}" if n == 0 else f"{core} {suffix[:-1]}{n})"
    if max_len is not None and len(result) > max_len:
        suffix_text = f" {suffix}" if n == 0 else f" {suffix[:-1]}{n})"
        result = f"{core[:max(0, max_len - len(suffix_text))]}{suffix_text}"
    return result


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
    candidate = _make_copy_name(base, max_len=500)
    for _ in range(_MAX_COPY_ITERATIONS):
        if not await _exists(db, ExamQuestion, ExamQuestion.title == candidate):
            return candidate
        candidate = _make_copy_name(candidate)
    return candidate


def _normalize_utc(dt: _dt_mod) -> _dt_mod:
    """Normalize a datetime to UTC-aware. Naive datetimes are assumed UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_tz.utc)
    return dt.astimezone(_tz.utc)


def _parse_backup_datetime(raw) -> _dt_mod | None:
    """Parse a backup datetime string/object to a UTC-aware datetime.
    Returns None if parsing fails."""
    if raw is None:
        return None
    if isinstance(raw, _dt_mod):
        return _normalize_utc(raw)
    if isinstance(raw, str):
        try:
            return _normalize_utc(_dt_mod.fromisoformat(raw))
        except (ValueError, TypeError):
            return None
    return None


def _validate_setting_value(key: str, value: str) -> str | None:
    """Validate a setting value. Returns error message or None if valid."""
    if key == SETTING_KEY:
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return "review_intervals 值不是合法 JSON"
        err = validate_review_intervals(parsed)
        return err
    return None


async def _import_app_settings(db: AsyncSession, data: dict, strategy: str) -> tuple[int, int, list[str]]:
    """Import app_settings from backup. Returns (imported, skipped, warnings)."""
    imported = 0
    skipped = 0
    warnings: list[str] = []
    for s in data.get("app_settings", []):
        key = s.get("key", "")
        value = s.get("value", "")
        if not key:
            continue
        # Whitelist check
        if key not in _SETTINGS_WHITELIST:
            skipped += 1
            continue
        # Validate value
        err = _validate_setting_value(key, value)
        if err:
            warnings.append(f"{key}: {err}")
            skipped += 1
            continue
        existing = await db.get(AppSetting, key)
        if existing:
            if strategy == "overwrite":
                existing.value = value
                imported += 1
            else:
                skipped += 1
        else:
            db.add(AppSetting(key=key, value=value))
            imported += 1
    return imported, skipped, warnings


_SESSION_SUBJECT_MAX = 100
_SESSION_NOTE_MAX = 5000


async def _import_study_sessions(
    db: AsyncSession, data: dict, strategy: str
) -> tuple[int, int, int, int, list[str]]:
    """Import study_sessions from backup.

    Returns (imported, skipped, invalid, kept_both_count, warnings).

    Validation rules:
    - started_at: required, must parse to a datetime. Otherwise → invalid.
    - ended_at < started_at: → invalid.
    - Active session (ended_at=None): force-end at now_utc. If started_at is
      in the future (so ended_at < started_at after force-end), → invalid.
    - duration_minutes: must be a plain int >= 0. Reject bool, float, str,
      negative, None/missing. If int exceeds actual elapsed minutes, cap and
      warn.
    - subject / note: non-string → coerce to "". Truncate if over limit.
    - Duplicate detection: same started_at + subject + note.
    """
    imported = 0
    skipped = 0
    invalid = 0
    kept_both_count = 0
    warnings: list[str] = []
    now_utc = _normalize_utc(_dt_mod.now(_tz.utc))

    for idx, s in enumerate(data.get("study_sessions", [])):
        # ── started_at ──
        started_dt = _parse_backup_datetime(s.get("started_at"))
        if started_dt is None:
            invalid += 1
            warnings.append(f"会话#{idx + 1}: started_at 缺失或无法解析，已跳过")
            continue

        # ── ended_at + active session handling ──
        ended_dt = _parse_backup_datetime(s.get("ended_at"))
        if ended_dt is None:
            # Active session → force-end at import time
            ended_dt = now_utc
            # If started_at is in the future, ended_at < started_at → invalid
            if ended_dt < started_dt:
                invalid += 1
                warnings.append(f"会话#{idx + 1}: 活跃会话的 started_at 在未来，已跳过")
                continue

        # ended_at < started_at check (for non-active sessions)
        if ended_dt < started_dt:
            invalid += 1
            warnings.append(f"会话#{idx + 1}: ended_at 早于 started_at，已跳过")
            continue

        # ── duration_minutes: strict int validation ──
        raw_dur = s.get("duration_minutes")
        if raw_dur is None or isinstance(raw_dur, bool) or (isinstance(raw_dur, int) and raw_dur == 0):
            # None, bool, or zero → recalculate from timestamps
            delta = ended_dt - started_dt
            duration = max(0, int(delta.total_seconds() // 60))
        elif isinstance(raw_dur, int) and not isinstance(raw_dur, bool):
            if raw_dur < 0:
                warnings.append(f"会话#{idx + 1}: duration_minutes 为负数({raw_dur})，已重算")
                delta = ended_dt - started_dt
                duration = max(0, int(delta.total_seconds() // 60))
            else:
                # Cap to actual elapsed minutes if inflated
                delta = ended_dt - started_dt
                actual_minutes = max(0, int(delta.total_seconds() // 60))
                if raw_dur > actual_minutes + 1:  # +1 tolerance for rounding
                    warnings.append(
                        f"会话#{idx + 1}: duration_minutes={raw_dur} 超过实际时长{actual_minutes}分钟，已截断"
                    )
                    duration = actual_minutes
                else:
                    duration = raw_dur
        elif isinstance(raw_dur, float):
            # Float → recalculate, warn
            warnings.append(f"会话#{idx + 1}: duration_minutes 为浮点数({raw_dur})，已重算")
            delta = ended_dt - started_dt
            duration = max(0, int(delta.total_seconds() // 60))
        elif isinstance(raw_dur, str):
            # String → try parse, otherwise recalculate
            try:
                parsed = int(raw_dur)
                if parsed < 0:
                    raise ValueError
                delta = ended_dt - started_dt
                actual_minutes = max(0, int(delta.total_seconds() // 60))
                if parsed > actual_minutes + 1:
                    warnings.append(
                        f"会话#{idx + 1}: duration_minutes={parsed} 超过实际时长{actual_minutes}分钟，已截断"
                    )
                    duration = actual_minutes
                else:
                    duration = parsed
            except (ValueError, TypeError):
                warnings.append(f"会话#{idx + 1}: duration_minutes='{raw_dur}' 无法解析，已重算")
                delta = ended_dt - started_dt
                duration = max(0, int(delta.total_seconds() // 60))
        else:
            delta = ended_dt - started_dt
            duration = max(0, int(delta.total_seconds() // 60))

        # ── subject / note: type coercion + truncation ──
        raw_subject = s.get("subject", "")
        if isinstance(raw_subject, str):
            subject = raw_subject
        else:
            subject = ""
            warnings.append(f"会话#{idx + 1}: subject 非字符串，已转为空")

        if len(subject) > _SESSION_SUBJECT_MAX:
            warnings.append(f"会话#{idx + 1}: subject 超长({len(subject)}字符)，已截断到{_SESSION_SUBJECT_MAX}")
            subject = subject[:_SESSION_SUBJECT_MAX]

        raw_note = s.get("note", "")
        if isinstance(raw_note, str):
            note = raw_note
        else:
            note = ""
            warnings.append(f"会话#{idx + 1}: note 非字符串，已转为空")

        if len(note) > _SESSION_NOTE_MAX:
            warnings.append(f"会话#{idx + 1}: note 超长({len(note)}字符)，已截断到{_SESSION_NOTE_MAX}")
            note = note[:_SESSION_NOTE_MAX]

        # ── Duplicate detection: match on started_at + subject + note ──
        dup = await db.execute(
            select(StudySession.id).where(
                StudySession.started_at == started_dt,
                StudySession.subject == subject,
                StudySession.note == note,
            ).limit(1)
        )
        existing_id = dup.scalars().first()

        if existing_id is not None:
            if strategy == "skip":
                skipped += 1
            elif strategy == "overwrite":
                existing_rec = await db.get(StudySession, existing_id)
                if existing_rec:
                    existing_rec.ended_at = ended_dt
                    existing_rec.duration_minutes = duration
                    existing_rec.note = note
                    imported += 1
                else:
                    skipped += 1
            else:  # keep_both
                rec = StudySession(
                    subject=subject, note=note,
                    started_at=started_dt, ended_at=ended_dt,
                    duration_minutes=duration,
                )
                db.add(rec)
                kept_both_count += 1
        else:
            rec = StudySession(
                subject=subject, note=note,
                started_at=started_dt, ended_at=ended_dt,
                duration_minutes=duration,
            )
            db.add(rec)
            imported += 1

    return imported, skipped, invalid, kept_both_count, warnings


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

    # ── App settings preview (review intervals) ──
    settings_total = 0
    settings_new = 0
    settings_conflict = 0
    settings_invalid = 0
    for s in data.get("app_settings", []):
        key = s.get("key", "")
        value = s.get("value", "")
        if not key or key not in _SETTINGS_WHITELIST:
            continue
        err = _validate_setting_value(key, value)
        if err:
            settings_invalid += 1
            continue
        settings_total += 1
        existing = await db.get(AppSetting, key)
        if existing:
            settings_conflict += 1
        else:
            settings_new += 1

    stats["app_settings"] = {
        "total": settings_total, "new_count": settings_new, "conflict_count": settings_conflict,
        "would_insert": settings_new if strategy in ("skip", "keep_both") else settings_new,
        "would_skip": settings_conflict if strategy in ("skip", "keep_both") else 0,
        "would_overwrite": settings_conflict if strategy == "overwrite" else 0,
        "would_keep_both": 0,  # settings are singleton, no keep_both
    }
    total_conflicts += settings_conflict

    # ── Study sessions preview (with validation) ──
    sess_total = 0
    sess_new = 0
    sess_conflict = 0
    sess_invalid = 0
    now_utc = _normalize_utc(_dt_mod.now(_tz.utc))
    for s in data.get("study_sessions", []):
        started_dt = _parse_backup_datetime(s.get("started_at"))
        if started_dt is None:
            sess_invalid += 1
            continue
        ended_dt = _parse_backup_datetime(s.get("ended_at"))
        if ended_dt is None:
            ended_dt = now_utc
            if ended_dt < started_dt:
                sess_invalid += 1
                continue
        if ended_dt < started_dt:
            sess_invalid += 1
            continue
        # Validate duration_minutes type
        raw_dur = s.get("duration_minutes")
        if raw_dur is not None and not isinstance(raw_dur, int) and not isinstance(raw_dur, (type(None),)):
            pass  # allow through preview, will be corrected on import
        sess_total += 1
        subject = s.get("subject", "") if isinstance(s.get("subject"), str) else ""
        note = s.get("note", "") if isinstance(s.get("note"), str) else ""
        dup = await db.execute(
            select(StudySession.id).where(
                StudySession.started_at == started_dt,
                StudySession.subject == subject,
                StudySession.note == note,
            ).limit(1)
        )
        if dup.scalars().first() is not None:
            sess_conflict += 1
        else:
            sess_new += 1

    if strategy == "skip":
        sess_skip, sess_ow, sess_kb = sess_conflict, 0, 0
    elif strategy == "overwrite":
        sess_skip, sess_ow, sess_kb = 0, sess_conflict, 0
    else:
        sess_skip, sess_ow, sess_kb = 0, 0, sess_conflict

    stats["study_sessions"] = {
        "total": sess_total, "new_count": sess_new, "conflict_count": sess_conflict,
        "would_insert": sess_new, "would_skip": sess_skip,
        "would_overwrite": sess_ow, "would_keep_both": sess_kb,
    }
    total_conflicts += sess_conflict

    return {
        "version": data.get("version"),
        "exported_at": data.get("exported_at"),
        "strategy": strategy,
        "total_conflicts": total_conflicts,
        "modules": stats,
        "conflict_samples": conflict_samples,
        "settings_invalid": settings_invalid,
        "sessions_invalid": sess_invalid,
        # Backward compat: keep old flat fields
        "materials_count": stats["materials"]["total"],
        "error_book_count": stats["error_book"]["total"],
        "study_plans_count": stats["study_plans"]["total"],
        "problems_count": stats["problems"]["total"],
        "chat_history_count": stats["chat_history"]["total"],
        "exam_questions_count": stats["exam_questions"]["total"],
        "exam_attempts_count": stats["exam_attempts"]["total"],
        "app_settings_count": settings_total,
        "study_sessions_count": sess_total,
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
                # JSON backup has no file content — preserve existing content and file
                overwritten["materials"] += 1
            else:  # keep_both
                rec = Material(filename=_make_copy_name(fn, max_len=500), file_type=ft, content="", stored_filename="")
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
                rec = ChatHistory(question=_make_copy_name(q), answer=a, conversation_id=c.get("conversation_id", ""))
                db.add(rec)
                kept_both["chat_history"] += 1
        else:
            rec = ChatHistory(question=q, answer=a, conversation_id=c.get("conversation_id", ""))
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

    # ── App settings (review intervals, etc.) — v0.3+ optional ──
    settings_imported, settings_skipped, settings_warnings = await _import_app_settings(db, data, strategy)

    # ── Study sessions — v0.3+ optional, idempotent ──
    sessions_imported, sessions_skipped, sessions_invalid, sessions_kept_both, sessions_warnings = await _import_study_sessions(db, data, strategy)
    # Merge sessions_kept_both into kept_both counter
    kept_both["study_sessions"] = sessions_kept_both

    await db.commit()

    result = {
        "inserted": inserted,
        "skipped": skipped,
        "overwritten": overwritten,
        "kept_both": kept_both,
        "settings_imported": settings_imported,
        "settings_skipped": settings_skipped,
        "sessions_imported": sessions_imported,
        "sessions_skipped": sessions_skipped,
        "sessions_invalid": sessions_invalid,
    }
    if settings_warnings:
        result["settings_warnings"] = settings_warnings
    if sessions_warnings:
        result["sessions_warnings"] = sessions_warnings

    # Log the operation
    log_summary = {k: {m: v for m, v in counts.items() if v > 0} for k, counts in result.items() if isinstance(counts, dict)}
    log_summary["settings_imported"] = settings_imported
    log_summary["sessions_imported"] = sessions_imported
    log = OperationLog(operation_type="import_json", file_type="json", strategy=strategy,
                       result_summary=json.dumps(log_summary, ensure_ascii=False))
    db.add(log)
    await db.commit()

    return result


# ── ZIP import helpers ──

def _safe_zip_path(entry_name: str, upload_dir: str) -> str | None:
    """Validate a ZIP entry name and return the resolved absolute path
    under upload_dir. Returns None if the path is unsafe."""
    # Reject absolute paths, backslashes, and leading slash
    if os.path.isabs(entry_name) or "\\" in entry_name or entry_name.startswith("/"):
        return None
    # Reject any path component that is ".."
    parts = entry_name.split("/")
    if any(p == ".." or p == "" for p in parts):
        return None
    # Only allow uploads/<filename> with safe filename
    if len(parts) != 2 or parts[0] != "uploads":
        return None
    fname = parts[1]
    # Reject filenames with special characters or path separators
    if not fname or "/" in fname or "\\" in fname or ".." in fname:
        return None
    # Must have an allowed extension
    ext = os.path.splitext(fname)[1].lower()
    _ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}
    if ext not in _ALLOWED_EXTS:
        return None
    resolved = os.path.normpath(os.path.join(upload_dir, fname))
    if not resolved.startswith(os.path.normpath(upload_dir) + os.sep) and resolved != os.path.normpath(upload_dir):
        return None
    return resolved


@router.post("/zip/preview")
async def import_zip_preview(
    file: UploadFile = File(...),
    strategy: str = Query(default="skip", description="冲突策略: skip / overwrite / keep_both"),
    db: AsyncSession = Depends(get_db),
):
    """Preview a ZIP backup: validate structure and return conflict analysis."""
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(422, f"无效的冲突策略 '{strategy}'，支持: skip, overwrite, keep_both")

    content = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(422, "无效的 ZIP 文件")

    names = set(zf.namelist())
    if "backup.json" not in names:
        raise HTTPException(422, "ZIP 缺少 backup.json")

    # Read and validate backup.json
    try:
        data = json.loads(zf.read("backup.json"))
    except Exception:
        raise HTTPException(422, "backup.json 格式错误")
    _validate(data)

    # Build manifest of files in ZIP
    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)
    zip_files: dict[str, int] = {}  # stored_filename -> size
    for entry in zf.infolist():
        if entry.is_dir():
            continue
        safe = _safe_zip_path(entry.filename, upload_dir)
        if safe:
            stored = os.path.basename(safe)
            zip_files[stored] = entry.file_size

    # Cross-reference with materials in backup
    materials_in_backup = data.get("materials", [])
    materials_with_files = [m for m in materials_in_backup if m.get("stored_filename") in zip_files]
    materials_without_files = [m for m in materials_in_backup if m.get("stored_filename") not in zip_files]

    # Conflict analysis for materials
    mat_total = 0
    mat_new = 0
    mat_conflict = 0
    mat_samples: list[str] = []
    for m in materials_in_backup:
        fn = m.get("filename", "")
        ft = m.get("file_type", "")
        if not fn:
            continue
        mat_total += 1
        existing = await _exists(db, Material, Material.filename == fn, Material.file_type == ft)
        if existing:
            mat_conflict += 1
            if len(mat_samples) < 3:
                mat_samples.append(fn[:50])
        else:
            mat_new += 1

    if strategy == "skip":
        mat_skip, mat_ow, mat_kb = mat_conflict, 0, 0
    elif strategy == "overwrite":
        mat_skip, mat_ow, mat_kb = 0, mat_conflict, 0
    else:
        mat_skip, mat_ow, mat_kb = 0, 0, mat_conflict

    # Reuse existing preview logic for other modules
    preview = await import_preview(data, strategy, db)
    # Override materials section with file-aware info
    preview["modules"]["materials"] = {
        "total": mat_total, "new_count": mat_new, "conflict_count": mat_conflict,
        "would_insert": mat_new, "would_skip": mat_skip,
        "would_overwrite": mat_ow, "would_keep_both": mat_kb,
    }
    if mat_samples:
        preview["conflict_samples"]["materials"] = mat_samples
    preview["materials_count"] = mat_total

    # ZIP-specific info
    preview["zip_info"] = {
        "file_count": len(zip_files),
        "materials_with_files": len(materials_with_files),
        "materials_without_files": len(materials_without_files),
        "total_file_size": sum(zip_files.values()),
        "manifest_present": "manifest.json" in names,
    }

    return preview


@router.post("/zip")
async def import_zip(
    file: UploadFile = File(...),
    strategy: str = Query(default="skip", description="冲突策略: skip / overwrite / keep_both"),
    db: AsyncSession = Depends(get_db),
):
    """Import from a ZIP backup: restore files and data."""
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(422, f"无效的冲突策略 '{strategy}'，支持: skip, overwrite, keep_both")

    content = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(422, "无效的 ZIP 文件")

    if "backup.json" not in set(zf.namelist()):
        raise HTTPException(422, "ZIP 缺少 backup.json")

    try:
        data = json.loads(zf.read("backup.json"))
    except Exception:
        raise HTTPException(422, "backup.json 格式错误")
    _validate(data)

    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)
    os.makedirs(upload_dir, exist_ok=True)

    # Build safe path map: stored_filename -> resolved absolute path
    safe_paths: dict[str, str] = {}
    for entry in zf.infolist():
        if entry.is_dir():
            continue
        safe = _safe_zip_path(entry.filename, upload_dir)
        if safe:
            stored = os.path.basename(safe)
            safe_paths[stored] = safe

    inserted = {"materials": 0, "error_book": 0, "study_plans": 0,
                "problems": 0, "chat_history": 0, "exam_questions": 0,
                "exam_attempts": 0}
    skipped = dict(inserted)
    overwritten = dict(inserted)
    kept_both = dict(inserted)
    files_restored = 0
    # Collect material IDs that need parse jobs (enqueued after commit)
    _pending_parse_ids: list[int] = []

    def _safe_delete_upload(stored_filename: str) -> None:
        """Delete a file from upload_dir with the same path-safety check
        used by materials.py._delete_uploaded_file."""
        if not stored_filename:
            return
        upload_abs = os.path.abspath(upload_dir)
        file_abs = os.path.abspath(os.path.join(upload_abs, stored_filename))
        try:
            if os.path.commonpath([upload_abs, file_abs]) != upload_abs:
                return
        except ValueError:
            return
        try:
            if os.path.isfile(file_abs):
                os.remove(file_abs)
        except OSError:
            pass

    def _generate_unique_stored(ext: str) -> str:
        """Generate a new UUID-based stored_filename that doesn't collide."""
        from uuid import uuid4
        return f"{uuid4().hex}{ext}"

    # ── Materials with file restoration ──
    for m in data.get("materials", []):
        fn = m.get("filename", "")
        ft = m.get("file_type", "")
        stored = m.get("stored_filename", "")
        has_file = stored in safe_paths

        existing = await _exists(db, Material, Material.filename == fn, Material.file_type == ft)
        if existing:
            if strategy == "skip":
                skipped["materials"] += 1
            elif strategy == "overwrite":
                if has_file:
                    # Update existing record
                    existing.status = "pending"
                    existing.error_message = ""
                    # Delete old file safely (using same check as materials.py)
                    old_stored = existing.stored_filename or ""
                    if old_stored and old_stored != stored:
                        _safe_delete_upload(old_stored)
                    existing.stored_filename = stored
                    existing.content = ""
                    # Write file from ZIP
                    try:
                        file_bytes = zf.read(f"uploads/{stored}")
                        with open(safe_paths[stored], "wb") as f:
                            f.write(file_bytes)
                        files_restored += 1
                    except (KeyError, OSError):
                        pass
                    _pending_parse_ids.append(existing.id)
                    job = MaterialParseJob(material_id=existing.id, status="pending", attempts=0)
                    db.add(job)
                else:
                    existing.status = "failed"
                    existing.error_message = "备份中无可恢复文件，需手动重新上传"
                    existing.content = ""
                overwritten["materials"] += 1
            else:  # keep_both
                new_fn = _make_copy_name(fn, max_len=500)
                # Generate a NEW stored_filename to avoid file-sharing
                # between original and copy (deleting one would orphan the other)
                ext = os.path.splitext(stored)[1] if stored else ft
                new_stored = _generate_unique_stored(ext)
                new_has_file = has_file
                if new_has_file:
                    rec = Material(filename=new_fn, file_type=ft, content="", stored_filename=new_stored, status="pending")
                    db.add(rec)
                    await db.flush()
                    try:
                        file_bytes = zf.read(f"uploads/{stored}")
                        dest = os.path.join(upload_dir, new_stored)
                        with open(dest, "wb") as f:
                            f.write(file_bytes)
                        files_restored += 1
                    except (KeyError, OSError):
                        pass
                    # Create parse job for the new material
                    job = MaterialParseJob(material_id=rec.id, status="pending", attempts=0)
                    db.add(job)
                    _pending_parse_ids.append(rec.id)
                else:
                    rec = Material(filename=new_fn, file_type=ft, content="", stored_filename="", status="failed", error_message="备份中无可恢复文件，需手动重新上传")
                    db.add(rec)
                    await db.flush()
                kept_both["materials"] += 1
        else:
            if has_file:
                rec = Material(filename=fn, file_type=ft, content="", stored_filename=stored, status="pending")
                db.add(rec)
                await db.flush()
                try:
                    file_bytes = zf.read(f"uploads/{stored}")
                    with open(safe_paths[stored], "wb") as f:
                        f.write(file_bytes)
                    files_restored += 1
                except (KeyError, OSError):
                    pass
                # Create parse job for new material
                job = MaterialParseJob(material_id=rec.id, status="pending", attempts=0)
                db.add(job)
                _pending_parse_ids.append(rec.id)
            else:
                rec = Material(filename=fn, file_type=ft, content="", stored_filename="", status="failed", error_message="备份中无可恢复文件，需手动重新上传")
                db.add(rec)
                await db.flush()
            inserted["materials"] += 1

    # ── Error book (same as JSON import) ──
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
            else:
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
            else:
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
            else:
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
                skipped["chat_history"] += 1
            else:
                rec = ChatHistory(question=_make_copy_name(q), answer=a, conversation_id=c.get("conversation_id", ""))
                db.add(rec)
                kept_both["chat_history"] += 1
        else:
            rec = ChatHistory(question=q, answer=a, conversation_id=c.get("conversation_id", ""))
            db.add(rec)
            inserted["chat_history"] += 1

    # ── Exam questions ──
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
            else:
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

    # ── Exam attempts ──
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

    # ── App settings (review intervals, etc.) — v0.3+ optional ──
    settings_imported, settings_skipped, settings_warnings = await _import_app_settings(db, data, strategy)

    # ── Study sessions — v0.3+ optional, idempotent ──
    sessions_imported, sessions_skipped, sessions_invalid, sessions_kept_both, sessions_warnings = await _import_study_sessions(db, data, strategy)
    kept_both["study_sessions"] = sessions_kept_both

    await db.commit()

    # Start parse worker for newly imported materials with files
    if _pending_parse_ids:
        try:
            from app.services.parse_worker import get_worker
            worker = get_worker()
            for mid in _pending_parse_ids:
                await worker.enqueue(mid)
        except Exception:
            pass  # parse worker not started yet or other non-critical error

    result = {
        "inserted": inserted,
        "skipped": skipped,
        "overwritten": overwritten,
        "kept_both": kept_both,
        "files_restored": files_restored,
        "settings_imported": settings_imported,
        "settings_skipped": settings_skipped,
        "sessions_imported": sessions_imported,
        "sessions_skipped": sessions_skipped,
        "sessions_invalid": sessions_invalid,
    }
    if settings_warnings:
        result["settings_warnings"] = settings_warnings
    if sessions_warnings:
        result["sessions_warnings"] = sessions_warnings

    # Log the operation
    log_summary = {k: {m: v for m, v in counts.items() if v > 0} for k, counts in
                   {"inserted": inserted, "skipped": skipped, "overwritten": overwritten, "kept_both": kept_both}.items()}
    log_summary["files_restored"] = files_restored
    log_summary["settings_imported"] = settings_imported
    log_summary["sessions_imported"] = sessions_imported
    log = OperationLog(operation_type="import_zip", file_type="zip", strategy=strategy,
                       result_summary=json.dumps(log_summary, ensure_ascii=False))
    db.add(log)
    await db.commit()

    return result
