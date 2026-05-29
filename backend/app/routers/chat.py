import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import ChatHistory, Material
from app.schemas import ChatRequest, ChatResponse, ChatSource, ChatHistoryItem, ConversationItem
from app.services import llm
from app.services.llm import LLMConfigError, LLMCallError
from app.services.search import search_chunks

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_CONTEXT_CHARS = 12000
_CONTEXT_HISTORY_COUNT = 5


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    sources: list[ChatSource] = []
    context_parts: list[str] = []
    seen_mids: set[int] = set()

    # 确定 conversation_id
    conversation_id = req.conversation_id or uuid.uuid4().hex[:12]

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

    # 加载最近对话历史作为上下文
    history_messages: list[dict[str, str]] = []
    hist_q = await db.execute(
        select(ChatHistory.question, ChatHistory.answer)
        .where(ChatHistory.conversation_id == conversation_id)
        .order_by(ChatHistory.id.desc())
        .limit(_CONTEXT_HISTORY_COUNT)
    )
    history_rows = hist_q.fetchall()
    for q, a in reversed(history_rows):
        history_messages.append({"role": "user", "content": q})
        history_messages.append({"role": "assistant", "content": a})

    try:
        answer = await llm.chat(req.question, context, history_messages)
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if sources:
        source_text = "、".join(s.filename for s in sources)
        answer += f"\n\n> 参考资料来源：{source_text}"
    elif not context_parts:
        answer += "\n\n> 未在资料库中找到直接依据，以上回答基于模型通用知识。"

    record = ChatHistory(
        conversation_id=conversation_id,
        question=req.question,
        answer=answer,
    )
    db.add(record)
    await db.commit()
    return ChatResponse(answer=answer, sources=sources, conversation_id=conversation_id)


@router.get("/history", response_model=list[ChatHistoryItem])
async def history(
    conversation_id: str = "",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ChatHistory)
    if conversation_id:
        stmt = stmt.where(ChatHistory.conversation_id == conversation_id)
    stmt = stmt.order_by(ChatHistory.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/conversations", response_model=list[ConversationItem])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """列出所有对话，按最后消息时间倒序。"""
    # 获取每个 conversation_id 的统计信息
    subq = (
        select(
            ChatHistory.conversation_id,
            func.count().label("cnt"),
            func.max(ChatHistory.created_at).label("last_at"),
        )
        .where(ChatHistory.conversation_id != "")
        .group_by(ChatHistory.conversation_id)
        .order_by(func.max(ChatHistory.created_at).desc())
    )
    result = await db.execute(subq)
    rows = result.fetchall()

    conversations = []
    for conv_id, cnt, last_at in rows:
        # 获取第一条消息作为标题
        title_q = await db.execute(
            select(ChatHistory.question)
            .where(ChatHistory.conversation_id == conv_id)
            .order_by(ChatHistory.id.asc())
            .limit(1)
        )
        first_q = title_q.scalar() or ""
        title = first_q[:50] + ("..." if len(first_q) > 50 else "")
        conversations.append(ConversationItem(
            conversation_id=conv_id,
            title=title,
            message_count=cnt,
            last_message_at=last_at,
        ))
    return conversations


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """删除整个对话。"""
    result = await db.execute(
        select(ChatHistory).where(ChatHistory.conversation_id == conversation_id)
    )
    records = result.scalars().all()
    if not records:
        raise HTTPException(404, "对话不存在")
    for r in records:
        await db.delete(r)
    await db.commit()
    return {"ok": True, "deleted": len(records)}
