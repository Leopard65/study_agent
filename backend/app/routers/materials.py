import os, uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Material
from app.schemas import MaterialItem, MaterialDetail, SearchRequest, SearchResult, BulkDeleteRequest, ExportSelectedRequest
from app.services.doc_parser import extract_text
from app.services.search import index_chunks, search_chunks, delete_chunks_for_material
from app.config import get_settings

router = APIRouter(prefix="/api/materials", tags=["materials"])
settings = get_settings()


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
        text_content = extract_text(save_path)
        material = Material(filename=file.filename or save_name, file_type=ext, content=text_content, stored_filename=save_name)
        db.add(material)
        await db.flush()

        if text_content.strip():
            await index_chunks(db, material.id, text_content)

        await db.commit()
        await db.refresh(material)
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
        created_at=mat.created_at,
    )


@router.delete("/{material_id}")
async def delete_material(material_id: int, db: AsyncSession = Depends(get_db)):
    mat = await db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "资料不存在")
    await delete_chunks_for_material(db, material_id)
    _delete_uploaded_file(mat.stored_filename or "")
    await db.delete(mat)
    await db.commit()
    return {"ok": True}
