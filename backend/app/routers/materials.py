import os, uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Material
from app.schemas import MaterialItem, SearchRequest, SearchResult
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

    os.makedirs(settings.upload_dir, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(settings.upload_dir, save_name)
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

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
async def list_materials(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Material).order_by(Material.created_at.desc()))
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
