import os, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Material, MaterialParseJob
from app.schemas import MaterialItem, MaterialDetail, SearchRequest, SearchResult, BulkDeleteRequest, ExportSelectedRequest, ParseJobItem, ChunkItem
from app.services.search import search_chunks, delete_chunks_for_material, _contains_cjk, _extract_keywords
from app.services.parse_worker import get_worker
from app.config import get_settings

router = APIRouter(prefix="/api/materials", tags=["materials"])
settings = get_settings()
VALID_JOB_STATUSES = {"pending", "processing", "done", "failed", "cancelled"}


def _build_marked_snippet(content: str, terms: list[str], context_chars: int = 60) -> str:
    """Build a short snippet with >>>...<<< around the first matching term."""
    for term in terms:
        if not term:
            continue
        idx = content.find(term)
        if idx == -1:
            idx = content.lower().find(term.lower())
        if idx == -1:
            continue

        match_text = content[idx:idx + len(term)]
        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(term) + context_chars)
        snippet = "..." if start > 0 else ""
        snippet += content[start:idx]
        snippet += f">>>{match_text}<<<"
        snippet += content[idx + len(term):end]
        if end < len(content):
            snippet += "..."
        return snippet

    fallback_len = context_chars * 2
    return content[:fallback_len] + ("..." if len(content) > fallback_len else "")


def _delete_uploaded_file(stored_filename: str) -> None:
    """Delete a stored file from upload_dir. Skips if path escapes upload_dir or file missing."""
    if not stored_filename:
        return
    upload_abs = os.path.abspath(settings.upload_dir)
    file_abs = os.path.abspath(os.path.join(upload_abs, stored_filename))
    try:
        if os.path.commonpath([upload_abs, file_abs]) != upload_abs:
            return
    except ValueError:
        return
    try:
        if os.path.isfile(file_abs):
            os.remove(file_abs)
    except OSError:
        pass


async def _delete_jobs_for_material(db: AsyncSession, material_id: int) -> None:
    """删除资料关联的所有 parse jobs。"""
    jobs = await db.execute(
        select(MaterialParseJob).where(MaterialParseJob.material_id == material_id)
    )
    for job in jobs.scalars().all():
        await db.delete(job)


