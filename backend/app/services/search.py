import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Common Chinese stop words to remove from search queries
_STOP_WORDS = frozenset([
    "什么", "怎么", "为什么", "如何", "请问", "在", "中", "的", "了", "是",
    "和", "与", "或", "及", "等", "对", "把", "被", "从", "到", "也",
    "就", "都", "而", "但", "如果", "因为", "所以", "可以", "这个", "那个",
    "有", "没有", "不", "没", "会", "能", "要", "我", "你", "他", "她",
    "它", "我们", "你们", "他们", "这", "那", "吗", "呢", "吧", "啊",
    "请", "告诉", "解释", "说明", "介绍", "一下", "一个", "什么是",
    "属于", "包括", "哪些", "什么样", "怎样", "意思", "含义",
])

# Domain-specific terms to prioritize
_DOMAIN_TERMS = frozenset([
    "卷积", "傅里叶", "拉普拉斯", "Z变换", "z变换", "系统", "信号",
    "频率响应", "冲激响应", "阶跃响应", "传递函数", "极点", "零点",
    "采样定理", "奈奎斯特", "巴特沃斯", "切比雪夫", "逆系统",
    "极限", "导数", "微分", "积分", "级数", "泰勒", "麦克劳林",
    "中值定理", "洛必达", "偏导", "梯度", "散度", "旋度",
    "矩阵", "行列式", "特征值", "特征向量", "线性方程", "二次型",
    "概率", "随机变量", "期望", "方差", "分布", "正态", "泊松",
    "马尔可夫", "贝叶斯", "假设检验", "置信区间", "回归",
    "线性时不变", "LTI", "连续时间", "离散时间", "卷积积分",
    "微分方程", "差分方程", "状态空间", "框图", "信号流图",
    "傅里叶变换", "傅里叶级数", "离散傅里叶", "快速傅里叶", "FFT", "DFT",
    "拉普拉斯逆变换", "双边拉普拉斯", "单边拉普拉斯",
    "Z逆变换", "ROC", "收敛域",
])


def _contains_cjk(query: str) -> bool:
    for ch in query:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF or
            0x3400 <= cp <= 0x4DBF or
            0x2E80 <= cp <= 0x2EFF or
            0xF900 <= cp <= 0xFAFF):
            return True
    return False


def _extract_keywords(query: str) -> list[str]:
    """Extract keywords from a Chinese natural language query.

    Strategy:
    1. Remove punctuation and non-CJK/ASCII characters
    2. Extract domain terms first (greedy match, longest first)
    3. Extract remaining CJK tokens >= 2 chars
    4. Remove stop words
    5. Domain terms go first (priority)
    """
    # Remove punctuation
    cleaned = re.sub(r'[，。？！、；：“”‘’（）【】《》\s?!.,;:\"\'()\[\]<>]+', ' ', query)
    cleaned = cleaned.strip()

    # Step 1: Find all domain terms present in the query
    found_domain: list[str] = []
    remaining = cleaned
    for term in sorted(_DOMAIN_TERMS, key=len, reverse=True):
        if term in remaining:
            found_domain.append(term)
            remaining = remaining.replace(term, ' ')

    # Step 2: Extract CJK word tokens (sequences of 2+ CJK chars) from remaining
    cjk_tokens = re.findall(r'[一-鿿]{2,}', remaining)

    # Step 3: Also extract ASCII tokens (English/technical terms) >= 2 chars
    ascii_tokens = re.findall(r'[a-zA-Z][a-zA-Z0-9]{1,}', remaining)

    # Step 4: Filter stop words
    keywords: list[str] = []
    seen: set[str] = set()

    for kw in found_domain:
        if kw not in seen and kw not in _STOP_WORDS:
            keywords.append(kw)
            seen.add(kw)

    for kw in cjk_tokens:
        if kw not in seen and kw not in _STOP_WORDS:
            keywords.append(kw)
            seen.add(kw)

    for kw in ascii_tokens:
        kw_upper = kw.upper()
        if kw_upper not in seen:
            keywords.append(kw)
            seen.add(kw_upper)

    return keywords


