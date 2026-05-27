from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ErrorBook
from app.schemas import ErrorBookCreate, ErrorBookUpdate, ErrorBookItem

router = APIRouter(prefix="/api/errors", tags=["errors"])


@router.post("", response_model=ErrorBookItem)
async def create_error(req: ErrorBookCreate, db: AsyncSession = Depends(get_db)):
    record = ErrorBook(**req.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("", response_model=list[ErrorBookItem])
async def list_errors(
    mastered: bool | None = None,
    subject: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ErrorBook)
    if mastered is not None:
        stmt = stmt.where(ErrorBook.mastered == mastered)
    if subject:
        stmt = stmt.where(ErrorBook.subject == subject)
    stmt = stmt.order_by(ErrorBook.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


REVIEW_INTERVALS = {1: 1, 2: 3, 3: 7}  # review_count -> days


@router.patch("/{error_id}", response_model=ErrorBookItem)
async def update_error(error_id: int, req: ErrorBookUpdate, db: AsyncSession = Depends(get_db)):
    record = await db.get(ErrorBook, error_id)
    if not record:
        raise HTTPException(404, "错题不存在")

    if req.mastered is not None:
        old_mastered = record.mastered
        new_mastered = req.mastered
        if not old_mastered and new_mastered:
            record.review_count = (record.review_count or 0) + 1
            interval = REVIEW_INTERVALS.get(record.review_count, 14)
            record.next_review_date = (date.today() + timedelta(days=interval)).isoformat()
            record.mastered = True
        elif old_mastered and not new_mastered:
            record.mastered = False
            record.next_review_date = date.today().isoformat()

    if req.next_review_date is not None:
        record.next_review_date = req.next_review_date
    if req.review_count is not None:
        record.review_count = max(0, req.review_count)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{error_id}")
async def delete_error(error_id: int, db: AsyncSession = Depends(get_db)):
    record = await db.get(ErrorBook, error_id)
    if not record:
        raise HTTPException(404, "错题不存在")
    await db.delete(record)
    await db.commit()
    return {"ok": True}
