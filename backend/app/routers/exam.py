import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.database import get_db
from app.models import ExamQuestion, ExamAttempt, ErrorBook
from app.schemas import (
    ExamQuestionCreate, ExamQuestionItem,
    ExamAttemptCreate, ExamAttemptItem,
    ErrorBookItem,
    ExamGenerateRequest, ExamGenerateResponse, ExamDraftItem,
)
from app.services.llm import generate_exam_questions, LLMConfigError, LLMCallError
from app.services.search import search_chunks

router = APIRouter(prefix="/api/exam", tags=["exam"])


@router.get("/questions", response_model=list[ExamQuestionItem])
async def list_questions(
    subject: str | None = None,
    year: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ExamQuestion)
    if subject:
        stmt = stmt.where(ExamQuestion.subject == subject)
    if year:
        stmt = stmt.where(ExamQuestion.year == year)
    if tag:
        stmt = stmt.where(ExamQuestion.tags.contains(tag))
    stmt = stmt.order_by(ExamQuestion.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/questions", response_model=ExamQuestionItem)
async def create_question(req: ExamQuestionCreate, db: AsyncSession = Depends(get_db)):
    record = ExamQuestion(**req.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/questions/{question_id}", response_model=ExamQuestionItem)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    record = await db.get(ExamQuestion, question_id)
    if not record:
        raise HTTPException(404, "题目不存在")
    return record


@router.post("/questions/{question_id}/attempt", response_model=ExamAttemptItem)
async def submit_attempt(
    question_id: int, req: ExamAttemptCreate, db: AsyncSession = Depends(get_db)
):
    question = await db.get(ExamQuestion, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    attempt = ExamAttempt(question_id=question_id, **req.model_dump())
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


@router.post("/questions/{question_id}/add-to-errors", response_model=ErrorBookItem)
async def add_to_error_book(question_id: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(ExamQuestion, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    # Deduplicate: check if this exam question was already added
    existing = await db.execute(
        select(ErrorBook).where(
            ErrorBook.error_type == "真题练习",
            ErrorBook.question == question.question,
        )
    )
    if existing.scalars().first():
        raise HTTPException(409, "该题目已在错题本中")
    error = ErrorBook(
        subject=question.subject or "",
        question=question.question,
        correct_answer=question.answer or "",
        correct_approach=question.solution or "",
        error_type="真题练习",
        tags=question.tags or "",
    )
    db.add(error)
    await db.commit()
    await db.refresh(error)
    return error


@router.delete("/questions/{question_id}")
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    record = await db.get(ExamQuestion, question_id)
    if not record:
        raise HTTPException(404, "题目不存在")
    # Cascade delete related attempts in bulk
    await db.execute(
        sql_delete(ExamAttempt).where(ExamAttempt.question_id == question_id)
    )
    await db.delete(record)
    await db.commit()
    return {"ok": True}


@router.post("/generate", response_model=ExamGenerateResponse)
async def generate(req: ExamGenerateRequest, db: AsyncSession = Depends(get_db)):
    # Optionally retrieve material context
    context = ""
    if req.use_materials:
        chunks = await search_chunks(db, req.topic, limit=5)
        if chunks:
            context = "\n\n".join(c["content"][:2000] for c in chunks)

    try:
        raw = await generate_exam_questions(
            subject=req.subject,
            topic=req.topic,
            count=req.count,
            difficulty=req.difficulty or "",
            context=context,
        )
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Parse JSON from response (handle markdown code blocks)
    json_str = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
    if m:
        json_str = m.group(1).strip()

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, list):
            raise ValueError("JSON 顶层不是数组")
    except Exception as e:
        return ExamGenerateResponse(drafts=[], raw_response=raw, parse_error=f"JSON 解析失败: {e}")

    drafts: list[ExamDraftItem] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        draft = ExamDraftItem(
            title=entry.get("title", ""),
            subject=entry.get("subject", "") or req.subject,
            year=entry.get("year", ""),
            question=entry.get("question", ""),
            answer=entry.get("answer", ""),
            solution=entry.get("solution", ""),
            tags=entry.get("tags", ""),
        )
        if draft.question:
            drafts.append(draft)

    if not drafts:
        return ExamGenerateResponse(
            drafts=[], raw_response=raw, parse_error="JSON 解析成功但未提取到有效题目"
        )

    return ExamGenerateResponse(drafts=drafts)
