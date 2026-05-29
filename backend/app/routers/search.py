import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.services.search import search_chunks

router = APIRouter(prefix="/api/search", tags=["search"])

VALID_TYPES = {"materials", "errors", "plans", "exam", "chat", "problems"}


def _plain_snippet(s: str, max_len: int = 120) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len] + "..."
    return s


@router.get("")
async def global_search(
    q: str = "",
    types: str = "",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(422, "搜索关键词不能为空")
    if len(q) > 100:
        raise HTTPException(422, "搜索关键词最长 100 字符")
    if limit < 1 or limit > 50:
        raise HTTPException(422, "limit 范围 1-50")

    if types:
        type_set = set(types.split(",")) & VALID_TYPES
        if not type_set:
            raise HTTPException(422, f"types 无效，允许: {','.join(sorted(VALID_TYPES))}")
    else:
        type_set = VALID_TYPES

    results: list[dict] = []
    per_type = max(limit // max(len(type_set), 1), 3)

    # Materials
    if "materials" in type_set:
        chunks = await search_chunks(db, q.strip(), limit=per_type)
        for c in chunks:
            results.append({
                "type": "material",
                "id": c["material_id"],
                "title": c.get("filename", ""),
                "snippet": _plain_snippet(c.get("snippet", "")),
                "created_at": None,
            })

    # Errors
    if "errors" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, knowledge_point, tags, error_type, created_at "
            "FROM error_book WHERE question LIKE :q OR knowledge_point LIKE :q "
            "OR tags LIKE :q OR error_type LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q}%", l=per_type))
        for r in rows.fetchall():
            title = r[4] or r[2] or "错题"
            results.append({
                "type": "error", "id": r[0],
                "title": title,
                "snippet": _plain_snippet(r[1]),
                "created_at": str(r[5]) if r[5] else None,
            })

    # Plans
    if "plans" in type_set:
        rows = await db.execute(text(
            "SELECT id, subject, task, date, created_at FROM study_plans "
            "WHERE subject LIKE :q OR task LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q}%", l=per_type))
        for r in rows.fetchall():
            results.append({
                "type": "plan", "id": r[0],
                "title": f"{r[3]} {r[1]}",
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[4]) if r[4] else None,
            })

    # Exam
    if "exam" in type_set:
        rows = await db.execute(text(
            "SELECT id, title, question, tags, created_at FROM exam_questions "
            "WHERE title LIKE :q OR question LIKE :q OR tags LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q}%", l=per_type))
        for r in rows.fetchall():
            results.append({
                "type": "exam", "id": r[0],
                "title": r[1] or "真题",
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[4]) if r[4] else None,
            })

    # Chat
    if "chat" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, answer, created_at FROM chat_history "
            "WHERE question LIKE :q OR answer LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q}%", l=per_type))
        for r in rows.fetchall():
            results.append({
                "type": "chat", "id": r[0],
                "title": _plain_snippet(r[1], 40),
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[3]) if r[3] else None,
            })

    # Problems
    if "problems" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, solution, subject, created_at FROM problems "
            "WHERE question LIKE :q OR solution LIKE :q OR subject LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q}%", l=per_type))
        for r in rows.fetchall():
            results.append({
                "type": "problem", "id": r[0],
                "title": r[3] or "题目解析",
                "snippet": _plain_snippet(r[1]),
                "created_at": str(r[4]) if r[4] else None,
            })

    return {"query": q, "results": results[:limit]}