@router.post("/upload", response_model=MaterialItem)
async def upload(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    allowed = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    os.makedirs(settings.upload_dir, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(settings.upload_dir, save_name)

    total_size = 0
    chunk_size = 1024 * 1024  # 1MB
    try:
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_bytes:
                    raise HTTPException(413, f"文件过大，最大支持 {settings.max_upload_mb}MB")
                f.write(chunk)
    except HTTPException:
        _delete_uploaded_file(save_name)
        raise
    except Exception:
        _delete_uploaded_file(save_name)
        raise

    try:
        material = Material(
            filename=file.filename or save_name,
            file_type=ext,
            content="",
            stored_filename=save_name,
            status="pending",
            error_message="",
        )
        db.add(material)
        await db.flush()

        # 创建 parse job
        job = MaterialParseJob(material_id=material.id, status="pending", attempts=0)
        db.add(job)
        await db.commit()
        await db.refresh(material)

        # 通知 worker
        await get_worker().enqueue(material.id)

        return material
    except Exception:
        await db.rollback()
        _delete_uploaded_file(save_name)
        raise


@router.get("", response_model=list[MaterialItem])
async def list_materials(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    result = await db.execute(
        select(Material).order_by(Material.created_at.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.post("/search", response_model=list[SearchResult])
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    hits = await search_chunks(db, req.query, req.limit)
    results = []
    seen: set[int] = set()
    for hit in hits:
        mid = hit["material_id"]
        if mid in seen:
            continue
        seen.add(mid)
        mat = await db.get(Material, mid)
        if mat:
            results.append(SearchResult(material_id=mat.id, filename=mat.filename, snippet=hit["snippet"]))
    return results


@router.get("/jobs", response_model=list[ParseJobItem])
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """返回最近的解析任务列表，含 material filename。"""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = select(MaterialParseJob).order_by(MaterialParseJob.created_at.desc())
    if status:
        if status not in VALID_JOB_STATUSES:
            raise HTTPException(422, f"status 包含无效值: {status}，允许: {','.join(sorted(VALID_JOB_STATUSES))}")
        query = query.where(MaterialParseJob.status == status)
    query = query.offset(offset).limit(limit)
    rows = await db.execute(query)
    jobs = rows.scalars().all()

    # 批量获取 material filenames
    mat_ids = {j.material_id for j in jobs}
    mat_map: dict[int, str] = {}
    if mat_ids:
        mats = await db.execute(select(Material).where(Material.id.in_(mat_ids)))
        for m in mats.scalars().all():
            mat_map[m.id] = m.filename

    return [
        ParseJobItem(
            id=j.id,
            material_id=j.material_id,
            filename=mat_map.get(j.material_id, ""),
            status=j.status,
            attempts=j.attempts,
            error_message=j.error_message or "",
            progress_current=j.progress_current or 0,
            progress_total=j.progress_total or 0,
            progress_message=j.progress_message or "",
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
        )
        for j in jobs
    ]


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """取消 pending 状态的解析任务。processing 状态返回 422。"""
    job = await db.get(MaterialParseJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status != "pending":
        if job.status == "processing":
            raise HTTPException(422, "正在解析中，暂不支持中断")
        raise HTTPException(
            422,
            f"当前状态 {job.status} 不支持取消，仅 pending 可取消",
        )
    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    # 同步 material 状态
    mat = await db.get(Material, job.material_id)
    if mat and mat.status == "pending":
        mat.status = "failed"
        mat.error_message = "任务已取消"
    await db.commit()
    await db.refresh(job)
    return {"ok": True, "job_id": job.id, "status": job.status}


@router.post("/bulk-delete")
async def bulk_delete(req: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    deleted = 0
    missing = 0
    for mid in req.ids:
        mat = await db.get(Material, mid)
        if not mat:
            missing += 1
            continue
        await delete_chunks_for_material(db, mid)
        await _delete_jobs_for_material(db, mid)
        _delete_uploaded_file(mat.stored_filename or "")
        await db.delete(mat)
        deleted += 1
    await db.commit()
    return {"deleted": deleted, "missing": missing}


@router.post("/export-selected")
async def export_selected(req: ExportSelectedRequest, db: AsyncSession = Depends(get_db)):
    items = []
    for mid in req.ids:
        mat = await db.get(Material, mid)
        if not mat:
            continue
        entry = {
            "id": mat.id,
            "filename": mat.filename,
            "file_type": mat.file_type,
            "content_length": len(mat.content or ""),
            "created_at": mat.created_at.isoformat() if mat.created_at else None,
        }
        if req.include_preview:
            content = mat.content or ""
            limit = max(0, settings.material_preview_chars)
            entry["preview"] = content[:limit] if limit else ""
        items.append(entry)
    return {"selected_count": len(req.ids), "materials": items}


@router.get("/{material_id}", response_model=MaterialDetail)
async def get_material(material_id: int, db: AsyncSession = Depends(get_db)):
    mat = await db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "资料不存在")
    content = mat.content or ""
    preview_limit = max(0, settings.material_preview_chars)
    return MaterialDetail(
        id=mat.id,
        filename=mat.filename,
        file_type=mat.file_type,
        stored_filename=mat.stored_filename or "",
        preview=content[:preview_limit] if preview_limit else "",
        content_length=len(content),
        truncated=len(content) > preview_limit if preview_limit else bool(content),
        status=mat.status or "ready",
        error_message=mat.error_message or "",
        created_at=mat.created_at,
    )


@router.get("/{material_id}/chunks", response_model=list[ChunkItem])
async def get_material_chunks(
    material_id: int,
    limit: int = 20,
    offset: int = 0,
    query: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """返回资料的分块内容，支持分页和资料内搜索高亮。"""
    mat = await db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "资料不存在")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    from sqlalchemy import text as sql_text
    from app.models import MaterialChunk

    if query and query.strip():
        query = query.strip()
        highlight_terms = [query]
        # 搜索模式：在该资料的 chunks 中查找含 query 的块
        if _contains_cjk(query):
            keywords = _extract_keywords(query)
            if not keywords:
                keywords = [query]
            highlight_terms = keywords
            conditions = " OR ".join([f"content LIKE :q{i}" for i in range(len(keywords))])
            params: dict = {f"q{i}": f"%{kw}%" for i, kw in enumerate(keywords)}
            params["mid"] = material_id
            params["l"] = limit
            params["o"] = offset
            result = await db.execute(
                sql_text(
                    f"SELECT id, chunk_index, content FROM material_chunks "
                    f"WHERE material_id = :mid AND ({conditions}) "
                    f"ORDER BY chunk_index LIMIT :l OFFSET :o"
                ).bindparams(**params)
            )
        else:
            # FTS5 search within this material
            fts_query = '"' + query.replace('"', '""') + '"'
            result = await db.execute(
                sql_text(
                    "SELECT mc.id, mc.chunk_index, mc.content FROM material_chunks mc "
                    "INNER JOIN chunks_fts fts ON fts.chunk_id = mc.id "
                    "WHERE fts.material_id = :mid AND chunks_fts MATCH :q "
                    "ORDER BY mc.chunk_index LIMIT :l OFFSET :o"
                ).bindparams(mid=material_id, q=fts_query, l=limit, o=offset)
            )

        rows = result.fetchall()
        items = []
        for r in rows:
            snippet = _build_marked_snippet(r[2], highlight_terms)
            items.append(ChunkItem(id=r[0], chunk_index=r[1], content=r[2], snippet=snippet))
        return items

    # 无搜索：分页返回 chunks
    result = await db.execute(
        select(MaterialChunk)
        .where(MaterialChunk.material_id == material_id)
        .order_by(MaterialChunk.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    chunks = result.scalars().all()
    return [
        ChunkItem(id=c.id, chunk_index=c.chunk_index, content=c.content, snippet="")
        for c in chunks
    ]


@router.post("/{material_id}/retry", response_model=MaterialItem)
async def retry_material(material_id: int, db: AsyncSession = Depends(get_db)):
    mat = await db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "资料不存在")
    if mat.status not in ("failed",):
        raise HTTPException(422, f"当前状态 {mat.status} 不支持重试，仅 failed 可重试")
    stored = mat.stored_filename or ""
    if not stored:
        raise HTTPException(422, "缺少存储文件，无法重试")
    file_path = os.path.join(settings.upload_dir, stored)
    if not os.path.isfile(file_path):
        raise HTTPException(422, "存储文件不存在，无法重试")
    mat.status = "pending"
    mat.error_message = ""

    # 创建新 job
    job = MaterialParseJob(material_id=material_id, status="pending", attempts=0)
    db.add(job)
    await db.commit()
    await db.refresh(mat)

    await get_worker().enqueue(material_id)
    return mat


@router.delete("/{material_id}")
async def delete_material(material_id: int, db: AsyncSession = Depends(get_db)):
    mat = await db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "资料不存在")
    await delete_chunks_for_material(db, material_id)
    await _delete_jobs_for_material(db, material_id)
    _delete_uploaded_file(mat.stored_filename or "")
    await db.delete(mat)
    await db.commit()
    return {"ok": True}
