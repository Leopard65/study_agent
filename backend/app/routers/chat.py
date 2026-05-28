from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ChatHistory, Material
from app.schemas import ChatRequest, ChatResponse, ChatSource, ChatHistoryItem
from app.services import llm
from app.services.llm import LLMConfigError, LLMCallError
from app.services.search import search_chunks

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_CONTEXT_CHARS = 12000


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    sources: list[ChatSource] = []
    context_parts: list[str] = []
    seen_mids: set[int] = set()

    # RAG: auto-search materials for relevant context
    hits = await search_chunks(db, req.question, limit=5)
    if hits:
        for hit in hits:
            mid = hit["material_id"]
            mat = await db.get(Material, mid)
            if mat and mid not in seen_mids:
                seen_mids.add(mid)
                sources.append(ChatSource(
                    material_id=mid,
                    filename=mat.filename,
                    snippet=hit.get("snippet", "")[:200],
                ))
            context_parts.append(hit["content"])

    # Merge user-provided context (e.g. from frontend selection)
    if req.context:
        context_parts.append(req.context)

    # Join and cap total context length
    context = None
    if context_parts:
        joined = "\n---\n".join(context_parts)
        if len(joined) > _MAX_CONTEXT_CHARS:
            joined = joined[:_MAX_CONTEXT_CHARS]
        context = joined

    try:
        answer = await llm.chat(req.question, context)
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if sources:
        source_text = "、".join(s.filename for s in sources)
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
