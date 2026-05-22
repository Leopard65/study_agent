from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ProblemRecord
from app.schemas import ProblemRequest, ProblemResponse, ProblemItem
from app.services.llm import solve_problem

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.post("/solve", response_model=ProblemResponse)
async def solve(req: ProblemRequest, db: AsyncSession = Depends(get_db)):
    solution = await solve_problem(req.question, req.subject)
    record = ProblemRecord(question=req.question, solution=solution, subject=req.subject)
    db.add(record)
    await db.commit()
    return ProblemResponse(solution=solution)


@router.get("/history", response_model=list[ProblemItem])
async def history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProblemRecord).order_by(ProblemRecord.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