def split_into_chunks(content: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    if not content or not content.strip():
        return []
    content = content.strip()
    if len(content) <= chunk_size:
        return [content]
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        if end < len(content):
            for sep in ["\n\n", "\n", "。", ".", "；", ";", "！", "!", "？", "?"]:
                idx = content.rfind(sep, start + chunk_size // 2, end + 200)
                if idx > start:
                    end = idx + len(sep)
                    break
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(content) else end
    return chunks


def _build_snippet(content: str, query: str, context_chars: int = 60) -> str:
    # Try each keyword to find best snippet
    for kw in (query if isinstance(query, list) else [query]):
        idx = content.find(kw)
        if idx == -1:
            idx = content.lower().find(kw.lower())
        if idx != -1:
            start = max(0, idx - context_chars)
            end = min(len(content), idx + len(kw) + context_chars)
            s = ""
            if start > 0:
                s += "..."
            s += content[start:end]
            if end < len(content):
                s += "..."
            return s
    return content[:context_chars * 2] + "..." if len(content) > context_chars * 2 else content


async def index_chunks(session: AsyncSession, material_id: int, content: str):
    from app.models import MaterialChunk
    chunks = split_into_chunks(content)
    for i, chunk_text in enumerate(chunks):
        record = MaterialChunk(material_id=material_id, chunk_index=i, content=chunk_text)
        session.add(record)
        await session.flush()
        await session.execute(
            text("INSERT INTO chunks_fts (content, chunk_id, material_id) VALUES (:content, :cid, :mid)"),
            {"content": chunk_text, "cid": record.id, "mid": material_id},
        )


async def search_chunks(session: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    """Search chunks. FTS5 for English; keyword-extracted LIKE for Chinese.

    Returns list of dicts: chunk_id, material_id, snippet, content
    """
    if not query or not query.strip():
        return []

    query = query.strip()

    # Step 1: Try FTS5 for non-CJK queries
    if not _contains_cjk(query):
        try:
            fts_query = '"' + query.replace('"', '""') + '"'
            result = await session.execute(
                text(
                    "SELECT chunk_id, material_id, "
                    "snippet(chunks_fts, 0, '>>>', '<<<', '...', 60) as snippet "
                    "FROM chunks_fts WHERE chunks_fts MATCH :q LIMIT :l"
                ).bindparams(q=fts_query, l=limit)
            )
            rows = result.fetchall()
            if rows:
                hits = []
                for r in rows:
                    content_row = await session.execute(
                        text("SELECT content FROM material_chunks WHERE id = :cid"),
                        {"cid": r[0]},
                    )
                    cr = content_row.fetchone()
                    hits.append({
                        "chunk_id": r[0],
                        "material_id": r[1],
                        "snippet": r[2],
                        "content": cr[0] if cr else "",
                    })
                return hits
        except Exception:
            pass

    # Step 2: CJK — extract keywords and search with LIKE
    keywords = _extract_keywords(query)
    if not keywords:
        # Fallback: use raw query
        keywords = [query]

    return await _keyword_like_search(session, keywords, limit)


async def _keyword_like_search(session: AsyncSession, keywords: list[str], limit: int) -> list[dict]:
    """Search by multiple keywords with LIKE, merge and deduplicate results."""
    seen_ids: set[int] = set()
    results: list[dict] = []

    for kw in keywords:
        if len(results) >= limit:
            break
        row = await session.execute(
            text(
                "SELECT id, material_id, content "
                "FROM material_chunks WHERE content LIKE :q LIMIT :l"
            ).bindparams(q=f"%{kw}%", l=limit)
        )
        for r in row.fetchall():
            cid = r[0]
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            results.append({
                "chunk_id": cid,
                "material_id": r[1],
                "snippet": _build_snippet(r[2], kw),
                "content": r[2],
            })
            if len(results) >= limit:
                break

    return results


async def delete_chunks_for_material(session: AsyncSession, material_id: int):
    result = await session.execute(
        text("SELECT id FROM material_chunks WHERE material_id = :mid"),
        {"mid": material_id},
    )
    chunk_ids = [r[0] for r in result.fetchall()]
    if chunk_ids:
        for cid in chunk_ids:
            await session.execute(
                text("DELETE FROM chunks_fts WHERE chunk_id = :cid"),
                {"cid": cid},
            )
    await session.execute(
        text("DELETE FROM material_chunks WHERE material_id = :mid"),
        {"mid": material_id},
    )
    await session.flush()
