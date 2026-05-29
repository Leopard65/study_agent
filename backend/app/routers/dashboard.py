from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import StudyPlan, Material, ErrorBook, ExamAttempt, StudySession
from app.schemas import DashboardStats
from app.utils.date import local_today, local_date_obj, utc_offset_modifier

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _local_date(col):
    """Convert a UTC-created_at column to local date using the configured timezone offset."""
    return func.date(col, utc_offset_modifier())


@router.get("", response_model=DashboardStats)
async def stats(db: AsyncSession = Depends(get_db)):
    today = local_today()

    # Today tasks
    today_tasks_q = await db.execute(select(func.count()).where(StudyPlan.date == today))
    today_tasks = today_tasks_q.scalar() or 0

    today_done_q = await db.execute(
        select(func.count()).where(StudyPlan.date == today, StudyPlan.completed == True)
    )
    today_completed = today_done_q.scalar() or 0

    # Materials count
    mat_q = await db.execute(select(func.count()).select_from(Material))
    total_materials = mat_q.scalar() or 0

    # Error book
    err_q = await db.execute(select(func.count()).select_from(ErrorBook))
    total_errors = err_q.scalar() or 0

    unmastered_q = await db.execute(select(func.count()).where(ErrorBook.mastered == False))
    unmastered_errors = unmastered_q.scalar() or 0

    # Today review errors: unmastered + next_review_date <= today
    review_q = await db.execute(
        select(func.count()).where(
            ErrorBook.mastered == False,
            ErrorBook.next_review_date != "",
            ErrorBook.next_review_date <= today,
        )
    )
    today_review_errors = review_q.scalar() or 0

    # Streak: count consecutive days with at least one completed task (single query)
    completed_dates_q = await db.execute(
        select(StudyPlan.date)
        .where(StudyPlan.completed.is_(True))
        .group_by(StudyPlan.date)
        .order_by(StudyPlan.date.desc())
    )
    completed_dates = {r[0] for r in completed_dates_q.fetchall()}
    streak = 0
    check_date = local_date_obj()
    for _ in range(365):
        if check_date.isoformat() in completed_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Today study minutes
    study_q = await db.execute(
        select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
            _local_date(StudySession.started_at) == today
        )
    )
    today_study_minutes = study_q.scalar() or 0

    return DashboardStats(
        today_tasks=today_tasks,
        today_completed=today_completed,
        total_materials=total_materials,
        total_errors=total_errors,
        unmastered_errors=unmastered_errors,
        streak_days=streak,
        today_review_errors=today_review_errors,
        today_study_minutes=today_study_minutes,
    )


@router.get("/trends")
async def trends(days: int = 7, db: AsyncSession = Depends(get_db)):
    if days not in (7, 30):
        raise HTTPException(422, "days 只允许 7 或 30")

    today = local_date_obj()
    start_date = (today - timedelta(days=days - 1)).isoformat()
    today_str = today.isoformat()

    # Plans: total + completed per date (single query)
    plans_q = await db.execute(
        select(
            StudyPlan.date,
            func.count().label("total"),
            func.count().filter(StudyPlan.completed.is_(True)).label("done"),
        )
        .where(StudyPlan.date >= start_date, StudyPlan.date <= today_str)
        .group_by(StudyPlan.date)
    )
    plans_map: dict[str, dict] = {}
    for r in plans_q.fetchall():
        plans_map[r[0]] = {"total": r[1], "done": r[2] or 0}

    # Errors created per date (single query)
    err_created_q = await db.execute(
        select(
            _local_date(ErrorBook.created_at).label("d"),
            func.count().label("cnt"),
        )
        .where(_local_date(ErrorBook.created_at) >= start_date)
        .group_by("d")
    )
    err_created_map: dict[str, int] = {r.d: r.cnt for r in err_created_q}

    # Errors due per date (single query)
    err_due_q = await db.execute(
        select(
            ErrorBook.next_review_date.label("d"),
            func.count().label("cnt"),
        )
        .where(
            ErrorBook.mastered.is_(False),
            ErrorBook.next_review_date >= start_date,
            ErrorBook.next_review_date <= today_str,
        )
        .group_by("d")
    )
    err_due_map: dict[str, int] = {r.d: r.cnt for r in err_due_q}

    # Exam attempts per date (single query)
    exam_q = await db.execute(
        select(
            _local_date(ExamAttempt.created_at).label("d"),
            func.count().label("total"),
            func.count().filter(ExamAttempt.is_correct.is_(True)).label("correct"),
        )
        .where(_local_date(ExamAttempt.created_at) >= start_date)
        .group_by("d")
    )
    exam_map: dict[str, dict] = {}
    for r in exam_q.fetchall():
        exam_map[r.d] = {"total": r.total, "correct": r.correct or 0}

    # Study minutes per date (single query)
    study_q = await db.execute(
        select(
            _local_date(StudySession.started_at).label("d"),
            func.coalesce(func.sum(StudySession.duration_minutes), 0).label("mins"),
        )
        .where(_local_date(StudySession.started_at) >= start_date)
        .group_by("d")
    )
    study_map: dict[str, int] = {r.d: r.mins for r in study_q}

    # Merge results by date
    items = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        p = plans_map.get(ds, {})
        ex = exam_map.get(ds, {})
        items.append({
            "date": ds,
            "plans_total": p.get("total", 0),
            "plans_completed": p.get("done", 0),
            "errors_created": err_created_map.get(ds, 0),
            "errors_review_due": err_due_map.get(ds, 0),
            "exam_attempts": ex.get("total", 0),
            "exam_correct": ex.get("correct", 0),
            "study_minutes": study_map.get(ds, 0),
        })

    return {"days": days, "items": items}
