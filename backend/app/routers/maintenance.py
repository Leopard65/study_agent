"""Data maintenance center: health checks, orphan cleanup, operation logs."""
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.config import get_settings
from app.models import Material, MaterialParseJob, MaterialChunk, OperationLog

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

# Only allow deleting files with these extensions (same as upload)
_ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}


def _dir_size(path: str) -> int:
    """Calculate total size of files in a directory (non-recursive for safety)."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    return total


def _safe_listdir(path: str) -> list[str]:
    """List filenames in directory, returning empty list on error."""
    try:
        return [e.name for e in os.scandir(path) if e.is_file()]
    except OSError:
        return []


@router.get("/health")
async def maintenance_health(db: AsyncSession = Depends(get_db)):
    """Return data health summary: counts, orphan files, missing files, DB size."""
    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)

    # Material counts
    total_materials = (await db.execute(select(func.count()).select_from(Material))).scalar() or 0

    # Parse job stats
    failed_jobs = (await db.execute(
        select(func.count()).select_from(MaterialParseJob).where(MaterialParseJob.status == "failed")
    )).scalar() or 0

    processing_jobs = (await db.execute(
        select(func.count()).select_from(MaterialParseJob).where(MaterialParseJob.status == "processing")
    )).scalar() or 0

    # Materials with stored_filename
    stored_rows = (await db.execute(
        select(Material.stored_filename).where(Material.stored_filename != "")
    )).scalars().all()
    referenced_files = set(stored_rows)

    # Files on disk
    disk_files = set(_safe_listdir(upload_dir))

    # Orphan files: on disk but not referenced by any material
    orphan_files = sorted(disk_files - referenced_files)

    # Missing files: referenced by materials but not on disk
    missing_files = sorted(referenced_files - disk_files)

    # Materials with failed status
    failed_materials = (await db.execute(
        select(func.count()).select_from(Material).where(Material.status == "failed")
    )).scalar() or 0

    # Chunk count
    total_chunks = (await db.execute(select(func.count()).select_from(MaterialChunk))).scalar() or 0

    # Database size
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    db_size = 0
    try:
        db_size = os.path.getsize(db_path)
    except OSError:
        pass

    # Uploads directory size
    uploads_size = _dir_size(upload_dir)

    # Operation log count
    total_ops = (await db.execute(select(func.count()).select_from(OperationLog))).scalar() or 0

    return {
        "total_materials": total_materials,
        "total_chunks": total_chunks,
        "upload_files": len(disk_files),
        "orphan_files": len(orphan_files),
        "orphan_file_names": orphan_files[:20],  # preview first 20
        "missing_files": len(missing_files),
        "missing_file_names": missing_files[:20],
        "failed_materials": failed_materials,
        "failed_jobs": failed_jobs,
        "processing_jobs": processing_jobs,
        "database_size": db_size,
        "uploads_size": uploads_size,
        "total_operations": total_ops,
    }


@router.post("/cleanup/preview")
async def cleanup_preview(db: AsyncSession = Depends(get_db)):
    """Preview what would be cleaned up. No actual deletion."""
    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)

    # Orphan files
    stored_rows = (await db.execute(
        select(Material.stored_filename).where(Material.stored_filename != "")
    )).scalars().all()
    referenced_files = set(stored_rows)
    disk_files = set(_safe_listdir(upload_dir))
    orphan_files = sorted(disk_files - referenced_files)

    # Invalid parse jobs: jobs whose material no longer exists
    all_jobs = (await db.execute(
        select(MaterialParseJob.id, MaterialParseJob.material_id, MaterialParseJob.status)
    )).all()
    material_ids = set((await db.execute(select(Material.id))).scalars().all())
    invalid_jobs = [{"job_id": j.id, "material_id": j.material_id, "status": j.status}
                    for j in all_jobs if j.material_id not in material_ids]

    # Orphan chunks: chunks whose material no longer exists
    chunk_material_ids = set((await db.execute(
        select(MaterialChunk.material_id).distinct()
    )).scalars().all())
    orphan_chunk_materials = sorted(chunk_material_ids - material_ids)

    return {
        "orphan_files": orphan_files,
        "orphan_files_count": len(orphan_files),
        "invalid_jobs": invalid_jobs,
        "invalid_jobs_count": len(invalid_jobs),
        "orphan_chunk_materials": orphan_chunk_materials,
        "orphan_chunk_materials_count": len(orphan_chunk_materials),
    }


@router.post("/cleanup")
async def cleanup_execute(db: AsyncSession = Depends(get_db)):
    """Execute cleanup: remove orphan files and invalid parse jobs.
    Conservative: never deletes referenced files."""
    settings = get_settings()
    upload_dir = os.path.abspath(settings.upload_dir)
    deleted_files: list[str] = []
    skipped_files: list[str] = []
    deleted_jobs = 0
    deleted_chunks = 0
    errors: list[str] = []

    # ── 1. Orphan files ──
    stored_rows = (await db.execute(
        select(Material.stored_filename).where(Material.stored_filename != "")
    )).scalars().all()
    referenced_files = set(stored_rows)
    disk_files = _safe_listdir(upload_dir)

    for fname in disk_files:
        if fname in referenced_files:
            continue
        # Safety: only delete files with allowed extensions
        ext = os.path.splitext(fname)[1].lower()
        if ext not in _ALLOWED_EXTS:
            skipped_files.append(fname)
            continue
        fpath = os.path.join(upload_dir, fname)
        # Double-check resolved path is inside upload_dir
        if not os.path.normpath(fpath).startswith(os.path.normpath(upload_dir) + os.sep):
            skipped_files.append(fname)
            continue
        try:
            os.remove(fpath)
            deleted_files.append(fname)
        except OSError as e:
            errors.append(f"删除 {fname}: {e}")

    # ── 2. Invalid parse jobs ──
    all_jobs = (await db.execute(
        select(MaterialParseJob.id, MaterialParseJob.material_id)
    )).all()
    material_ids = set((await db.execute(select(Material.id))).scalars().all())
    for job in all_jobs:
        if job.material_id not in material_ids:
            await db.execute(text("DELETE FROM material_parse_jobs WHERE id = :id"), {"id": job.id})
            deleted_jobs += 1

    # ── 3. Orphan chunks (and their FTS entries) ──
    chunk_material_ids = set((await db.execute(
        select(MaterialChunk.material_id).distinct()
    )).scalars().all())
    orphan_chunk_mids = sorted(chunk_material_ids - material_ids)
    for mid in orphan_chunk_mids:
        # Delete FTS entries for chunks of this material
        await db.execute(text("DELETE FROM chunks_fts WHERE material_id = :mid"), {"mid": mid})
        result = await db.execute(text("DELETE FROM material_chunks WHERE material_id = :mid"), {"mid": mid})
        deleted_chunks += result.rowcount

    await db.commit()

    # ── Log the operation ──
    summary = {
        "deleted_files": len(deleted_files),
        "skipped_files": len(skipped_files),
        "deleted_jobs": deleted_jobs,
        "deleted_chunks": deleted_chunks,
        "errors": len(errors),
    }
    log_entry = OperationLog(
        operation_type="cleanup",
        file_type="",
        strategy="",
        result_summary=json.dumps(summary, ensure_ascii=False),
        error_message="; ".join(errors[:5]) if errors else "",
    )
    db.add(log_entry)
    await db.commit()

    return {
        "deleted_files": deleted_files,
        "skipped_files": skipped_files,
        "deleted_jobs": deleted_jobs,
        "deleted_chunks": deleted_chunks,
        "errors": errors,
    }


@router.get("/logs")
async def list_logs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Return recent operation logs (backup/import/cleanup)."""
    if limit < 1 or limit > 100:
        raise HTTPException(422, "limit 必须在 1-100 之间")
    rows = (await db.execute(
        select(OperationLog).order_by(OperationLog.id.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "operation_type": r.operation_type,
            "file_type": r.file_type,
            "strategy": r.strategy,
            "result_summary": r.result_summary,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
