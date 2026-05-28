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

    # Streak: count consecutive days with at least one completed task
    streak = 0
    check_date = local_date_obj()
    for _ in range(365):
        d = check_date.isoformat()
        q = await db.execute(
            select(func.count()).where(StudyPlan.date == d, StudyPlan.completed == True)
        )
        if q.scalar():
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
    items = []

    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        ds = d.isoformat()

        # Plans
        plan_total_q = await db.execute(
            select(func.count()).where(StudyPlan.date == ds)
        )
        plan_done_q = await db.execute(
            select(func.count()).where(StudyPlan.date == ds, StudyPlan.completed == True)
        )

        # Errors created on this date (UTC created_at → local date)
        err_created_q = await db.execute(
            select(func.count()).where(
                _local_date(ErrorBook.created_at) == ds
            )
        )

        # Errors with next_review_date == this date and not mastered
        err_due_q = await db.execute(
            select(func.count()).where(
                ErrorBook.mastered == False,
                ErrorBook.next_review_date == ds,
            )
        )

        # Exam attempts on this date (UTC created_at → local date)
        exam_total_q = await db.execute(
            select(func.count()).where(
                _local_date(ExamAttempt.created_at) == ds
            )
        )
        exam_correct_q = await db.execute(
            select(func.count()).where(
                _local_date(ExamAttempt.created_at) == ds,
                ExamAttempt.is_correct == True,
            )
        )

        # Study minutes on this date
        study_q = await db.execute(
            select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
                _local_date(StudySession.started_at) == ds
            )
        )

        items.append({
            "date": ds,
            "plans_total": plan_total_q.scalar() or 0,
            "plans_completed": plan_done_q.scalar() or 0,
            "errors_created": err_created_q.scalar() or 0,
            "errors_review_due": err_due_q.scalar() or 0,
            "exam_attempts": exam_total_q.scalar() or 0,
            "exam_correct": exam_correct_q.scalar() or 0,
            "study_minutes": study_q.scalar() or 0,
        })

    return {"days": days, "items": items}
