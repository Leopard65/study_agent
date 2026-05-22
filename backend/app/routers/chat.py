from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ChatHistory, Material
from app.schemas import ChatRequest, ChatResponse, ChatHistoryItem
from app.services import llm
from app.services.search import search_chunks

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    # RAG: auto-search materials for relevant context
    sources: list[str] = []
    context_parts: list[str] = []

    hits = await search_chunks(db, req.question, limit=5)
    if hits:
        for hit in hits:
            mat = await db.get(Material, hit["material_id"])
            if mat and mat.filename not in sources:
                sources.append(mat.filename)
            context_parts.append(hit["content"])

    context = "\n---\n".join(context_parts) if context_parts else None

    # Build prompt with source awareness
    answer = await llm.chat(req.question, context)

    if sources:
        source_text = "、".join(sources)
        answer += f"\n\n> 参考资料来源：{source_text}"
    elif not context_parts:
        answer += "\n\n> 未在资料库中找到直接依据，以上回答基于模型通用知识。"

    record = ChatHistory(question=req.question, answer=answer)
    db.add(record)
    await db.commit()
    return ChatResponse(answer=answer, sources=sources)


@router.get("/history", response_model=list[ChatHistoryItem])
async def history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
