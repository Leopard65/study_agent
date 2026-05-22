import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import StudyPlan
from app.schemas import (
    StudyPlanCreate, StudyPlanUpdate, StudyPlanItem,
    PlanGenerateRequest, PlanGenerateResponse,
)
from app.services.llm import generate_plan, LLMConfigError, LLMCallError

router = APIRouter(prefix="/api/plan", tags=["plan"])


@router.post("", response_model=StudyPlanItem)
async def create_plan(req: StudyPlanCreate, db: AsyncSession = Depends(get_db)):
    record = StudyPlan(**req.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("", response_model=list[StudyPlanItem])
async def list_plans(date: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(StudyPlan)
    if date:
        stmt = stmt.where(StudyPlan.date == date)
    stmt = stmt.order_by(StudyPlan.date, StudyPlan.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/{plan_id}", response_model=StudyPlanItem)
async def update_plan(plan_id: int, req: StudyPlanUpdate, db: AsyncSession = Depends(get_db)):
    record = await db.get(StudyPlan, plan_id)
    if not record:
        raise HTTPException(404, "计划不存在")
    if req.completed is not None:
        record.completed = req.completed
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{plan_id}")
async def delete_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    record = await db.get(StudyPlan, plan_id)
    if not record:
        raise HTTPException(404, "计划不存在")
    await db.delete(record)
    await db.commit()
    return {"ok": True}


@router.post("/generate", response_model=PlanGenerateResponse)
async def generate(req: PlanGenerateRequest, db: AsyncSession = Depends(get_db)):
    try:
        raw = await generate_plan(req.subjects, req.daily_hours, req.days, req.start_date)
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Try to extract JSON from response (handle markdown code blocks)
    json_str = raw.strip()
    # Remove ```json ... ``` wrappers
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
    if m:
        json_str = m.group(1).strip()

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, list):
            raise ValueError("JSON 顶层不是数组")
    except Exception as e:
        return PlanGenerateResponse(plans=[], raw_response=raw, parse_error=f"JSON 解析失败: {e}")

    items: list[StudyPlan] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        d = entry.get("date", "")
        s = entry.get("subject", "")
        t = entry.get("task", "")
        if d and s and t:
            record = StudyPlan(date=d, subject=s, task=t)
            db.add(record)
            items.append(record)

    if not items:
        return PlanGenerateResponse(
            plans=[], raw_response=raw, parse_error="JSON 解析成功但未提取到有效计划条目"
        )

    await db.commit()
    for r in items:
        await db.refresh(r)
    return PlanGenerateResponse(plans=items)
