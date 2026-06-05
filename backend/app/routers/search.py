import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.database import get_db
from app.models import Material
from app.services.search import search_chunks

router = APIRouter(prefix="/api/search", tags=["search"])

VALID_TYPES = {"materials", "errors", "plans", "exam", "chat", "problems"}


def _plain_snippet(s: str, max_len: int = 120) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len] + "..."
    return s


def _match_field(q: str, *fields: str | None) -> str:
    """返回第一个命中关键词的字段名。标题/题干优先，其次正文/答案。"""
    q_lower = q.lower()
    # 第一优先级：标题、题干、科目、标签
    priority1 = ["title", "question", "subject", "tags", "knowledge_point", "error_type"]
    # 第二优先级：正文、答案、解析
    priority2 = ["answer", "solution", "task", "content"]
    field_names = priority1 + priority2
    for fname, val in zip(field_names, fields):
        if val and q_lower in str(val).lower():
            return fname
    return "content"


@router.get("")
async def global_search(
    q: str = "",
    types: str = "",
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(422, "搜索关键词不能为空")
    if len(q) > 100:
        raise HTTPException(422, "搜索关键词最长 100 字符")
    if limit < 1 or limit > 50:
        raise HTTPException(422, "limit 范围 1-50")
    if offset < 0:
        raise HTTPException(422, "offset 不能为负数")

    if types:
        type_list = [t.strip() for t in types.split(",") if t.strip()]
        invalid = [t for t in type_list if t not in VALID_TYPES]
        if invalid:
            raise HTTPException(422, f"types 包含无效值: {','.join(invalid)}，允许: {','.join(sorted(VALID_TYPES))}")
        type_set = set(type_list)
    else:
        type_set = VALID_TYPES

    q_stripped = q.strip()
    results: list[dict] = []
    # 每个类型拉取足够多的结果，保证分页 total 准确
    # 取 limit + offset 的总量与每类型上限的较大值
    page_cap = offset + limit
    per_type = max(page_cap // max(len(type_set), 1), 10)

    # Materials（按 material_id 去重，每个资料只保留最佳 chunk）
    if "materials" in type_set:
        chunks = await search_chunks(db, q_stripped, limit=per_type * 2)
        seen_mids: set[int] = set()
        best_chunks: dict[int, dict] = {}
        for c in chunks:
            mid = c["material_id"]
            if mid not in seen_mids:
                seen_mids.add(mid)
                best_chunks[mid] = c
            if len(best_chunks) >= per_type:
                break
        if best_chunks:
            mat_rows = await db.execute(
                select(Material.id, Material.filename).where(Material.id.in_(list(best_chunks.keys())))
            )
            filenames = {row.id: row.filename for row in mat_rows}
            for mid, c in best_chunks.items():
                if mid not in filenames:
                    continue  # skip FTS hits for deleted materials
                results.append({
                    "type": "material",
                    "id": mid,
                    "title": filenames.get(mid, "资料"),
                    "snippet": _plain_snippet(c.get("snippet", "")),
                    "created_at": None,
                    "match_field": "content",
                })

    # Errors（标题/题干命中优先）
    if "errors" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, knowledge_point, tags, error_type, created_at "
            "FROM error_book WHERE question LIKE :q OR knowledge_point LIKE :q "
            "OR tags LIKE :q OR error_type LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q_stripped}%", l=per_type * 2))
        error_rows = rows.fetchall()
        # 按命中优先级排序：error_type/tags/knowledge_point 命中排前面
        def error_sort_key(r):
            title_hit = q_stripped.lower() in (r[4] or "").lower() or q_stripped.lower() in (r[2] or "").lower() or q_stripped.lower() in (r[3] or "").lower()
            return (0 if title_hit else 1, r[0])
        error_rows.sort(key=error_sort_key)
        for r in error_rows[:per_type]:
            title = r[4] or r[2] or "错题"
            mf = _match_field(q_stripped, r[4], r[1], None, r[3], r[2])
            results.append({
                "type": "error", "id": r[0],
                "title": title,
                "snippet": _plain_snippet(r[1]),
                "created_at": str(r[5]) if r[5] else None,
                "match_field": mf,
            })

    # Plans
    if "plans" in type_set:
        rows = await db.execute(text(
            "SELECT id, subject, task, date, created_at FROM study_plans "
            "WHERE subject LIKE :q OR task LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q_stripped}%", l=per_type))
        for r in rows.fetchall():
            mf = _match_field(q_stripped, r[1], None, None, None, None, r[2])
            results.append({
                "type": "plan", "id": r[0],
                "title": f"{r[3]} {r[1]}",
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[4]) if r[4] else None,
                "match_field": mf,
            })

    # Exam（标题命中优先）
    if "exam" in type_set:
        rows = await db.execute(text(
            "SELECT id, title, question, tags, created_at FROM exam_questions "
            "WHERE title LIKE :q OR question LIKE :q OR tags LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q_stripped}%", l=per_type * 2))
        exam_rows = rows.fetchall()
        def exam_sort_key(r):
            title_hit = q_stripped.lower() in (r[1] or "").lower() or q_stripped.lower() in (r[3] or "").lower()
            return (0 if title_hit else 1, r[0])
        exam_rows.sort(key=exam_sort_key)
        for r in exam_rows[:per_type]:
            mf = _match_field(q_stripped, r[1], r[2], None, r[3])
            results.append({
                "type": "exam", "id": r[0],
                "title": r[1] or "真题",
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[4]) if r[4] else None,
                "match_field": mf,
            })

    # Chat
    if "chat" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, answer, created_at FROM chat_history "
            "WHERE question LIKE :q OR answer LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q_stripped}%", l=per_type))
        for r in rows.fetchall():
            mf = _match_field(q_stripped, r[1], r[2])
            results.append({
                "type": "chat", "id": r[0],
                "title": _plain_snippet(r[1], 40),
                "snippet": _plain_snippet(r[2]),
                "created_at": str(r[3]) if r[3] else None,
                "match_field": mf,
            })

    # Problems
    if "problems" in type_set:
        rows = await db.execute(text(
            "SELECT id, question, solution, subject, created_at FROM problems "
            "WHERE question LIKE :q OR solution LIKE :q OR subject LIKE :q LIMIT :l"
        ).bindparams(q=f"%{q_stripped}%", l=per_type))
        for r in rows.fetchall():
            mf = _match_field(q_stripped, r[3], r[1], None, None, None, r[2])
            results.append({
                "type": "problem", "id": r[0],
                "title": r[3] or "题目解析",
                "snippet": _plain_snippet(r[1]),
                "created_at": str(r[4]) if r[4] else None,
                "match_field": mf,
            })

    # 按 match_field 排序：title/question/subject/tags 命中优先
    priority_fields = {"title", "question", "subject", "tags", "knowledge_point", "error_type"}
    results.sort(key=lambda r: (0 if r.get("match_field") in priority_fields else 1))

    return {"query": q, "total": len(results), "results": results[offset:offset + limit]}
