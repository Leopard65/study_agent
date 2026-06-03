"""Review queue router: /api/review/queue and /api/review/{id}/action."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import ErrorBook
from app.utils.date import local_today, local_date_obj
from app.routers.settings import get_review_intervals

router = APIRouter(prefix="/api/review", tags=["review"])


# ── Request / Response schemas ──
class ReviewActionRequest(BaseModel):
    action: str  # mastered | again | postpone | skip


class ReviewQueueItem(BaseModel):
    id: int
    subject: str
    chapter: str
    knowledge_point: str
    question: str
    user_answer: str
    correct_answer: str
    error_type: str
    error_reason: str
    correct_approach: str
    review_suggestion: str
    tags: str
    next_review_date: str
    mastered: bool
    review_count: int
    due_days: int
    priority_reason: str


class WeakPoint(BaseModel):
    name: str
    count: int


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total_due: int
    total_unmastered: int
    weak_points: list[WeakPoint]
    today: str


class ReviewActionResult(BaseModel):
    ok: bool
    action: str
    error_id: int
    mastered: bool | None = None
    next_review_date: str | None = None
    review_count: int | None = None


# ── Priority helpers ──
def _priority_score(item: ErrorBook, kp_freq: dict[str, int], today: str) -> tuple:
    """Lower tuple = higher priority (shown first).

    Priority:
    1. Overdue items first (more overdue = higher), then today-due
    2. Knowledge-point frequency (higher errors = higher priority)
    3. Lower review_count = higher priority (less practiced)
    """
    nrd = item.next_review_date or ""
    if nrd and nrd <= today:
        overdue_days = (local_date_obj() - _parse_date(nrd)).days
    else:
        overdue_days = -365  # future items last

    kp = item.knowledge_point or ""
    freq = kp_freq.get(kp, 0)

    return (
        -overdue_days,       # more overdue → smaller (higher priority)
        -freq,               # higher freq → smaller (higher priority)
        item.review_count or 0,  # lower count → smaller (higher priority)
    )


def _parse_date(s: str):
    from datetime import date
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return local_date_obj()


def _due_days(item: ErrorBook, today: str) -> int:
    """Positive = overdue by N days, 0 = due today, negative = future."""
    nrd = item.next_review_date or ""
    if not nrd:
        return 0
    try:
        from datetime import date
        return (local_date_obj() - date.fromisoformat(nrd)).days
    except (ValueError, TypeError):
        return 0


def _priority_reason(item: ErrorBook, kp_freq: dict[str, int], today: str) -> str:
    dd = _due_days(item, today)
    parts: list[str] = []
    if dd > 0:
        parts.append(f"逾期 {dd} 天")
    elif dd == 0:
        parts.append("今日到期")

    kp = item.knowledge_point or ""
    if kp and kp_freq.get(kp, 0) >= 3:
        parts.append(f"知识点「{kp}」高频错误({kp_freq[kp]}次)")

    rc = item.review_count or 0
    if rc == 0:
        parts.append("首次复习")
    elif rc <= 2:
        parts.append(f"仅复习{rc}次")

    return "；".join(parts) if parts else "待复习"


@router.get("/queue", response_model=ReviewQueueResponse)
async def review_queue(db: AsyncSession = Depends(get_db)):
    today = local_today()

    # Fetch all unmastered with next_review_date <= today
    stmt = (
        select(ErrorBook)
        .where(
            ErrorBook.mastered == False,  # noqa: E712
            ErrorBook.next_review_date != "",
            ErrorBook.next_review_date <= today,
        )
    )
    result = await db.execute(stmt)
    due_items = list(result.scalars().all())

    # Stats
    total_due = len(due_items)

    unmastered_q = await db.execute(
        select(func.count()).where(ErrorBook.mastered == False)  # noqa: E712
    )
    total_unmastered = unmastered_q.scalar() or 0

    # Knowledge-point frequency among ALL unmastered errors
    all_unmastered_q = await db.execute(
        select(ErrorBook).where(ErrorBook.mastered == False)  # noqa: E712
    )
    all_unmastered = all_unmastered_q.scalars().all()

    kp_freq: dict[str, int] = {}
    for e in all_unmastered:
        kp = (e.knowledge_point or "").strip()
        if kp:
            kp_freq[kp] = kp_freq.get(kp, 0) + 1

    # Weak points: top 5 knowledge points by error count
    weak_points = sorted(
        [{"name": k, "count": v} for k, v in kp_freq.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    # Sort by priority
    due_items.sort(key=lambda e: _priority_score(e, kp_freq, today))

    # Build response
    items = []
    for e in due_items:
        items.append({
            "id": e.id,
            "subject": e.subject or "",
            "chapter": e.chapter or "",
            "knowledge_point": e.knowledge_point or "",
            "question": e.question or "",
            "user_answer": e.user_answer or "",
            "correct_answer": e.correct_answer or "",
            "error_type": e.error_type or "",
            "error_reason": e.error_reason or "",
            "correct_approach": e.correct_approach or "",
            "review_suggestion": e.review_suggestion or "",
            "tags": e.tags or "",
            "next_review_date": e.next_review_date or "",
            "mastered": e.mastered,
            "review_count": e.review_count or 0,
            "due_days": _due_days(e, today),
            "priority_reason": _priority_reason(e, kp_freq, today),
        })

    return {
        "items": items,
        "total_due": total_due,
        "total_unmastered": total_unmastered,
        "weak_points": weak_points,
        "today": today,
    }


@router.post("/{error_id}/action", response_model=ReviewActionResult)
async def review_action(error_id: int, req: ReviewActionRequest, db: AsyncSession = Depends(get_db)):
    record = await db.get(ErrorBook, error_id)
    if not record:
        raise HTTPException(404, "错题不存在")

    action = req.action
    if action not in ("mastered", "again", "postpone", "skip"):
        raise HTTPException(422, f"无效操作: {action}，可选: mastered, again, postpone, skip")

    if action == "skip":
        # Skip is a frontend-only concept; return the record unchanged
        return {"ok": True, "action": "skip", "error_id": error_id}

    if action == "mastered":
        # Idempotent: only advance review_count when transitioning false→true,
        # consistent with PATCH /api/errors/{id} logic.
        if not record.mastered:
            intervals = await get_review_intervals(db)
            record.review_count = (record.review_count or 0) + 1
            idx = min(record.review_count - 1, len(intervals) - 1)
            interval = intervals[idx]
            record.next_review_date = (local_date_obj() + timedelta(days=interval)).isoformat()
            record.mastered = True
        # else: already mastered — no-op, don't bump review_count or date

    elif action == "again":
        # "仍未掌握" — keep today as review date so it stays in the daily queue.
        # The frontend removes it from the current round, but on next load
        # it will reappear because next_review_date <= today.
        record.mastered = False
        record.next_review_date = local_today()

    elif action == "postpone":
        # "明日再来" — explicitly defer to tomorrow.
        record.mastered = False
        record.next_review_date = (local_date_obj() + timedelta(days=1)).isoformat()

    await db.commit()
    await db.refresh(record)

    return {
        "ok": True,
        "action": action,
        "error_id": error_id,
        "mastered": record.mastered,
        "next_review_date": record.next_review_date,
        "review_count": record.review_count,
    }
