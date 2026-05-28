from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import StudySession
from app.schemas import StudySessionStartRequest

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _serialize(s: StudySession) -> dict:
    return {
        "id": s.id,
        "subject": s.subject or "",
        "note": s.note or "",
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "duration_minutes": s.duration_minutes or 0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/active")
async def get_active(db: AsyncSession = Depends(get_db)):
    stmt = select(StudySession).where(StudySession.ended_at == None).order_by(StudySession.id.desc()).limit(1)
    r = await db.execute(stmt)
    session = r.scalars().first()
    return _serialize(session) if session else None


@router.post("/start")
async def start_session(body: StudySessionStartRequest = StudySessionStartRequest(), db: AsyncSession = Depends(get_db)):
    # Check for existing active session
    stmt = select(StudySession).where(StudySession.ended_at == None).order_by(StudySession.id.desc()).limit(1)
    r = await db.execute(stmt)
    existing = r.scalars().first()
    if existing:
        raise HTTPException(409, "已有进行中的学习会话，请先结束当前会话")

    rec = StudySession(
        subject=body.subject,
        note=body.note,
        started_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return _serialize(rec)


@router.post("/{session_id}/stop")
async def stop_session(session_id: int, db: AsyncSession = Depends(get_db)):
    rec = await db.get(StudySession, session_id)
    if not rec:
        raise HTTPException(404, "学习会话不存在")
    if rec.ended_at is not None:
        raise HTTPException(409, "该会话已结束")

    now = datetime.now(timezone.utc)
    rec.ended_at = now
    started = rec.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    delta = now - started
    rec.duration_minutes = max(1, int(delta.total_seconds() // 60))
    await db.commit()
    await db.refresh(rec)
    return _serialize(rec)


@router.get("")
async def list_sessions(limit: int = 20, db: AsyncSession = Depends(get_db)):
    if limit < 1 or limit > 100:
        raise HTTPException(422, "limit 范围 1-100")
    stmt = select(StudySession).order_by(StudySession.id.desc()).limit(limit)
    r = await db.execute(stmt)
    return [_serialize(s) for s in r.scalars().all()]
