import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import AppSetting


class ReviewSettingsUpdate(BaseModel):
    intervals: list[StrictInt] = Field(..., min_length=1, max_length=10)

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_INTERVALS = [1, 3, 7, 14]
SETTING_KEY = "review_intervals"


def validate_review_intervals(intervals: list[int]) -> str | None:
    """Validate review intervals. Returns error message or None if valid."""
    if not isinstance(intervals, list) or len(intervals) < 1 or len(intervals) > 10:
        return "间隔列表长度必须为 1-10"
    for v in intervals:
        if type(v) is not int or v < 1 or v > 365:
            return "每个间隔必须是 1-365 的正整数"
    for i in range(1, len(intervals)):
        if intervals[i] <= intervals[i - 1]:
            return "间隔必须严格递增"
    return None


async def get_review_intervals(db: AsyncSession) -> list[int]:
    record = await db.get(AppSetting, SETTING_KEY)
    if not record:
        return DEFAULT_INTERVALS
    try:
        parsed = json.loads(record.value)
        # Defend against dirty DB values
        if not isinstance(parsed, list):
            return DEFAULT_INTERVALS
        err = validate_review_intervals(parsed)
        if err:
            return DEFAULT_INTERVALS
        return parsed
    except Exception:
        return DEFAULT_INTERVALS


@router.get("/review")
async def read_review_settings(db: AsyncSession = Depends(get_db)):
    intervals = await get_review_intervals(db)
    return {"intervals": intervals}


@router.put("/review")
async def update_review_settings(body: ReviewSettingsUpdate, db: AsyncSession = Depends(get_db)):
    intervals = body.intervals
    err = validate_review_intervals(intervals)
    if err:
        raise HTTPException(422, err)

    record = await db.get(AppSetting, SETTING_KEY)
    if record:
        record.value = json.dumps(intervals)
    else:
        record = AppSetting(key=SETTING_KEY, value=json.dumps(intervals))
        db.add(record)
    await db.commit()
    return {"intervals": intervals}
