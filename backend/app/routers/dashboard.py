from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import StudyPlan, Material, ErrorBook
from app.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
async def stats(db: AsyncSession = Depends(get_db)):
    today = date.today().isoformat()

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

    # Streak: count consecutive days with at least one completed task
    streak = 0
    check_date = date.today()
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

    return DashboardStats(
        today_tasks=today_tasks,
        today_completed=today_completed,
        total_materials=total_materials,
        total_errors=total_errors,
        unmastered_errors=unmastered_errors,
        streak_days=streak,
    )
