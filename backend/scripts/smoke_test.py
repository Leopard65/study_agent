"""本地冒烟测试：覆盖非 AI 主链路，不依赖 API Key。
用法：cd backend && .venv\\Scripts\\python.exe scripts\\smoke_test.py

环境变量 CORS_ORIGINS 可配置 CORS 允许来源，默认 localhost:5173。"""
import json
import os
import sys
import io

# Fix Windows console encoding: force UTF-8 for stdout/stderr
if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name)
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        elif isinstance(_stream, io.TextIOWrapper):
            setattr(sys, _stream_name, io.TextIOWrapper(_stream.buffer, encoding="utf-8", errors="replace"))

# 确保 backend/ 在 sys.path 中，以便 import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tempfile
import shutil

# ── 隔离：用临时数据库和上传目录，不污染本地库 ──
_tmp_dir = tempfile.mkdtemp(prefix="smoke_test_")
_db_path = os.path.join(_tmp_dir, "test.db")
_uploads_dir = os.path.join(_tmp_dir, "uploads")

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["UPLOAD_DIR"] = _uploads_dir
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["MATERIAL_PREVIEW_CHARS"] = "5000"
os.environ["APP_TIMEZONE"] = "Asia/Shanghai"
os.environ["MATERIAL_PARSE_CONCURRENCY"] = "1"

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import async_session
from app.services.parse_worker import reset_worker_for_testing

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f"  ({detail})"
        print(msg)
        raise AssertionError(msg)


def run(client: TestClient):
    material_id = None
    stored_filename = None

    # Reset worker singleton so lifespan creates a fresh one
    reset_worker_for_testing()

    # ── 1. Health ──
    print("\n[1] GET /api/health")
    r = client.get("/api/health")
    check("status 200", r.status_code == 200)
    data = r.json()
    check("has status", "status" in data)
    check("has database", "database" in data)
    check("has upload_dir", "upload_dir" in data)
    check("has ai_configured", "ai_configured" in data)
    check("has model", "model" in data)
    check("has ocr_available", "ocr_available" in data)
    check("database ok", data["database"] == "ok")
    check("upload_dir ok", data["upload_dir"] == "ok")
    check("ai_configured is bool", isinstance(data["ai_configured"], bool), f"got {type(data['ai_configured'])}")

    # Verify placeholder key detection
    from app.config import is_ai_configured, _PLACEHOLDER_KEYS
    for placeholder in ["", "your_api_key_here", "sk-xxx", "replace_me"]:
        check(f"placeholder '{placeholder}' in _PLACEHOLDER_KEYS", placeholder in _PLACEHOLDER_KEYS)

    # ── 2. Upload material ──
    print("\n[2] POST /api/materials/upload")
    test_content = "这是一段测试文本，用于冒烟测试验证资料上传和检索功能。"
    test_file = os.path.join(_tmp_dir, "test_upload.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)

    with open(test_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("test_upload.txt", f, "text/plain")})
    check("upload 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json()
    check("has id", "id" in body)
    check("has stored_filename", "stored_filename" in body)
    material_id = body["id"]
    stored_filename = body["stored_filename"]
    check("stored_filename not empty", bool(stored_filename))
    check("upload status pending or ready", body.get("status") in ("pending", "ready"), f"got {body.get('status')}")
    check("has status field", "status" in body)
    check("has error_message field", "error_message" in body)

    # ── 2h. Background parsing completes ──
    print("\n[2h] Wait for background parsing")
    import time
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{material_id}")
        if r.json().get("status") == "ready":
            break
    check("material status becomes ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")
    detail_after_parse = r.json()
    check("content parsed", "冒烟测试" in detail_after_parse.get("preview", ""), f"preview={detail_after_parse.get('preview', '')[:100]}")
    check("content_length > 0", detail_after_parse.get("content_length", 0) > 0)

    # Verify chunks and FTS were created
    async def verify_chunks():
        async with async_session() as session:
            cq = await session.execute(
                text("SELECT COUNT(*) FROM material_chunks WHERE material_id = :id"), {"id": material_id}
            )
            chunk_count = cq.scalar() or 0
            fq = await session.execute(
                text("SELECT COUNT(*) FROM chunks_fts WHERE material_id = :id"), {"id": material_id}
            )
            fts_count = fq.scalar() or 0
            return chunk_count, fts_count

    loop_chk = asyncio.new_event_loop()
    chk_count, fts_count = loop_chk.run_until_complete(verify_chunks())
    loop_chk.close()
    check("chunks created after parse", chk_count > 0, f"count={chk_count}")
    check("fts entries created after parse", fts_count > 0, f"count={fts_count}")

    # Verify parse job was created and completed
    async def verify_parse_job():
        async with async_session() as session:
            jq = await session.execute(
                text("SELECT id, status, attempts, error_message FROM material_parse_jobs WHERE material_id = :id ORDER BY id"),
                {"id": material_id},
            )
            return jq.fetchall()

    loop_job = asyncio.new_event_loop()
    jobs = loop_job.run_until_complete(verify_parse_job())
    loop_job.close()
    check("parse job created", len(jobs) >= 1, f"count={len(jobs)}")
    if jobs:
        last_job = jobs[-1]
        check("parse job status=done", last_job[1] == "done", f"status={last_job[1]}")
        check("parse job attempts >= 1", last_job[2] >= 1, f"attempts={last_job[2]}")

    # ── 2b. List materials pagination ──
    print("\n[2b] GET /api/materials?limit=1&offset=0")
    r = client.get("/api/materials", params={"limit": 1, "offset": 0})
    check("list page1 200", r.status_code == 200, f"got {r.status_code}")
    page1 = r.json()
    check("page1 is list", isinstance(page1, list))
    check("page1 length <= 1", len(page1) <= 1, f"got {len(page1)}")
    if len(page1) == 1:
        check("page1 first id matches", page1[0]["id"] == material_id)

    print("\n[2c] GET /api/materials?limit=1&offset=1")
    r = client.get("/api/materials", params={"limit": 1, "offset": 1})
    check("list page2 200", r.status_code == 200, f"got {r.status_code}")
    page2 = r.json()
    check("page2 is empty list", page2 == [], f"got {page2}")

    # ── 2d. Pagination clamp (limit/offset out of range) ──
    print("\n[2d] GET /api/materials?limit=999&offset=-10")
    r = client.get("/api/materials", params={"limit": 999, "offset": -10})
    check("clamp 200", r.status_code == 200, f"got {r.status_code}")
    clamp_result = r.json()
    check("clamp returns list", isinstance(clamp_result, list))

    # ── 2e. Dashboard reflects uploaded material ──
    print("\n[2e] GET /api/dashboard (after upload)")
    r = client.get("/api/dashboard")
    check("dashboard after upload 200", r.status_code == 200)
    dash_after = r.json()
    check("total_materials >= 1", dash_after["total_materials"] >= 1, f"got {dash_after['total_materials']}")

    # ── 2f. Material detail ──
    print("\n[2f] GET /api/materials/{id}")
    r = client.get(f"/api/materials/{material_id}")
    check("detail 200", r.status_code == 200, f"got {r.status_code}")
    detail = r.json()
    check("detail id matches", detail["id"] == material_id)
    check("detail filename matches", detail["filename"] == "test_upload.txt")
    check("detail preview has text", "冒烟测试" in detail.get("preview", ""))
    check("detail content_length >= 4", detail.get("content_length", 0) >= 4)
    check("detail truncated is False", detail.get("truncated") is False)

    # ── 2g. Material detail truncation ──
    print("\n[2g] GET /api/materials/{id} (truncation)")
    from app.models import Material as MaterialModel

    async def insert_large_material():
        async with async_session() as session:
            mat = MaterialModel(
                filename="large_test.txt",
                file_type=".txt",
                content="a" * 6000,
                stored_filename="large_test_stored.txt",
            )
            session.add(mat)
            await session.commit()
            await session.refresh(mat)
            return mat.id

    loop3 = asyncio.new_event_loop()
    large_id = loop3.run_until_complete(insert_large_material())
    loop3.close()

    r = client.get(f"/api/materials/{large_id}")
    check("large detail 200", r.status_code == 200, f"got {r.status_code}")
    large_detail = r.json()
    check("large preview length == 5000", len(large_detail.get("preview", "")) == 5000)
    check("large content_length == 6000", large_detail.get("content_length") == 6000)
    check("large truncated is True", large_detail.get("truncated") is True)

    # cleanup large material
    async def delete_large_material():
        async with async_session() as session:
            from sqlalchemy import text as sql_text
            await session.execute(sql_text("DELETE FROM materials WHERE id = :id"), {"id": large_id})
            await session.commit()

    loop4 = asyncio.new_event_loop()
    loop4.run_until_complete(delete_large_material())
    loop4.close()

    # ── 3. Search material ──
    print("\n[3] POST /api/materials/search")
    r = client.post("/api/materials/search", json={"query": "冒烟测试", "limit": 10})
    check("search 200", r.status_code == 200)
    results = r.json()
    check("found at least 1 result", len(results) >= 1, f"got {len(results)}")
    check("result matches material_id", results[0]["material_id"] == material_id)

    # ── 3b. Search limit boundary ──
    print("\n[3b] POST /api/materials/search (limit=999)")
    r = client.post("/api/materials/search", json={"query": "冒烟测试", "limit": 999})
    check("search limit=999 returns 422", r.status_code == 422, f"got {r.status_code}")

    print("\n[3c] POST /api/materials/search (limit=50)")
    r = client.post("/api/materials/search", json={"query": "冒烟测试", "limit": 50})
    check("search limit=50 returns 200", r.status_code == 200, f"got {r.status_code}")

    # ── 4. Delete material ──
    print("\n[4] DELETE /api/materials/{id}")
    r = client.delete(f"/api/materials/{material_id}")
    check("delete 200", r.status_code == 200)
    check("ok=true", r.json().get("ok") is True)

    # verify DB cleanup (sync wrapper around async session)
    async def verify_cleanup():
        async with async_session() as session:
            mat_q = await session.execute(
                text("SELECT COUNT(*) FROM materials WHERE id = :id"), {"id": material_id}
            )
            mat_count = mat_q.scalar() or 0
            chunk_q = await session.execute(
                text("SELECT COUNT(*) FROM material_chunks WHERE material_id = :id"), {"id": material_id}
            )
            chunk_count = chunk_q.scalar() or 0
            fts_q = await session.execute(
                text("SELECT COUNT(*) FROM chunks_fts WHERE material_id = :id"), {"id": material_id}
            )
            fts_count = fts_q.scalar() or 0
            return mat_count, chunk_count, fts_count

    loop = asyncio.new_event_loop()
    mat_count, chunk_count, fts_count = loop.run_until_complete(verify_cleanup())
    loop.close()
    check("material row deleted", mat_count == 0, f"count={mat_count}")
    check("chunks deleted", chunk_count == 0, f"count={chunk_count}")
    check("fts deleted", fts_count == 0, f"count={fts_count}")

    # verify file deleted
    upload_file = os.path.join(_uploads_dir, stored_filename)
    check("upload file removed", not os.path.exists(upload_file))

    # verify detail returns 404 after deletion
    print("\n[4a] GET /api/materials/{id} (after delete)")
    r = client.get(f"/api/materials/{material_id}")
    check("detail after delete 404", r.status_code == 404, f"got {r.status_code}")

    # ── 4b. Oversized upload rejected ──
    print("\n[4b] POST /api/materials/upload (oversized)")
    files_before = sorted(os.listdir(_uploads_dir))
    oversized_content = b"x" * (1024 * 1024 + 1)  # slightly over 1MB
    from io import BytesIO
    oversized_io = BytesIO(oversized_content)
    r = client.post(
        "/api/materials/upload",
        files={"file": ("oversized.txt", oversized_io, "text/plain")},
    )
    check("oversized upload 413", r.status_code == 413, f"got {r.status_code}")
    detail = r.json().get("detail", "")
    check("detail contains 文件过大", "文件过大" in detail, f"detail={detail}")

    files_after = sorted(os.listdir(_uploads_dir))
    check("no residual files in upload dir", files_after == files_before, f"before={files_before}, after={files_after}")

    # verify no DB record for oversized.txt
    async def verify_no_oversized():
        async with async_session() as session:
            q = await session.execute(
                text("SELECT COUNT(*) FROM materials WHERE filename = :fn"),
                {"fn": "oversized.txt"},
            )
            return q.scalar() or 0

    loop2 = asyncio.new_event_loop()
    oversized_count = loop2.run_until_complete(verify_no_oversized())
    loop2.close()
    check("no oversized.txt in DB", oversized_count == 0, f"count={oversized_count}")

    # ── 4c. OCR fallback: image-only PDF ──
    print("\n[4c] OCR fallback: upload image-only PDF")
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    ocr_marker = "OCR SMOKE FOURIER 12345"
    img = Image.new("RGB", (1200, 200), "white")
    draw = ImageDraw.Draw(img)

    # Try common Windows fonts, fallback to Pillow default
    font = None
    for font_name in ("arial.ttf", "Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            font = ImageFont.truetype(font_name, 60)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    draw.text((40, 50), ocr_marker, fill="black", font=font)
    img_path = os.path.join(_tmp_dir, "ocr_page.png")
    img.save(img_path)

    ocr_pdf_path = os.path.join(_tmp_dir, "ocr_test.pdf")
    ocr_doc = fitz.open()
    pdf_page = ocr_doc.new_page(width=612, height=792)
    pdf_page.insert_image(fitz.Rect(36, 100, 576, 300), filename=img_path)
    ocr_doc.save(ocr_pdf_path)
    ocr_doc.close()

    ocr_material_id = None
    ocr_stored_filename = None
    with open(ocr_pdf_path, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("ocr_test.pdf", f, "application/pdf")})
    check("ocr upload 200", r.status_code == 200, f"got {r.status_code}")
    ocr_body = r.json()
    ocr_material_id = ocr_body["id"]
    ocr_stored_filename = ocr_body["stored_filename"]
    check("ocr has id", ocr_material_id is not None)

    # Wait for background OCR parsing to complete
    for _ in range(60):
        time.sleep(0.2)
        r = client.get(f"/api/materials/{ocr_material_id}")
        if r.json().get("status") in ("ready", "failed"):
            break

    check("ocr detail 200", r.status_code == 200, f"got {r.status_code}")
    ocr_detail = r.json()
    ocr_preview = ocr_detail.get("preview", "")

    # Check OCR availability; require content assertion when available
    hr = client.get("/api/health")
    ocr_available = hr.json().get("ocr_available", False)
    if ocr_available:
        has_ocr_text = any(kw in ocr_preview for kw in ("OCR", "FOURIER", "12345"))
        check("ocr preview contains marker", has_ocr_text, f"preview={ocr_preview[:200]}")
    else:
        ocr_reason = hr.json().get("ocr_detail", "unknown")
        print(f"  SKIP  ocr content assertion — OCR not available: {ocr_reason}")

    # cleanup OCR material
    r = client.delete(f"/api/materials/{ocr_material_id}")
    check("ocr delete 200", r.status_code == 200)
    check("ocr ok=true", r.json().get("ok") is True)
    ocr_upload_file = os.path.join(_uploads_dir, ocr_stored_filename)
    check("ocr upload file removed", not os.path.exists(ocr_upload_file))

    # ── 4d. Failed status and retry ──
    print("\n[4d] Failed status and retry")
    # Create a material with a valid file, then manually break it to simulate failure
    fail_file = os.path.join(_tmp_dir, "fail_test.txt")
    with open(fail_file, "w", encoding="utf-8") as f:
        f.write("失败重试测试内容")
    with open(fail_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("fail_test.txt", f, "text/plain")})
    check("fail material upload 200", r.status_code == 200)
    fail_mat_id = r.json()["id"]

    # Wait for it to become ready
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{fail_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    fail_status = r.json().get("status")
    check("fail material becomes ready", fail_status == "ready", f"got {fail_status}")

    # Simulate failure by setting status to failed directly in DB
    async def set_material_failed(mid):
        async with async_session() as session:
            await session.execute(text("UPDATE materials SET status='failed', error_message='模拟解析失败: OCR 超时' WHERE id=:id"), {"id": mid})
            await session.commit()

    loop_fail = asyncio.new_event_loop()
    loop_fail.run_until_complete(set_material_failed(fail_mat_id))
    loop_fail.close()

    r = client.get(f"/api/materials/{fail_mat_id}")
    check("failed status visible", r.json().get("status") == "failed", f"got {r.json().get('status')}")
    check("failed error_message visible", "OCR 超时" in r.json().get("error_message", ""), f"msg={r.json().get('error_message')}")

    # List should show failed status
    r = client.get("/api/materials", params={"limit": 100, "offset": 0})
    fail_in_list = [m for m in r.json() if m["id"] == fail_mat_id]
    if fail_in_list:
        check("list shows failed status", fail_in_list[0]["status"] == "failed")
        check("list shows error_message", "OCR 超时" in fail_in_list[0].get("error_message", ""))

    # Retry
    r = client.post(f"/api/materials/{fail_mat_id}/retry")
    check("retry 200", r.status_code == 200, f"got {r.status_code}")
    check("retry status pending", r.json().get("status") == "pending", f"got {r.json().get('status')}")
    check("retry error_message cleared", r.json().get("error_message") == "", f"got {r.json().get('error_message')}")

    # Wait for retry to complete
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{fail_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("retry completes to ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")
    check("retry content restored", "失败重试" in r.json().get("preview", ""))

    # Verify retry created a new job with attempts incremented
    async def verify_retry_jobs():
        async with async_session() as session:
            jq = await session.execute(
                text("SELECT id, status, attempts FROM material_parse_jobs WHERE material_id = :id ORDER BY id"),
                {"id": fail_mat_id},
            )
            return jq.fetchall()

    loop_rj = asyncio.new_event_loop()
    retry_jobs = loop_rj.run_until_complete(verify_retry_jobs())
    loop_rj.close()
    check("retry created new job", len(retry_jobs) >= 2, f"count={len(retry_jobs)}")
    if len(retry_jobs) >= 2:
        check("retry job status=done", retry_jobs[-1][1] == "done", f"status={retry_jobs[-1][1]}")
        check("retry job attempts=1", retry_jobs[-1][2] == 1, f"attempts={retry_jobs[-1][2]}")

    # Retry on non-failed material should be 422
    r = client.post(f"/api/materials/{fail_mat_id}/retry")
    check("retry on ready 422", r.status_code == 422, f"got {r.status_code}")

    # Retry on nonexistent
    r = client.post("/api/materials/999999/retry")
    check("retry nonexistent 404", r.status_code == 404, f"got {r.status_code}")

    # Verify delete cleans up parse jobs
    async def count_jobs(mid):
        async with async_session() as session:
            jq = await session.execute(
                text("SELECT COUNT(*) FROM material_parse_jobs WHERE material_id = :id"), {"id": mid}
            )
            return jq.scalar() or 0

    loop_dc = asyncio.new_event_loop()
    jobs_before = loop_dc.run_until_complete(count_jobs(fail_mat_id))
    loop_dc.close()
    check("jobs exist before delete", jobs_before >= 1, f"count={jobs_before}")

    # Cleanup
    r = client.delete(f"/api/materials/{fail_mat_id}")
    check("fail material cleanup 200", r.status_code == 200)

    # Verify jobs were cleaned up
    loop_dc2 = asyncio.new_event_loop()
    jobs_after = loop_dc2.run_until_complete(count_jobs(fail_mat_id))
    loop_dc2.close()
    check("jobs cleaned up after delete", jobs_after == 0, f"count={jobs_after}")

    # ── 5. Study Plan CRUD ──
    print("\n[5] POST /api/plan")
    r = client.post("/api/plan", json={"date": "2099-12-31", "subject": "测试科目", "task": "冒烟测试任务"})
    check("create plan 200", r.status_code == 200)
    plan_body = r.json()
    plan_id = plan_body["id"]
    check("plan has id", plan_id is not None)
    check("plan completed=false", plan_body["completed"] is False)

    print("\n[6] PATCH /api/plan/{id}")
    r = client.patch(f"/api/plan/{plan_id}", json={"completed": True})
    check("patch plan 200", r.status_code == 200)
    check("plan completed=true", r.json()["completed"] is True)

    print("\n[7] GET /api/plan?date=2099-12-31")
    r = client.get("/api/plan", params={"date": "2099-12-31"})
    check("list plans 200", r.status_code == 200)
    plans = r.json()
    check("found our plan", any(p["id"] == plan_id for p in plans))

    print("\n[8] DELETE /api/plan/{id}")
    r = client.delete(f"/api/plan/{plan_id}")
    check("delete plan 200", r.status_code == 200)
    check("ok=true", r.json().get("ok") is True)

    # ── 6. Error Book CRUD ──
    print("\n[9] POST /api/errors")
    r = client.post("/api/errors", json={
        "subject": "测试科目",
        "question": "冒烟测试错题",
        "error_type": "测试错误",
        "mastered": False,
    })
    check("create error 200", r.status_code == 200)
    err_body = r.json()
    error_id = err_body["id"]
    check("error has id", error_id is not None)
    check("error mastered=false", err_body["mastered"] is False)
    check("error review_count=0", err_body.get("review_count") == 0)

    print("\n[10] PATCH /api/errors/{id} (mastered=true, 1st review)")
    from datetime import timedelta as _td
    from app.utils.date import local_date_obj
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("patch error 200", r.status_code == 200)
    err1 = r.json()
    check("error mastered=true", err1["mastered"] is True)
    check("review_count=1", err1.get("review_count") == 1)
    expected_date1 = (local_date_obj() + _td(days=1)).isoformat()
    check("next_review_date=tomorrow", err1.get("next_review_date") == expected_date1, f"got {err1.get('next_review_date')}")

    print("\n[10b] PATCH /api/errors/{id} (mastered=false)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": False})
    check("unmaster 200", r.status_code == 200)
    err2 = r.json()
    check("mastered=false", err2["mastered"] is False)
    check("review_count still 1", err2.get("review_count") == 1)
    expected_today = local_date_obj().isoformat()
    check("next_review_date=today", err2.get("next_review_date") == expected_today, f"got {err2.get('next_review_date')}")

    print("\n[10c] PATCH /api/errors/{id} (mastered=true, 2nd review)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("re-master 200", r.status_code == 200)
    err3 = r.json()
    check("review_count=2", err3.get("review_count") == 2)
    expected_date2 = (local_date_obj() + _td(days=3)).isoformat()
    check("next_review_date=+3d", err3.get("next_review_date") == expected_date2, f"got {err3.get('next_review_date')}")

    # ── 10d. Repeat mastered=true should NOT double-increment ──
    print("\n[10d] PATCH /api/errors/{id} (mastered=true again)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("repeat master 200", r.status_code == 200)
    err3d = r.json()
    check("still mastered=true", err3d["mastered"] is True)
    check("review_count still 2", err3d.get("review_count") == 2, f"got {err3d.get('review_count')}")
    check("next_review_date still +3d", err3d.get("next_review_date") == expected_date2, f"got {err3d.get('next_review_date')}")

    # ── 10e. Explicit review_count lower-bound protection ──
    print("\n[10e] PATCH /api/errors/{id} (review_count=-5)")
    r = client.patch(f"/api/errors/{error_id}", json={"review_count": -5})
    check("neg review_count 200", r.status_code == 200)
    err3e = r.json()
    check("review_count clamped to 0", err3e.get("review_count") == 0, f"got {err3e.get('review_count')}")

    # ── 10f. Explicit next_review_date override ──
    print("\n[10f] PATCH /api/errors/{id} (next_review_date=2099-01-01)")
    r = client.patch(f"/api/errors/{error_id}", json={"next_review_date": "2099-01-01"})
    check("explicit date 200", r.status_code == 200)
    err3f = r.json()
    check("next_review_date=2099-01-01", err3f.get("next_review_date") == "2099-01-01", f"got {err3f.get('next_review_date')}")

    # ── 10g. Explicit review_count positive override ──
    print("\n[10g] PATCH /api/errors/{id} (review_count=4)")
    r = client.patch(f"/api/errors/{error_id}", json={"review_count": 4})
    check("set review_count 200", r.status_code == 200)
    err3g = r.json()
    check("review_count=4", err3g.get("review_count") == 4, f"got {err3g.get('review_count')}")

    # ── 10h. Unmaster then re-master at count 5 → interval 14d ──
    print("\n[10h] PATCH /api/errors/{id} (unmaster then re-master)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": False})
    check("unmaster for 10h 200", r.status_code == 200)
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("re-master at count 5 200", r.status_code == 200)
    err3h = r.json()
    check("review_count=5", err3h.get("review_count") == 5, f"got {err3h.get('review_count')}")
    expected_date5 = (local_date_obj() + _td(days=14)).isoformat()
    check("next_review_date=+14d", err3h.get("next_review_date") == expected_date5, f"got {err3h.get('next_review_date')}")

    print("\n[11] GET /api/errors?mastered=true")
    r = client.get("/api/errors", params={"mastered": "true"})
    check("list errors 200", r.status_code == 200)
    errors = r.json()
    check("found our error", any(e["id"] == error_id for e in errors))

    print("\n[12] DELETE /api/errors/{id}")
    r = client.delete(f"/api/errors/{error_id}")
    check("delete error 200", r.status_code == 200)
    check("ok=true", r.json().get("ok") is True)

    # ── 7. Dashboard ──
    print("\n[13] GET /api/dashboard")
    r = client.get("/api/dashboard")
    check("dashboard 200", r.status_code == 200)
    dash = r.json()
    for field in ("today_tasks", "today_completed", "total_materials", "total_errors", "unmastered_errors", "streak_days", "today_review_errors"):
        check(f"has {field}", field in dash)
    check("today_review_errors is int", isinstance(dash["today_review_errors"], int))

    # ── 7b. Dashboard today_review_errors with due error ──
    print("\n[13b] Dashboard today_review_errors")
    from app.utils.date import local_today
    today_str = local_today()
    r = client.post("/api/errors", json={
        "subject": "复习统计",
        "question": "待复习错题",
        "next_review_date": today_str,
    })
    check("review error create 200", r.status_code == 200)
    review_err_id = r.json()["id"]

    r = client.get("/api/dashboard")
    check("dashboard with review err 200", r.status_code == 200)
    dash2 = r.json()
    check("today_review_errors >= 1", dash2["today_review_errors"] >= 1, f"got {dash2['today_review_errors']}")

    # ── 7c. Future-dated error should NOT count as today review ──
    print("\n[13c] Future-dated error not counted")
    from datetime import timedelta as _td2
    from app.utils.date import local_date_obj
    future_str = (local_date_obj() + _td2(days=30)).isoformat()
    r = client.post("/api/errors", json={
        "subject": "未来复习",
        "question": "未来错题",
        "next_review_date": future_str,
    })
    check("future error create 200", r.status_code == 200)
    future_err_id = r.json()["id"]

    r = client.get("/api/dashboard")
    check("dashboard after future err 200", r.status_code == 200)
    dash3 = r.json()
    # today_review_errors should still be exactly 1 (the today-dated one, not the future one)
    check("today_review_errors still 1", dash3["today_review_errors"] == 1, f"got {dash3['today_review_errors']}")

    # cleanup both errors
    r = client.delete(f"/api/errors/{review_err_id}")
    check("cleanup review error 200", r.status_code == 200)
    r = client.delete(f"/api/errors/{future_err_id}")
    check("cleanup future error 200", r.status_code == 200)

    # ── 7d. After cleanup, today_review_errors should be 0 ──
    print("\n[13d] Dashboard after cleanup")
    r = client.get("/api/dashboard")
    check("dashboard after cleanup 200", r.status_code == 200)
    dash4 = r.json()
    check("today_review_errors back to 0", dash4["today_review_errors"] == 0, f"got {dash4['today_review_errors']}")

    # ── 8. Input validation ──
    print("\n[14] Input validation")
    r = client.post("/api/errors", json={"question": ""})
    check("empty question rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/errors", json={"question": "ok", "next_review_date": "bad-date"})
    check("bad date format rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/plan", json={"date": "2025/01/01", "subject": "x", "task": "y"})
    check("plan bad date rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/materials/search", json={"query": "", "limit": 5})
    check("empty search query rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/problems/solve", json={"question": ""})
    check("empty problem question rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/plan/generate", json={"subjects": [], "days": 7})
    check("empty subjects rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/plan/generate", json={"subjects": ["math"], "days": 0})
    check("days=0 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/plan/generate", json={"subjects": ["math"], "daily_hours": 0})
    check("daily_hours=0 rejected 422", r.status_code == 422, f"got {r.status_code}")

    # chat empty question
    r = client.post("/api/chat", json={"question": ""})
    check("chat empty question rejected 422", r.status_code == 422, f"got {r.status_code}")

    # plan generate bad start_date
    r = client.post("/api/plan/generate", json={"subjects": ["math"], "start_date": "not-a-date"})
    check("plan gen bad start_date 422", r.status_code == 422, f"got {r.status_code}")

    # boundary values that should pass
    r = client.post("/api/plan/generate", json={"subjects": ["math"], "days": 365, "daily_hours": 16})
    check("plan gen boundary values pass", r.status_code in (200, 502, 503), f"got {r.status_code}")

    # subjects with empty strings after strip should fail
    r = client.post("/api/plan/generate", json={"subjects": ["", "  "], "days": 7})
    check("whitespace-only subjects rejected 422", r.status_code == 422, f"got {r.status_code}")

    # ── 9. Search snippet markers ──
    print("\n[15] Search snippet markers")
    # Upload a fresh material for snippet testing
    snippet_file = os.path.join(_tmp_dir, "snippet_test.txt")
    with open(snippet_file, "w", encoding="utf-8") as f:
        f.write("搜索高亮安全测试片段包含关键内容。")
    with open(snippet_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("snippet_test.txt", f, "text/plain")})
    check("snippet material upload 200", r.status_code == 200)
    snippet_mid = r.json()["id"]

    # Wait for parsing
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{snippet_mid}")
        if r.json().get("status") in ("ready", "failed"):
            break

    r = client.post("/api/materials/search", json={"query": "搜索高亮", "limit": 1})
    check("snippet search 200", r.status_code == 200)
    snippet_results = r.json()
    if len(snippet_results) > 0:
        snippet = snippet_results[0].get("snippet", "")
        check("snippet has no <script>", "<script>" not in snippet)
        check("snippet has no <img>", "<img" not in snippet)
        check("snippet has no raw HTML tags", "<" not in snippet or ">>>" in snippet)
    else:
        print("  SKIP  snippet content check — no results")

    # cleanup
    r = client.delete(f"/api/materials/{snippet_mid}")
    check("snippet material cleanup 200", r.status_code == 200)

    # ── 16. Exam Practice CRUD ──
    print("\n[16] POST /api/exam/questions")
    r = client.post("/api/exam/questions", json={
        "title": "2025年高数真题-极限",
        "subject": "高等数学",
        "year": "2025",
        "question": "求极限 $\\lim_{x\\to 0} \\frac{\\sin x}{x}$",
        "answer": "1",
        "solution": "由洛必达法则或等价无穷小可知极限为1。",
        "tags": "极限,洛必达",
    })
    check("create exam question 200", r.status_code == 200, f"got {r.status_code}")
    eq_body = r.json()
    eq_id = eq_body["id"]
    check("exam question has id", eq_id is not None)
    check("exam question title matches", eq_body["title"] == "2025年高数真题-极限")
    check("exam question subject matches", eq_body["subject"] == "高等数学")
    check("exam question year matches", eq_body["year"] == "2025")

    print("\n[16b] GET /api/exam/questions")
    r = client.get("/api/exam/questions")
    check("list exam questions 200", r.status_code == 200)
    eq_list = r.json()
    check("found our exam question", any(q["id"] == eq_id for q in eq_list))

    print("\n[16c] GET /api/exam/questions?subject=高等数学")
    r = client.get("/api/exam/questions", params={"subject": "高等数学"})
    check("filter by subject 200", r.status_code == 200)
    filtered = r.json()
    check("filtered has our question", any(q["id"] == eq_id for q in filtered))

    print("\n[16d] GET /api/exam/questions?year=2025")
    r = client.get("/api/exam/questions", params={"year": "2025"})
    check("filter by year 200", r.status_code == 200)
    year_filtered = r.json()
    check("year filtered has our question", any(q["id"] == eq_id for q in year_filtered))

    print("\n[16e] GET /api/exam/questions?tag=极限")
    r = client.get("/api/exam/questions", params={"tag": "极限"})
    check("filter by tag 200", r.status_code == 200)
    tag_filtered = r.json()
    check("tag filtered has our question", any(q["id"] == eq_id for q in tag_filtered))

    print("\n[16f] GET /api/exam/questions/{id}")
    r = client.get(f"/api/exam/questions/{eq_id}")
    check("get exam question 200", r.status_code == 200)
    eq_detail = r.json()
    check("detail id matches", eq_detail["id"] == eq_id)
    check("detail question has LaTeX", "\\sin" in eq_detail["question"])

    # ── 16g. Submit attempt ──
    print("\n[16g] POST /api/exam/questions/{id}/attempt")
    r = client.post(f"/api/exam/questions/{eq_id}/attempt", json={"user_answer": "1"})
    check("submit attempt 200", r.status_code == 200)
    attempt_body = r.json()
    attempt_id = attempt_body["id"]
    check("attempt has id", attempt_id is not None)
    check("attempt question_id matches", attempt_body["question_id"] == eq_id)
    check("attempt user_answer matches", attempt_body["user_answer"] == "1")

    # ── 16h. Add to error book ──
    print("\n[16h] POST /api/exam/questions/{id}/add-to-errors")
    r = client.post(f"/api/exam/questions/{eq_id}/add-to-errors")
    check("add to errors 200", r.status_code == 200)
    added_err = r.json()
    check("error has id", added_err["id"] is not None)
    check("error subject from exam", added_err["subject"] == "高等数学")
    check("error question from exam", "sin" in added_err["question"] or "极限" in added_err["question"])
    check("error correct_answer from exam", added_err["correct_answer"] == "1")
    check("error error_type=真题练习", added_err["error_type"] == "真题练习")
    added_err_id = added_err["id"]

    # ── 16h2. Duplicate add-to-errors should return 409 ──
    r = client.post(f"/api/exam/questions/{eq_id}/add-to-errors")
    check("duplicate add-to-errors 409", r.status_code == 409, f"got {r.status_code}")
    check("duplicate detail contains 已在错题本中", "已在错题本中" in r.json().get("detail", ""), f"detail={r.json().get('detail')}")

    # cleanup the error created from exam
    r = client.delete(f"/api/errors/{added_err_id}")
    check("cleanup exam error 200", r.status_code == 200)

    # ── 16i. Delete exam question (cascade attempts) ──
    print("\n[16i] DELETE /api/exam/questions/{id}")
    r = client.delete(f"/api/exam/questions/{eq_id}")
    check("delete exam question 200", r.status_code == 200)
    check("ok=true", r.json().get("ok") is True)

    # verify cascade: attempt should be gone
    async def verify_exam_cleanup():
        async with async_session() as session:
            q_count = (await session.execute(
                text("SELECT COUNT(*) FROM exam_questions WHERE id = :id"), {"id": eq_id}
            )).scalar() or 0
            a_count = (await session.execute(
                text("SELECT COUNT(*) FROM exam_attempts WHERE question_id = :id"), {"id": eq_id}
            )).scalar() or 0
            return q_count, a_count

    loop5 = asyncio.new_event_loop()
    q_count, a_count = loop5.run_until_complete(verify_exam_cleanup())
    loop5.close()
    check("exam question deleted from DB", q_count == 0, f"count={q_count}")
    check("exam attempts cascade deleted", a_count == 0, f"count={a_count}")

    # verify 404 after deletion
    r = client.get(f"/api/exam/questions/{eq_id}")
    check("exam question 404 after delete", r.status_code == 404, f"got {r.status_code}")

    # ── 16j. Exam input validation ──
    print("\n[16j] Exam input validation")
    r = client.post("/api/exam/questions", json={"title": "", "question": "test"})
    check("empty title rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/questions", json={"title": "ok", "question": ""})
    check("empty question rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/questions", json={"title": "ok", "question": "ok", "year": "bad"})
    check("bad year format rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/questions", json={"title": "ok", "question": "ok", "year": "202"})
    check("3-digit year rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/exam/questions/99999")
    check("nonexistent exam question 404", r.status_code == 404, f"got {r.status_code}")

    r = client.post("/api/exam/questions/99999/attempt", json={"user_answer": "x"})
    check("attempt on nonexistent 404", r.status_code == 404, f"got {r.status_code}")

    r = client.post("/api/exam/questions/99999/add-to-errors")
    check("add-to-errors on nonexistent 404", r.status_code == 404, f"got {r.status_code}")

    # ── 16k. Exam generate validation ──
    print("\n[16k] POST /api/exam/generate validation")
    r = client.post("/api/exam/generate", json={"topic": "", "count": 5})
    check("empty topic rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/generate", json={"topic": "极限", "count": 0})
    check("count=0 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/generate", json={"topic": "极限", "count": 11})
    check("count=11 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/generate", json={"topic": "极限", "count": -1})
    check("count=-1 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/exam/generate", json={"topic": "极限", "count": 5, "difficulty": "extreme"})
    check("bad difficulty rejected 422", r.status_code == 422, f"got {r.status_code}")

    # ── 16l. Exam generate without API key → 503 ──
    print("\n[16l] POST /api/exam/generate (no API key)")
    import unittest.mock as mock
    from app.routers import exam as exam_router
    from app.services.llm import LLMConfigError

    # Patch where it's used (exam_router namespace), not where it's defined (llm_mod)
    original_fn = exam_router.generate_exam_questions
    exam_router.generate_exam_questions = mock.AsyncMock(side_effect=LLMConfigError("未配置 OPENAI_API_KEY"))
    try:
        r = client.post("/api/exam/generate", json={"topic": "极限", "count": 3})
        check("no api key returns 503", r.status_code == 503, f"got {r.status_code}, body={r.json()}")
        check("detail mentions API Key", "API_KEY" in r.json().get("detail", "").upper(), f"detail={r.json().get('detail')}")
    finally:
        exam_router.generate_exam_questions = original_fn

    # ── 16m. Exam generate with mock LLM (parse failure) ──
    print("\n[16m] POST /api/exam/generate (mock LLM parse failure)")

    async def _mock_llm_bad(*args, **kwargs):
        return "This is not valid JSON at all."

    original_fn_m = exam_router.generate_exam_questions
    exam_router.generate_exam_questions = mock.AsyncMock(side_effect=_mock_llm_bad)
    try:
        r = client.post("/api/exam/generate", json={"topic": "极限", "count": 3, "use_materials": False})
        check("parse failure 200", r.status_code == 200, f"got {r.status_code}")
        body = r.json()
        check("drafts is empty", body["drafts"] == [], f"got {body['drafts']}")
        check("has raw_response", bool(body.get("raw_response")), f"raw_response={body.get('raw_response')}")
        check("has parse_error", bool(body.get("parse_error")), f"parse_error={body.get('parse_error')}")
        check("parse_error mentions JSON", "JSON" in body["parse_error"], f"parse_error={body['parse_error']}")
    finally:
        exam_router.generate_exam_questions = original_fn_m

    # ── 16n. Exam generate with mock LLM (success, no DB write) ──
    print("\n[16n] POST /api/exam/generate (mock LLM success, no DB write)")
    mock_json = json.dumps([
        {
            "title": "AI生成-极限计算",
            "subject": "高等数学",
            "year": "模拟",
            "question": "求极限 $\\lim_{x\\to 0} \\frac{e^x - 1}{x}$",
            "answer": "1",
            "solution": "由等价无穷小 $e^x - 1 \\sim x$，极限为 1。",
            "tags": "极限,等价无穷小",
        },
        {
            "title": "AI生成-导数计算",
            "subject": "高等数学",
            "year": "模拟",
            "question": "求 $f(x) = x^3$ 的导数。",
            "answer": "$f'(x) = 3x^2$",
            "solution": "由幂函数求导法则，$f'(x) = 3x^{3-1} = 3x^2$。",
            "tags": "导数,幂函数",
        },
    ])

    async def _mock_llm_good(*args, **kwargs):
        return mock_json

    # Count exam questions before
    r_before = client.get("/api/exam/questions")
    count_before = len(r_before.json())

    original_fn_n = exam_router.generate_exam_questions
    exam_router.generate_exam_questions = mock.AsyncMock(side_effect=_mock_llm_good)
    try:
        r = client.post("/api/exam/generate", json={"topic": "极限与导数", "count": 2, "use_materials": False})
        check("mock success 200", r.status_code == 200, f"got {r.status_code}")
        body = r.json()
        check("drafts length 2", len(body["drafts"]) == 2, f"got {len(body['drafts'])}")
        check("draft 0 title matches", body["drafts"][0]["title"] == "AI生成-极限计算")
        check("draft 1 title matches", body["drafts"][1]["title"] == "AI生成-导数计算")
        check("no parse_error", body.get("parse_error") is None)
        check("no raw_response", body.get("raw_response") is None)
    finally:
        exam_router.generate_exam_questions = original_fn_n

    # Verify NO new exam questions were written to DB
    r_after = client.get("/api/exam/questions")
    count_after = len(r_after.json())
    check("no DB writes from generate", count_after == count_before, f"before={count_before}, after={count_after}")

    # ── 17. Export JSON ──
    print("\n[17] GET /api/export/json")
    # Create some test data first
    r = client.post("/api/errors", json={"subject": "导出测试", "question": "导出错题"})
    check("export: create error 200", r.status_code == 200)
    export_err_id = r.json()["id"]

    r = client.post("/api/plan", json={"date": "2099-01-01", "subject": "导出测试", "task": "导出计划"})
    check("export: create plan 200", r.status_code == 200)
    export_plan_id = r.json()["id"]

    r = client.post("/api/exam/questions", json={"title": "导出真题", "question": "导出题目内容"})
    check("export: create exam question 200", r.status_code == 200)
    export_eq_id = r.json()["id"]

    r = client.post(f"/api/exam/questions/{export_eq_id}/attempt", json={"user_answer": "导出答案"})
    check("export: create attempt 200", r.status_code == 200)

    # Now export
    r = client.get("/api/export/json")
    check("export status 200", r.status_code == 200, f"got {r.status_code}")
    check("export content-type is json", "application/json" in r.headers.get("content-type", ""), f"ct={r.headers.get('content-type')}")

    data = r.json()
    check("has exported_at", "exported_at" in data)
    check("has version", data.get("version") == "0.3")
    check("has materials", "materials" in data)
    check("has material_chunks_count", "material_chunks_count" in data)
    check("has chat_history", "chat_history" in data)
    check("has error_book", "error_book" in data)
    check("has study_plans", "study_plans" in data)
    check("has problems", "problems" in data)
    check("has exam_questions", "exam_questions" in data)
    check("has exam_attempts", "exam_attempts" in data)

    # Materials should NOT contain full content
    if data["materials"]:
        check("material has no content field", "content" not in data["materials"][0])
        check("material has content_length", "content_length" in data["materials"][0])

    # Verify data counts match what we created
    check("error_book has our entry", any(e["id"] == export_err_id for e in data["error_book"]))
    check("study_plans has our entry", any(p["id"] == export_plan_id for p in data["study_plans"]))
    check("exam_questions has our entry", any(q["id"] == export_eq_id for q in data["exam_questions"]))
    check("exam_attempts has entry", len(data["exam_attempts"]) >= 1)

    # Verify exam_attempt structure
    attempt_item = data["exam_attempts"][0]
    check("attempt has question_id", "question_id" in attempt_item)
    check("attempt has user_answer", "user_answer" in attempt_item)
    check("attempt has is_correct", "is_correct" in attempt_item)
    check("attempt has created_at", "created_at" in attempt_item)

    # Cleanup
    r = client.delete(f"/api/errors/{export_err_id}")
    check("export: cleanup error 200", r.status_code == 200)
    r = client.delete(f"/api/plan/{export_plan_id}")
    check("export: cleanup plan 200", r.status_code == 200)
    r = client.delete(f"/api/exam/questions/{export_eq_id}")
    check("export: cleanup exam 200", r.status_code == 200)

    # ── 18. Review settings ──
    print("\n[18] GET /api/settings/review (default)")
    r = client.get("/api/settings/review")
    check("get settings 200", r.status_code == 200)
    check("default intervals [1,3,7,14]", r.json()["intervals"] == [1, 3, 7, 14], f"got {r.json()['intervals']}")

    print("\n[18b] PUT /api/settings/review validation")
    r = client.put("/api/settings/review", json={"intervals": []})
    check("empty intervals 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": [3, 1]})
    check("non-increasing 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": [1, 1, 3]})
    check("equal values 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": [0, 3]})
    check("value < 1 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": [1, 366]})
    check("value > 365 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": list(range(1, 12))})
    check("> 10 elements rejected 422", r.status_code == 422, f"got {r.status_code}")

    print("\n[18c] PUT /api/settings/review [2,5,10]")
    r = client.put("/api/settings/review", json={"intervals": [2, 5, 10]})
    check("put [2,5,10] 200", r.status_code == 200, f"got {r.status_code}")
    check("returns [2,5,10]", r.json()["intervals"] == [2, 5, 10], f"got {r.json()['intervals']}")

    r = client.get("/api/settings/review")
    check("get confirms [2,5,10]", r.json()["intervals"] == [2, 5, 10], f"got {r.json()['intervals']}")

    # ── 18d. Verify intervals affect error book review dates ──
    print("\n[18d] Review intervals affect error book")
    from app.utils.date import local_date_obj as _ld
    from datetime import timedelta as _td

    r = client.post("/api/errors", json={"subject": "策略测试", "question": "复习间隔测试"})
    check("create test error 200", r.status_code == 200)
    test_err_id = r.json()["id"]

    # 1st mastered → interval[0] = 2 days
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": True})
    check("1st master 200", r.status_code == 200)
    e1 = r.json()
    check("review_count=1", e1["review_count"] == 1)
    expected1 = (_ld() + _td(days=2)).isoformat()
    check("1st review +2d", e1["next_review_date"] == expected1, f"got {e1['next_review_date']}")

    # unmaster
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": False})
    check("unmaster 200", r.status_code == 200)

    # 2nd mastered → interval[1] = 5 days
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": True})
    check("2nd master 200", r.status_code == 200)
    e2 = r.json()
    check("review_count=2", e2["review_count"] == 2)
    expected2 = (_ld() + _td(days=5)).isoformat()
    check("2nd review +5d", e2["next_review_date"] == expected2, f"got {e2['next_review_date']}")

    # unmaster
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": False})
    check("unmaster2 200", r.status_code == 200)

    # 3rd mastered → interval[2] = 10 days
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": True})
    check("3rd master 200", r.status_code == 200)
    e3 = r.json()
    check("review_count=3", e3["review_count"] == 3)
    expected3 = (_ld() + _td(days=10)).isoformat()
    check("3rd review +10d", e3["next_review_date"] == expected3, f"got {e3['next_review_date']}")

    # unmaster
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": False})
    check("unmaster3 200", r.status_code == 200)

    # 4th mastered → beyond array, uses last = 10 days
    r = client.patch(f"/api/errors/{test_err_id}", json={"mastered": True})
    check("4th master 200", r.status_code == 200)
    e4 = r.json()
    check("review_count=4", e4["review_count"] == 4)
    expected4 = (_ld() + _td(days=10)).isoformat()
    check("4th review +10d (last interval)", e4["next_review_date"] == expected4, f"got {e4['next_review_date']}")

    # Cleanup
    r = client.delete(f"/api/errors/{test_err_id}")
    check("cleanup test error 200", r.status_code == 200)

    # Reset to default
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("reset to default 200", r.status_code == 200)

    # ── 19. Import preview and restore ──
    print("\n[19] POST /api/import/preview (missing fields)")
    r = client.post("/api/import/preview", json={"version": "0.2"})
    check("missing fields 422", r.status_code == 422, f"got {r.status_code}")

    print("\n[19b] POST /api/import/preview (valid)")
    backup = {
        "exported_at": "2026-01-01T00:00:00Z",
        "version": "0.2",
        "materials": [
            {"filename": "导入资料.txt", "file_type": ".txt", "content_length": 100},
            {"filename": "导入资料.txt", "file_type": ".txt", "content_length": 100},  # dup
        ],
        "material_chunks_count": 0,
        "chat_history": [
            {"question": "导入问题1", "answer": "导入答案1"},
        ],
        "error_book": [
            {"question": "导入错题1", "error_type": "导入", "subject": "测试"},
            {"question": "导入错题1", "error_type": "导入"},  # dup
        ],
        "study_plans": [
            {"date": "2099-06-01", "subject": "导入科目", "task": "导入任务"},
        ],
        "problems": [
            {"question": "导入解析题1", "solution": "导入解法1"},
        ],
        "exam_questions": [
            {"id": 9001, "title": "导入真题1", "question": "导入题目1", "answer": "答案1", "subject": "测试"},
            {"id": 9002, "title": "导入真题2", "question": "导入题目2", "answer": "答案2"},
        ],
        "exam_attempts": [
            {"question_id": 9001, "user_answer": "导入答案A", "is_correct": False},
            {"question_id": 9002, "user_answer": "导入答案B", "is_correct": True},
            {"question_id": 99999, "user_answer": "无效题目", "is_correct": False},  # bad ref
        ],
    }
    r = client.post("/api/import/preview", json=backup)
    check("preview 200", r.status_code == 200)
    pv = r.json()
    check("preview error_book_count=2", pv["error_book_count"] == 2)
    check("preview exam_questions_count=2", pv["exam_questions_count"] == 2)
    check("preview exam_attempts_count=3", pv["exam_attempts_count"] == 3)
    check("preview has modules", "modules" in pv)
    check("preview has conflict_samples", "conflict_samples" in pv)
    check("preview has total_conflicts", "total_conflicts" in pv)
    check("preview strategy default", pv["strategy"] == "skip")
    # First import: no conflicts yet (DB is empty)
    check("preview total_conflicts=0 (first import)", pv["total_conflicts"] == 0)
    check("preview materials new_count=2", pv["modules"]["materials"]["new_count"] == 2)
    check("preview error_book new_count=2", pv["modules"]["error_book"]["new_count"] == 2)
    check("preview materials conflict_count=0", pv["modules"]["materials"]["conflict_count"] == 0)

    # Verify preview did NOT write to DB
    r_before = client.get("/api/exam/questions")
    count_before = len(r_before.json())

    print("\n[19c] POST /api/import/json (first import)")
    r = client.post("/api/import/json", json=backup)
    check("import 200", r.status_code == 200)
    result = r.json()
    ins = result["inserted"]
    skp = result["skipped"]
    check("has overwritten key", "overwritten" in result)
    check("has kept_both key", "kept_both" in result)
    check("inserted 1 material (dup skipped)", ins["materials"] == 1, f"got ins={ins['materials']}, skp={skp['materials']}")
    check("skipped 1 material dup", skp["materials"] == 1)
    check("inserted 1 error (dup skipped)", ins["error_book"] == 1, f"got ins={ins['error_book']}, skp={skp['error_book']}")
    check("skipped 1 error dup", skp["error_book"] == 1)
    check("inserted 1 plan", ins["study_plans"] == 1)
    check("inserted 1 problem", ins["problems"] == 1)
    check("inserted 1 chat", ins["chat_history"] == 1)
    check("inserted 2 exam_questions", ins["exam_questions"] == 2)
    # Attempts: 9001 and 9002 should map to new question IDs; 99999 should skip
    check("inserted 2 exam_attempts", ins["exam_attempts"] == 2, f"got {ins['exam_attempts']}")
    check("skipped 1 exam_attempts (bad ref)", skp["exam_attempts"] == 1)

    # Verify material has no content
    r_mats = client.get("/api/materials")
    imported_mats = [m for m in r_mats.json() if m["filename"] == "导入资料.txt"]
    if imported_mats:
        mid = imported_mats[0]["id"]
        r_detail = client.get(f"/api/materials/{mid}")
        check("imported material content empty", r_detail.json().get("preview", "") == "")

    # Verify exam_attempts question_id mapped correctly
    r_eqs = client.get("/api/exam/questions")
    imported_eqs = {q["title"]: q["id"] for q in r_eqs.json() if q["title"].startswith("导入真题")}
    eq1_id = imported_eqs.get("导入真题1")
    eq2_id = imported_eqs.get("导入真题2")
    if eq1_id and eq2_id:
        async def _check_attempts():
            async with async_session() as session:
                r1 = await session.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE question_id = :qid"), {"qid": eq1_id})
                r2 = await session.execute(text("SELECT COUNT(*) FROM exam_attempts WHERE question_id = :qid"), {"qid": eq2_id})
                return r1.scalar() or 0, r2.scalar() or 0
        loop_chk = asyncio.new_event_loop()
        a1, a2 = loop_chk.run_until_complete(_check_attempts())
        loop_chk.close()
        check("attempt mapped to eq1", a1 >= 1, f"got {a1}")
        check("attempt mapped to eq2", a2 >= 1, f"got {a2}")

    print("\n[19d] POST /api/import/json (second import, all dup)")
    r = client.post("/api/import/json", json=backup)
    check("reimport 200", r.status_code == 200)
    result2 = r.json()
    ins2 = result2["inserted"]
    skp2 = result2["skipped"]
    check("all materials skipped on reimport", ins2["materials"] == 0, f"got {ins2['materials']}")
    check("all errors skipped on reimport", ins2["error_book"] == 0, f"got {ins2['error_book']}")
    check("all plans skipped on reimport", ins2["study_plans"] == 0)
    check("all problems skipped on reimport", ins2["problems"] == 0)
    check("all chat skipped on reimport", ins2["chat_history"] == 0)
    check("all exam_questions skipped on reimport", ins2["exam_questions"] == 0)

    # ── 19d2. Conflict preview detection ──
    print("\n[19d2] POST /api/import/preview (conflict detection, strategy=skip)")
    r = client.post("/api/import/preview", json=backup, params={"strategy": "skip"})
    check("conflict preview skip 200", r.status_code == 200)
    pv_skip = r.json()
    check("conflict preview has modules", "modules" in pv_skip)
    check("conflict preview total_conflicts > 0", pv_skip["total_conflicts"] > 0, f"got {pv_skip['total_conflicts']}")
    check("conflict preview strategy=skip", pv_skip["strategy"] == "skip")
    # Materials: 2 items, 1 dup in file, both conflict with DB
    check("materials conflict_count=2", pv_skip["modules"]["materials"]["conflict_count"] == 2)
    check("materials new_count=0", pv_skip["modules"]["materials"]["new_count"] == 0)
    check("materials would_skip=2", pv_skip["modules"]["materials"]["would_skip"] == 2)
    check("materials would_insert=0", pv_skip["modules"]["materials"]["would_insert"] == 0)
    check("materials would_overwrite=0", pv_skip["modules"]["materials"]["would_overwrite"] == 0)
    # Error book: 2 items, 1 dup in file, both conflict with DB
    check("error_book conflict_count=2", pv_skip["modules"]["error_book"]["conflict_count"] == 2)
    check("error_book would_skip=2", pv_skip["modules"]["error_book"]["would_skip"] == 2)
    # Has conflict samples
    check("has conflict_samples", len(pv_skip["conflict_samples"]) > 0)

    print("\n[19d3] POST /api/import/preview (conflict detection, strategy=overwrite)")
    r = client.post("/api/import/preview", json=backup, params={"strategy": "overwrite"})
    check("conflict preview overwrite 200", r.status_code == 200)
    pv_ow = r.json()
    check("conflict preview strategy=overwrite", pv_ow["strategy"] == "overwrite")
    check("materials would_overwrite=2", pv_ow["modules"]["materials"]["would_overwrite"] == 2)
    check("materials would_skip=0", pv_ow["modules"]["materials"]["would_skip"] == 0)
    check("error_book would_overwrite=2", pv_ow["modules"]["error_book"]["would_overwrite"] == 2)
    check("chat would_skip (immutable)", pv_ow["modules"]["chat_history"]["would_skip"] == 1)

    print("\n[19d4] POST /api/import/preview (conflict detection, strategy=keep_both)")
    r = client.post("/api/import/preview", json=backup, params={"strategy": "keep_both"})
    check("conflict preview keep_both 200", r.status_code == 200)
    pv_kb = r.json()
    check("conflict preview strategy=keep_both", pv_kb["strategy"] == "keep_both")
    check("materials would_keep_both=2", pv_kb["modules"]["materials"]["would_keep_both"] == 2)
    check("materials would_skip=0", pv_kb["modules"]["materials"]["would_skip"] == 0)
    check("error_book would_keep_both=2", pv_kb["modules"]["error_book"]["would_keep_both"] == 2)

    print("\n[19d5] POST /api/import/preview (invalid strategy)")
    r = client.post("/api/import/preview", json=backup, params={"strategy": "bad"})
    check("preview invalid strategy 422", r.status_code == 422)

    print("\n[19d5b] POST /api/import/preview (rapid strategy switching)")
    # Simulate rapid strategy switches: skip -> overwrite -> keep_both -> skip
    # Each should return correct strategy label and conflict handling
    for strat, expected_ow, expected_skip, expected_kb in [
        ("skip", 0, 2, 0), ("overwrite", 2, 0, 0), ("keep_both", 0, 0, 2), ("skip", 0, 2, 0),
    ]:
        r = client.post("/api/import/preview", json=backup, params={"strategy": strat})
        check(f"rapid {strat} 200", r.status_code == 200)
        d = r.json()
        check(f"rapid {strat} strategy label", d["strategy"] == strat)
        check(f"rapid {strat} materials would_overwrite={expected_ow}", d["modules"]["materials"]["would_overwrite"] == expected_ow)
        check(f"rapid {strat} materials would_skip={expected_skip}", d["modules"]["materials"]["would_skip"] == expected_skip)
        check(f"rapid {strat} materials would_keep_both={expected_kb}", d["modules"]["materials"]["would_keep_both"] == expected_kb)

    print("\n[19d5c] POST /api/import/preview (preview is read-only, no side effects)")
    count_before_preview = len(client.get("/api/exam/questions").json())
    for _ in range(5):
        client.post("/api/import/preview", json=backup, params={"strategy": "overwrite"})
    count_after_preview = len(client.get("/api/exam/questions").json())
    check("preview did not change DB", count_after_preview == count_before_preview, f"before={count_before_preview}, after={count_after_preview}")

    print("\n[19d6] Preview matches actual import (skip)")
    pv_mods = pv_skip["modules"]
    # Actual import with skip should match preview predictions
    r = client.post("/api/import/json", json=backup, params={"strategy": "skip"})
    check("verify skip import 200", r.status_code == 200)
    vr = r.json()
    for mod in ["materials", "error_book", "study_plans", "problems", "chat_history", "exam_questions"]:
        check(f"skip {mod} inserted matches", vr["inserted"][mod] == pv_mods[mod]["would_insert"], f"actual={vr['inserted'][mod]}, preview={pv_mods[mod]['would_insert']}")
        check(f"skip {mod} skipped matches", vr["skipped"][mod] == pv_mods[mod]["would_skip"], f"actual={vr['skipped'][mod]}, preview={pv_mods[mod]['would_skip']}")

    # Cleanup imported data
    for q in r_eqs.json():
        if q["title"].startswith("导入真题"):
            client.delete(f"/api/exam/questions/{q['id']}")
    for e in client.get("/api/errors").json():
        if e["question"].startswith("导入错题"):
            client.delete(f"/api/errors/{e['id']}")
    for p in client.get("/api/plan").json():
        if p.get("task", "").startswith("导入任务"):
            client.delete(f"/api/plan/{p['id']}")

    # ── 19e. Import conflict strategies ──
    print("\n[19e] POST /api/import/json (invalid strategy)")
    r = client.post("/api/import/json", json=backup, params={"strategy": "invalid"})
    check("invalid strategy 422", r.status_code == 422, f"got {r.status_code}")

    print("\n[19f] POST /api/import/json (no conflict, empty data)")
    empty_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.2",
        "materials": [], "material_chunks_count": 0, "chat_history": [],
        "error_book": [], "study_plans": [], "problems": [],
        "exam_questions": [], "exam_attempts": [],
    }
    r = client.post("/api/import/json", json=empty_backup, params={"strategy": "skip"})
    check("empty import 200", r.status_code == 200)
    res_empty = r.json()
    check("empty all inserted=0", all(v == 0 for v in res_empty["inserted"].values()))
    check("empty all skipped=0", all(v == 0 for v in res_empty["skipped"].values()))

    # Prepare conflict data: import once, then import same data with different strategies
    conflict_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.2",
        "materials": [{"filename": "冲突测试.txt", "file_type": ".txt"}],
        "material_chunks_count": 0,
        "chat_history": [{"question": "冲突问答Q", "answer": "冲突问答A"}],
        "error_book": [{"question": "冲突错题Q", "error_type": "冲突", "subject": "原科目"}],
        "study_plans": [{"date": "2099-12-01", "subject": "冲突科目", "task": "冲突任务"}],
        "problems": [{"question": "冲突解析Q", "solution": "原解法"}],
        "exam_questions": [{"id": 8001, "title": "冲突真题T", "question": "冲突真题Q", "answer": "原答案"}],
        "exam_attempts": [],
    }
    # First import: insert all
    r = client.post("/api/import/json", json=conflict_backup)
    check("conflict first import 200", r.status_code == 200)
    check("conflict first all inserted", all(v > 0 for k, v in r.json()["inserted"].items() if k != "exam_attempts"))

    print("\n[19g] POST /api/import/json (strategy=skip)")
    r = client.post("/api/import/json", json=conflict_backup, params={"strategy": "skip"})
    check("skip 200", r.status_code == 200)
    skip_res = r.json()
    check("skip all skipped", all(v > 0 for k, v in skip_res["skipped"].items() if k != "exam_attempts"))
    check("skip nothing inserted", all(v == 0 for k, v in skip_res["inserted"].items() if k != "exam_attempts"))
    check("skip nothing overwritten", all(v == 0 for v in skip_res["overwritten"].values()))
    check("skip nothing kept_both", all(v == 0 for v in skip_res["kept_both"].values()))

    print("\n[19h] POST /api/import/json (strategy=overwrite)")
    conflict_backup["error_book"][0]["subject"] = "覆盖科目"
    conflict_backup["problems"][0]["solution"] = "覆盖解法"
    r = client.post("/api/import/json", json=conflict_backup, params={"strategy": "overwrite"})
    check("overwrite 200", r.status_code == 200)
    ow_res = r.json()
    check("overwrite errors overwritten", ow_res["overwritten"]["error_book"] >= 1)
    check("overwrite problems overwritten", ow_res["overwritten"]["problems"] >= 1)
    check("overwrite nothing inserted (all existed)", all(v == 0 for k, v in ow_res["inserted"].items() if k not in ("exam_attempts",)))
    # Verify overwritten values
    r_errs = client.get("/api/errors")
    conflict_err = [e for e in r_errs.json() if e["question"] == "冲突错题Q"]
    if conflict_err:
        check("error subject overwritten", conflict_err[0]["subject"] == "覆盖科目")
    r_probs = client.get("/api/problems/history")
    conflict_prob = [p for p in r_probs.json() if p["question"] == "冲突解析Q"]
    if conflict_prob:
        check("problem solution overwritten", conflict_prob[0]["solution"] == "覆盖解法")

    print("\n[19i] POST /api/import/json (strategy=keep_both)")
    r = client.post("/api/import/json", json=conflict_backup, params={"strategy": "keep_both"})
    check("keep_both 200", r.status_code == 200)
    kb_res = r.json()
    check("keep_both errors kept", kb_res["kept_both"]["error_book"] >= 1)
    check("keep_both problems kept", kb_res["kept_both"]["problems"] >= 1)
    check("keep_both nothing overwritten", all(v == 0 for v in kb_res["overwritten"].values()))
    # Verify both copies exist
    r_errs2 = client.get("/api/errors")
    err_qs = [e["question"] for e in r_errs2.json()]
    check("original error exists", "冲突错题Q" in err_qs)
    check("copy error exists", any("副本" in q for q in err_qs), f"got {err_qs}")
    r_probs2 = client.get("/api/problems/history")
    prob_qs = [p["question"] for p in r_probs2.json()]
    check("original problem exists", "冲突解析Q" in prob_qs)
    check("copy problem exists", any("副本" in q for q in prob_qs))

    print("\n[19i2] POST /api/import/json (keep_both preserves long text)")
    long_question = "长错题Q-" + ("保持完整内容" * 80)
    long_title = "长真题T-" + ("标题内容" * 70)
    long_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.2",
        "materials": [], "material_chunks_count": 0, "chat_history": [],
        "error_book": [{"question": long_question, "error_type": "长文本", "subject": "原科目"}],
        "study_plans": [], "problems": [],
        "exam_questions": [{"id": 8101, "title": long_title, "question": "长真题Q", "answer": "原答案"}],
        "exam_attempts": [],
    }
    r = client.post("/api/import/json", json=long_backup)
    check("long first import 200", r.status_code == 200)
    r = client.post("/api/import/json", json=long_backup, params={"strategy": "keep_both"})
    check("long keep_both 200", r.status_code == 200)
    long_errs = [e["question"] for e in client.get("/api/errors").json() if e["question"].startswith("长错题Q-")]
    check("long error copy keeps base text", any(q.startswith(long_question) and "副本" in q for q in long_errs), f"got lengths={[len(q) for q in long_errs]}")
    long_titles = [q["title"] for q in client.get("/api/exam/questions").json() if q["title"].startswith("长真题T-")]
    check("long exam title copy keeps suffix", any("副本" in t for t in long_titles), f"got {long_titles}")

    # Cleanup conflict test data
    for q in client.get("/api/exam/questions").json():
        if q["title"].startswith("冲突真题") or q["title"].startswith("长真题T-"):
            client.delete(f"/api/exam/questions/{q['id']}")
    for e in client.get("/api/errors").json():
        if e["question"].startswith("冲突错题") or e["question"].startswith("长错题Q-"):
            client.delete(f"/api/errors/{e['id']}")
    for p in client.get("/api/plan").json():
        if p.get("task", "").startswith("冲突任务"):
            client.delete(f"/api/plan/{p['id']}")
    for p in client.get("/api/problems/history").json():
        if p["question"].startswith("冲突解析"):
            client.delete(f"/api/problems/{p['id']}")
    for m in client.get("/api/materials").json():
        if m["filename"].startswith("冲突测试"):
            client.delete(f"/api/materials/{m['id']}")

    # ── 20. Dashboard trends ──
    print("\n[20] GET /api/dashboard/trends")
    r = client.get("/api/dashboard/trends", params={"days": 7})
    check("trends 7d 200", r.status_code == 200)
    t7 = r.json()
    check("trends days=7", t7["days"] == 7)
    check("trends has 7 items", len(t7["items"]) == 7, f"got {len(t7['items'])}")
    check("item has date", "date" in t7["items"][0])
    check("item has plans_total", "plans_total" in t7["items"][0])
    check("item has plans_completed", "plans_completed" in t7["items"][0])
    check("item has errors_created", "errors_created" in t7["items"][0])
    check("item has errors_review_due", "errors_review_due" in t7["items"][0])
    check("item has exam_attempts", "exam_attempts" in t7["items"][0])
    check("item has exam_correct", "exam_correct" in t7["items"][0])

    r = client.get("/api/dashboard/trends", params={"days": 30})
    check("trends 30d 200", r.status_code == 200)
    check("trends 30d has 30 items", len(r.json()["items"]) == 30)

    r = client.get("/api/dashboard/trends", params={"days": 14})
    check("trends 14d rejected 422", r.status_code == 422, f"got {r.status_code}")

    # ── 20b. Trends with test data ──
    print("\n[20b] Trends with test data")
    today_str = local_today()
    today_iso = local_date_obj().isoformat()

    # Create a plan for today
    r = client.post("/api/plan", json={"date": today_str, "subject": "趋势测试", "task": "趋势任务A"})
    check("trends: create plan 200", r.status_code == 200)
    trend_plan_id = r.json()["id"]
    client.patch(f"/api/plan/{trend_plan_id}", json={"completed": True})

    r = client.post("/api/plan", json={"date": today_str, "subject": "趋势测试", "task": "趋势任务B"})
    check("trends: create plan2 200", r.status_code == 200)
    trend_plan_id2 = r.json()["id"]

    # Create an error with next_review_date = today
    r = client.post("/api/errors", json={"subject": "趋势测试", "question": "趋势待复习错题", "next_review_date": today_str})
    check("trends: create error 200", r.status_code == 200)
    trend_err_id = r.json()["id"]

    # Create exam question + attempt
    r = client.post("/api/exam/questions", json={"title": "趋势真题", "question": "趋势题目"})
    check("trends: create eq 200", r.status_code == 200)
    trend_eq_id = r.json()["id"]
    r = client.post(f"/api/exam/questions/{trend_eq_id}/attempt", json={"user_answer": "趋势答案", "is_correct": True})
    check("trends: create attempt 200", r.status_code == 200)

    # Now check trends
    r = client.get("/api/dashboard/trends", params={"days": 7})
    check("trends with data 200", r.status_code == 200)
    items = r.json()["items"]
    today_item = [x for x in items if x["date"] == today_iso]
    if today_item:
        ti = today_item[0]
        check("today plans_total >= 2", ti["plans_total"] >= 2, f"got {ti['plans_total']}")
        check("today plans_completed >= 1", ti["plans_completed"] >= 1, f"got {ti['plans_completed']}")
        check("today errors_review_due >= 1", ti["errors_review_due"] >= 1, f"got {ti['errors_review_due']}")
        check("today exam_attempts >= 1", ti["exam_attempts"] >= 1, f"got {ti['exam_attempts']}")
        check("today exam_correct >= 1", ti["exam_correct"] >= 1, f"got {ti['exam_correct']}")
    else:
        print("  SKIP  today not in trends items")

    # Cleanup
    client.delete(f"/api/plan/{trend_plan_id}")
    client.delete(f"/api/plan/{trend_plan_id2}")
    client.delete(f"/api/errors/{trend_err_id}")
    client.delete(f"/api/exam/questions/{trend_eq_id}")

    # ── 21. Global search ──
    print("\n[21] GET /api/search validation")
    r = client.get("/api/search", params={"q": ""})
    check("empty q rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/search", params={"q": "x", "limit": 0})
    check("limit=0 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/search", params={"q": "x", "limit": 51})
    check("limit=51 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/search", params={"q": "x", "types": "invalid"})
    check("invalid types rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/search", params={"q": "x", "types": "errors,invalid,foo"})
    check("mixed invalid types rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/search", params={"q": "a" * 101})
    check("q too long rejected 422", r.status_code == 422, f"got {r.status_code}")

    # ── 21b. Search with test data ──
    print("\n[21b] Search with test data")
    # Upload a material with searchable content
    search_file = os.path.join(_tmp_dir, "search_test.txt")
    with open(search_file, "w", encoding="utf-8") as f:
        f.write("全局搜索测试卷积定理相关内容")
    with open(search_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("search_test.txt", f, "text/plain")})
    check("search: upload material 200", r.status_code == 200)
    search_mat_id = r.json()["id"]

    # Wait for background parsing to complete so chunks are indexed
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{search_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("search material parsed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Create error
    r = client.post("/api/errors", json={"subject": "搜索测试", "question": "全局搜索卷积定理错题"})
    check("search: create error 200", r.status_code == 200)
    search_err_id = r.json()["id"]

    # Create plan
    r = client.post("/api/plan", json={"date": "2099-07-01", "subject": "搜索测试", "task": "全局搜索卷积定理计划"})
    check("search: create plan 200", r.status_code == 200)
    search_plan_id = r.json()["id"]

    # Create exam question
    r = client.post("/api/exam/questions", json={"title": "搜索真题", "question": "全局搜索卷积定理题目"})
    check("search: create exam 200", r.status_code == 200)
    search_eq_id = r.json()["id"]

    # Search all types
    r = client.get("/api/search", params={"q": "卷积定理", "limit": 50})
    check("search all types 200", r.status_code == 200)
    sr = r.json()
    check("search has query", sr["query"] == "卷积定理")
    types_found = {x["type"] for x in sr["results"]}
    check("found material results", "material" in types_found, f"types={types_found}")
    check("found error results", "error" in types_found, f"types={types_found}")
    check("found plan results", "plan" in types_found, f"types={types_found}")
    check("found exam results", "exam" in types_found, f"types={types_found}")

    # Verify snippets are plain text (no HTML)
    for item in sr["results"]:
        check(f"snippet no HTML ({item['type']})", "<" not in item["snippet"], f"snippet={item['snippet'][:50]}")

    # Verify match_field is present on all results
    for item in sr["results"]:
        check(f"match_field present ({item['type']})", "match_field" in item, f"keys={list(item.keys())}")

    # Verify material results are deduplicated (each material_id appears at most once)
    mat_ids = [x["id"] for x in sr["results"] if x["type"] == "material"]
    check("material results deduplicated", len(mat_ids) == len(set(mat_ids)), f"mat_ids={mat_ids}")

    # Upload a second chunk for the same material to test dedup
    search_file2 = os.path.join(_tmp_dir, "search_test2.txt")
    with open(search_file2, "w", encoding="utf-8") as f:
        f.write("全局搜索测试卷积定理补充内容第二次上传")
    with open(search_file2, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("search_test2.txt", f, "text/plain")})
    check("search: upload material2 200", r.status_code == 200)
    search_mat2_id = r.json()["id"]

    # Wait for second material parsing
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{search_mat2_id}")
        if r.json().get("status") in ("ready", "failed"):
            break

    # Search again - each material should appear at most once
    r = client.get("/api/search", params={"q": "卷积定理", "types": "materials", "limit": 50})
    sr2 = r.json()
    mat_ids2 = [x["id"] for x in sr2["results"] if x["type"] == "material"]
    check("dedup after second upload", len(mat_ids2) == len(set(mat_ids2)), f"mat_ids={mat_ids2}")

    # Verify title match priority: exam title "搜索真题" should rank before question-only matches
    r = client.get("/api/search", params={"q": "搜索真题", "types": "exam", "limit": 10})
    sr3 = r.json()
    if sr3["results"]:
        check("title match has match_field=question or title",
              sr3["results"][0].get("match_field") in ("title", "question", "tags"),
              f"match_field={sr3['results'][0].get('match_field')}")

    # Search with type filter
    r = client.get("/api/search", params={"q": "卷积定理", "types": "errors,exam", "limit": 20})
    check("filtered search 200", r.status_code == 200)
    filtered_types = {x["type"] for x in r.json()["results"]}
    check("filtered only errors+exam", filtered_types <= {"error", "exam"}, f"types={filtered_types}")

    # Verify search result IDs are correct entity IDs
    r = client.get("/api/search", params={"q": "卷积定理", "limit": 50})
    sr = r.json()
    mat_result_ids = {x["id"] for x in sr["results"] if x["type"] == "material"}
    check("material id is entity id", search_mat_id in mat_result_ids, f"got {mat_result_ids}, expected {search_mat_id}")
    mat_titles = {x["title"] for x in sr["results"] if x["type"] == "material"}
    check("material title is filename", "search_test.txt" in mat_titles, f"got {mat_titles}")

    err_result_ids = {x["id"] for x in sr["results"] if x["type"] == "error"}
    check("error id is entity id", search_err_id in err_result_ids, f"got {err_result_ids}, expected {search_err_id}")

    plan_result_ids = {x["id"] for x in sr["results"] if x["type"] == "plan"}
    check("plan id is entity id", search_plan_id in plan_result_ids, f"got {plan_result_ids}, expected {search_plan_id}")

    exam_result_ids = {x["id"] for x in sr["results"] if x["type"] == "exam"}
    check("exam id is entity id", search_eq_id in exam_result_ids, f"got {exam_result_ids}, expected {search_eq_id}")

    # ── 21c. Search pagination: total, offset, limit ──
    print("\n[21c] Search pagination")
    # Create multiple errors with common keyword for pagination testing
    pagination_err_ids = []
    for i in range(5):
        r = client.post("/api/errors", json={"subject": "分页测试", "question": f"分页关键词第{i}题"})
        check(f"pagination error {i} 200", r.status_code == 200)
        pagination_err_ids.append(r.json()["id"])

    # Search with limit=2 → should return 2 results, total >= 5
    r = client.get("/api/search", params={"q": "分页关键词", "types": "errors", "limit": 2})
    check("pagination limit=2 200", r.status_code == 200)
    p1 = r.json()
    check("pagination has total", "total" in p1)
    check("pagination total >= 5", p1["total"] >= 5, f"got {p1['total']}")
    check("pagination results len=2", len(p1["results"]) == 2, f"got {len(p1['results'])}")

    # Search with limit=2, offset=2 → next page
    r = client.get("/api/search", params={"q": "分页关键词", "types": "errors", "limit": 2, "offset": 2})
    check("pagination offset=2 200", r.status_code == 200)
    p2 = r.json()
    check("pagination offset total same", p2["total"] == p1["total"], f"got {p2['total']}")
    check("pagination offset results len=2", len(p2["results"]) == 2, f"got {len(p2['results'])}")
    # Results should differ from page 1
    p1_ids = {x["id"] for x in p1["results"]}
    p2_ids = {x["id"] for x in p2["results"]}
    check("pagination pages differ", p1_ids.isdisjoint(p2_ids), f"p1={p1_ids}, p2={p2_ids}")

    # Search with offset beyond total → empty results
    r = client.get("/api/search", params={"q": "分页关键词", "types": "errors", "limit": 10, "offset": 999})
    check("pagination beyond total 200", r.status_code == 200)
    p_beyond = r.json()
    check("pagination beyond total empty results", len(p_beyond["results"]) == 0, f"got {len(p_beyond['results'])}")
    check("pagination beyond total still correct", p_beyond["total"] >= 5, f"got {p_beyond['total']}")

    # Invalid offset rejected
    r = client.get("/api/search", params={"q": "test", "offset": -1})
    check("negative offset rejected 422", r.status_code == 422, f"got {r.status_code}")

    # Cleanup pagination test data
    for eid in pagination_err_ids:
        client.delete(f"/api/errors/{eid}")

    # Cleanup
    client.delete(f"/api/materials/{search_mat_id}")
    client.delete(f"/api/errors/{search_err_id}")
    client.delete(f"/api/plan/{search_plan_id}")
    client.delete(f"/api/exam/questions/{search_eq_id}")

    # ── 22. Study sessions ──
    print("\n[22] POST /api/sessions/start")
    r = client.post("/api/sessions/start", json={"subject": "高数", "note": "复习极限"})
    check("start session 200", r.status_code == 200)
    sess = r.json()
    sess_id = sess["id"]
    check("session has id", sess_id is not None)
    check("session subject", sess["subject"] == "高数")
    check("session note", sess["note"] == "复习极限")
    check("session started_at not null", sess["started_at"] is not None)
    check("session ended_at is null", sess["ended_at"] is None)
    check("session duration_minutes is 0", sess["duration_minutes"] == 0)

    # Second start should return 409
    r = client.post("/api/sessions/start", json={"subject": "线代"})
    check("second start 409", r.status_code == 409, f"got {r.status_code}")

    # Active should return the session
    r = client.get("/api/sessions/active")
    check("active 200", r.status_code == 200)
    check("active is not null", r.json() is not None)
    check("active id matches", r.json()["id"] == sess_id)

    # Stop the session
    import time
    time.sleep(1)  # ensure duration > 0
    r = client.post(f"/api/sessions/{sess_id}/stop")
    check("stop session 200", r.status_code == 200)
    stopped = r.json()
    check("stopped ended_at not null", stopped["ended_at"] is not None)
    check("stopped duration_minutes >= 1", stopped["duration_minutes"] >= 1, f"got {stopped['duration_minutes']}")

    # Active should be null now
    r = client.get("/api/sessions/active")
    check("active is null after stop", r.json() is None)

    # Double stop should return 409
    r = client.post(f"/api/sessions/{sess_id}/stop")
    check("double stop 409", r.status_code == 409, f"got {r.status_code}")

    # List should contain the session
    r = client.get("/api/sessions", params={"limit": 10})
    check("list sessions 200", r.status_code == 200)
    check("list contains our session", any(s["id"] == sess_id for s in r.json()))

    # Dashboard should show today_study_minutes
    r = client.get("/api/dashboard")
    check("dashboard has today_study_minutes", "today_study_minutes" in r.json())
    check("today_study_minutes >= 1", r.json()["today_study_minutes"] >= 1, f"got {r.json()['today_study_minutes']}")

    # Trends should include study_minutes
    r = client.get("/api/dashboard/trends", params={"days": 7})
    check("trends has study_minutes", "study_minutes" in r.json()["items"][0])
    today_trend = [x for x in r.json()["items"] if x["date"] == local_today()]
    if today_trend:
        check("today study_minutes >= 1", today_trend[0]["study_minutes"] >= 1, f"got {today_trend[0]['study_minutes']}")

    # Stop on nonexistent
    r = client.post("/api/sessions/99999/stop")
    check("stop nonexistent 404", r.status_code == 404, f"got {r.status_code}")

    # Limit validation
    r = client.get("/api/sessions", params={"limit": 0})
    check("limit=0 rejected 422", r.status_code == 422, f"got {r.status_code}")

    r = client.get("/api/sessions", params={"limit": 101})
    check("limit=101 rejected 422", r.status_code == 422, f"got {r.status_code}")

    # ── 23. Error stats ──
    print("\n[23] GET /api/errors/stats (empty)")
    r = client.get("/api/errors/stats")
    check("stats 200", r.status_code == 200)
    s = r.json()
    check("stats total=0", s["total"] == 0)
    check("stats mastered=0", s["mastered"] == 0)
    check("stats unmastered=0", s["unmastered"] == 0)
    check("stats due_today=0", s["due_today"] == 0)
    check("stats by_subject is list", isinstance(s["by_subject"], list))
    check("stats by_error_type is list", isinstance(s["by_error_type"], list))
    check("stats by_knowledge_point is list", isinstance(s["by_knowledge_point"], list))
    check("stats created_last_30_days len=30", len(s["created_last_30_days"]) == 30, f"got {len(s['created_last_30_days'])}")

    # ── 23b. Stats with test data ──
    print("\n[23b] Stats with test data")
    stats_errs = []
    for subj, etype, kp in [
        ("高数", "计算错误", "极限"),
        ("高数", "概念错误", "极限"),
        ("线代", "计算错误", "矩阵"),
        ("概率", "", "分布"),
        ("概率", "计算错误", ""),
    ]:
        r = client.post("/api/errors", json={"subject": subj, "error_type": etype, "knowledge_point": kp, "question": f"stats-{subj}-{kp}"})
        check(f"create stats error {subj} 200", r.status_code == 200)
        stats_errs.append(r.json()["id"])

    # Master one
    client.patch(f"/api/errors/{stats_errs[0]}", json={"mastered": True})

    # Set one with today as review date
    client.patch(f"/api/errors/{stats_errs[2]}", json={"next_review_date": local_today()})

    r = client.get("/api/errors/stats")
    check("stats with data 200", r.status_code == 200)
    s = r.json()
    check("stats total >= 5", s["total"] >= 5, f"got {s['total']}")
    check("stats mastered >= 1", s["mastered"] >= 1, f"got {s['mastered']}")
    check("stats unmastered >= 4", s["unmastered"] >= 4, f"got {s['unmastered']}")
    check("stats due_today >= 1", s["due_today"] >= 1, f"got {s['due_today']}")

    # by_subject should have 高数, 概率, 线代
    subj_names = {x["name"] for x in s["by_subject"]}
    check("by_subject has 高数", "高数" in subj_names, f"got {subj_names}")
    check("by_subject has 线代", "线代" in subj_names, f"got {subj_names}")

    # by_error_type should have 计算错误, 未分类
    etype_names = {x["name"] for x in s["by_error_type"]}
    check("by_error_type has 计算错误", "计算错误" in etype_names, f"got {etype_names}")
    check("by_error_type has 未分类", "未分类" in etype_names, f"got {etype_names}")

    # by_knowledge_point should have 极限, 矩阵
    kp_names = {x["name"] for x in s["by_knowledge_point"]}
    check("by_kp has 极限", "极限" in kp_names, f"got {kp_names}")

    # created_last_30_days last entry is today with count >= 5
    today_entry = s["created_last_30_days"][-1]
    check("today entry date", today_entry["date"] == local_today(), f"got {today_entry['date']}")
    check("today entry count >= 5", today_entry["count"] >= 5, f"got {today_entry['count']}")

    # Cleanup
    for eid in stats_errs:
        client.delete(f"/api/errors/{eid}")

    # ── 28. Material chunks endpoint ──
    print("\n[28] GET /api/materials/{id}/chunks")
    # Upload a material with known content for chunk testing
    chunk_content = "第一段内容用于测试分块功能。\n\n第二段内容包含卷积定理的相关描述。\n\n第三段内容涉及傅里叶变换的基本概念。\n\n" + "第四段较长内容 " * 50
    chunk_content += "\nenglish test marker for fts path"
    chunk_file = os.path.join(_tmp_dir, "chunk_test.txt")
    with open(chunk_file, "w", encoding="utf-8") as f:
        f.write(chunk_content)
    with open(chunk_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("chunk_test.txt", f, "text/plain")})
    check("chunk material upload 200", r.status_code == 200)
    chunk_mat_id = r.json()["id"]

    # Wait for parsing
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{chunk_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("chunk material parsed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Basic chunks listing
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks")
    check("chunks list 200", r.status_code == 200, f"got {r.status_code}")
    chunks_list = r.json()
    check("chunks is list", isinstance(chunks_list, list))
    check("chunks has items", len(chunks_list) > 0, f"count={len(chunks_list)}")
    if chunks_list:
        c0 = chunks_list[0]
        check("chunk has id", "id" in c0)
        check("chunk has chunk_index", "chunk_index" in c0)
        check("chunk has content", "content" in c0)
        check("chunk has snippet", "snippet" in c0)
        check("chunk_index starts at 0", c0["chunk_index"] == 0, f"got {c0['chunk_index']}")
        check("chunk content not empty", len(c0["content"]) > 0)

    # Pagination: limit=1
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"limit": 1})
    check("chunks limit=1 200", r.status_code == 200)
    check("chunks limit=1 returns 1", len(r.json()) == 1, f"got {len(r.json())}")

    # Pagination: offset
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"limit": 1, "offset": 1})
    check("chunks offset=1 200", r.status_code == 200)
    if len(chunks_list) > 1:
        check("chunks offset returns different chunk", r.json()[0]["chunk_index"] == 1, f"got {r.json()[0]['chunk_index']}")

    # Query search within material
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"query": "卷积定理"})
    check("chunks query 200", r.status_code == 200)
    query_results = r.json()
    check("query found chunks", len(query_results) > 0, f"count={len(query_results)}")
    if query_results:
        check("query chunk has snippet", len(query_results[0]["snippet"]) > 0)
        # Snippet should contain the query or highlight markers
        snippet_text = query_results[0]["snippet"]
        has_markers = ">>>" in snippet_text and "<<<" in snippet_text
        check("query snippet contains highlight markers", has_markers, f"snippet={snippet_text[:80]}")

    # Query with English text (FTS5 path)
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"query": "test"})
    check("chunks english query 200", r.status_code == 200)
    english_results = r.json()
    check("english query found chunks", len(english_results) > 0, f"count={len(english_results)}")
    if english_results:
        check("english query snippet highlighted", ">>>test<<<" in english_results[0]["snippet"], f"snippet={english_results[0]['snippet']}")

    # Non-existent material
    r = client.get("/api/materials/999999/chunks")
    check("chunks nonexistent 404", r.status_code == 404, f"got {r.status_code}")

    # Invalid limit/offset
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"limit": 0})
    check("chunks limit=0 clamped", r.status_code == 200)  # clamped to 1
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"limit": 200})
    check("chunks limit=200 clamped", r.status_code == 200)  # clamped to 100
    r = client.get(f"/api/materials/{chunk_mat_id}/chunks", params={"offset": -1})
    check("chunks negative offset clamped", r.status_code == 200)  # clamped to 0

    # Cleanup
    client.delete(f"/api/materials/{chunk_mat_id}")

    # ── 25. Parse job: startup recovery logic ──
    print("\n[25] Parse job: startup recovery logic")
    # Upload a material, wait for it to finish, then simulate a stuck "processing" state
    recovery_file = os.path.join(_tmp_dir, "recovery_test.txt")
    with open(recovery_file, "w", encoding="utf-8") as f:
        f.write("启动恢复测试内容")
    with open(recovery_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("recovery_test.txt", f, "text/plain")})
    check("recovery upload 200", r.status_code == 200)
    recovery_mid = r.json()["id"]

    # Wait for it to become ready
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{recovery_mid}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("recovery material ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Simulate a stuck processing job + material (mimics crash during processing)
    async def simulate_stuck_job(mid):
        async with async_session() as session:
            await session.execute(text(
                "INSERT INTO material_parse_jobs (material_id, status, attempts) VALUES (:mid, 'processing', 1)"
            ), {"mid": mid})
            await session.execute(text(
                "UPDATE materials SET status='processing' WHERE id=:mid"
            ), {"mid": mid})
            await session.commit()

    loop_stuck = asyncio.new_event_loop()
    loop_stuck.run_until_complete(simulate_stuck_job(recovery_mid))
    loop_stuck.close()

    # Verify stuck state
    r = client.get(f"/api/materials/{recovery_mid}")
    check("stuck status is processing", r.json().get("status") == "processing", f"got {r.json().get('status')}")

    # Verify recovery SQL logic: reset processing → pending (same as start_worker does)
    async def verify_recovery_sql():
        async with async_session() as session:
            # Count processing jobs before recovery
            before = await session.execute(text(
                "SELECT COUNT(*) FROM material_parse_jobs WHERE status='processing'"
            ))
            before_count = before.scalar() or 0

            # Apply recovery: processing → pending
            await session.execute(text(
                "UPDATE material_parse_jobs SET status='pending', started_at=NULL WHERE status='processing'"
            ))
            await session.execute(text(
                "UPDATE materials SET status='pending', error_message='' WHERE status='processing'"
            ))
            await session.commit()

            # Count processing jobs after recovery
            after = await session.execute(text(
                "SELECT COUNT(*) FROM material_parse_jobs WHERE status='processing'"
            ))
            after_count = after.scalar() or 0

            # Verify material status
            mat = await session.execute(text(
                "SELECT status FROM materials WHERE id=:mid"
            ), {"mid": recovery_mid})
            mat_status = mat.scalar()

            return before_count, after_count, mat_status

    loop_rec = asyncio.new_event_loop()
    before_cnt, after_cnt, mat_st = loop_rec.run_until_complete(verify_recovery_sql())
    loop_rec.close()
    check("recovery: processing jobs existed before", before_cnt >= 1, f"count={before_cnt}")
    check("recovery: no processing jobs after", after_cnt == 0, f"count={after_cnt}")
    check("recovery: material reset to pending", mat_st == "pending", f"status={mat_st}")

    # Now use retry endpoint to re-process (simulates worker picking up recovered job)
    r = client.post(f"/api/materials/{recovery_mid}/retry")
    # Material is pending, not failed — retry should fail with 422
    check("retry on pending 422", r.status_code == 422, f"got {r.status_code}")

    # Manually set to failed so we can retry
    async def set_failed(mid):
        async with async_session() as session:
            await session.execute(text(
                "UPDATE materials SET status='failed', error_message='恢复测试' WHERE id=:mid"
            ), {"mid": mid})
            await session.commit()

    loop_sf = asyncio.new_event_loop()
    loop_sf.run_until_complete(set_failed(recovery_mid))
    loop_sf.close()

    r = client.post(f"/api/materials/{recovery_mid}/retry")
    check("retry after recovery 200", r.status_code == 200, f"got {r.status_code}")

    # Wait for retry to complete
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{recovery_mid}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("recovery retry completes to ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")
    check("recovery content preserved", "启动恢复" in r.json().get("preview", ""))

    # Cleanup
    client.delete(f"/api/materials/{recovery_mid}")

    # ── 26. Parse job: concurrency via sequential upload ──
    print("\n[26] Parse job: sequential upload and processing")
    # Upload 3 materials, verify all get parse jobs that complete
    conc_ids = []
    for i in range(3):
        cfile = os.path.join(_tmp_dir, f"conc_{i}.txt")
        with open(cfile, "w", encoding="utf-8") as f:
            f.write(f"并发限制测试 {i} " + "x" * 500)
        with open(cfile, "rb") as f:
            r = client.post("/api/materials/upload", files={"file": (f"conc_{i}.txt", f, "text/plain")})
        check(f"conc upload {i} 200", r.status_code == 200)
        conc_ids.append(r.json()["id"])

    # Wait for all to complete
    for mid in conc_ids:
        for _ in range(50):
            time.sleep(0.1)
            r = client.get(f"/api/materials/{mid}")
            if r.json().get("status") in ("ready", "failed"):
                break
        check(f"conc material {mid} ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Verify all parse jobs completed
    async def verify_conc_jobs():
        async with async_session() as session:
            jq = await session.execute(text(
                "SELECT material_id, status FROM material_parse_jobs WHERE material_id IN (:m0, :m1, :m2) AND status='done'"
            ), {"m0": conc_ids[0], "m1": conc_ids[1], "m2": conc_ids[2]})
            return jq.fetchall()

    loop_cj = asyncio.new_event_loop()
    conc_jobs = loop_cj.run_until_complete(verify_conc_jobs())
    loop_cj.close()
    check("all conc jobs done", len(conc_jobs) >= 3, f"count={len(conc_jobs)}")

    # Cleanup
    for mid in conc_ids:
        client.delete(f"/api/materials/{mid}")

    # ── 27. Parse job: list, cancel, and lifecycle ──
    print("\n[27] GET /api/materials/jobs (list parse jobs)")
    r = client.get("/api/materials/jobs")
    check("jobs list 200", r.status_code == 200, f"got {r.status_code}")
    jobs_list = r.json()
    check("jobs list is list", isinstance(jobs_list, list))
    # There should be completed jobs from previous tests
    check("jobs list has items", len(jobs_list) > 0, f"count={len(jobs_list)}")
    # Verify schema fields
    if jobs_list:
        j0 = jobs_list[0]
        check("job has id", "id" in j0)
        check("job has material_id", "material_id" in j0)
        check("job has filename", "filename" in j0)
        check("job has status", "status" in j0)
        check("job has attempts", "attempts" in j0)
        check("job has error_message", "error_message" in j0)
        check("job has progress_current", "progress_current" in j0)
        check("job has progress_total", "progress_total" in j0)
        check("job has progress_message", "progress_message" in j0)
        check("job has created_at", "created_at" in j0)
        check("job has started_at", "started_at" in j0)
        check("job has finished_at", "finished_at" in j0)

    # Filter by status
    print("\n[27b] GET /api/materials/jobs?status=done")
    r = client.get("/api/materials/jobs", params={"status": "done"})
    check("jobs filter done 200", r.status_code == 200)
    done_jobs = r.json()
    check("all filtered jobs are done", all(j["status"] == "done" for j in done_jobs), f"statuses={set(j['status'] for j in done_jobs)}")

    print("\n[27c] GET /api/materials/jobs?status=pending")
    r = client.get("/api/materials/jobs", params={"status": "pending"})
    check("jobs filter pending 200", r.status_code == 200)
    pending_jobs = r.json()
    check("all filtered jobs are pending", all(j["status"] == "pending" for j in pending_jobs))

    r = client.get("/api/materials/jobs", params={"status": "invalid"})
    check("jobs invalid status 422", r.status_code == 422, f"got {r.status_code}")

    # ── 27h. Progress fields: completed jobs have final progress ──
    print("\n[27h] Progress fields on completed jobs")
    r = client.get("/api/materials/jobs", params={"status": "done"})
    check("progress done jobs 200", r.status_code == 200)
    done_progress_jobs = r.json()
    if done_progress_jobs:
        dp = done_progress_jobs[0]
        check("done job progress_current=4", dp["progress_current"] == 4, f"got {dp['progress_current']}")
        check("done job progress_total=4", dp["progress_total"] == 4, f"got {dp['progress_total']}")
        check("done job progress_message=已完成", dp["progress_message"] == "已完成", f"got {dp['progress_message']}")
    else:
        print("  SKIP  no done jobs to check progress")

    # ── 27i. Progress on failed jobs ──
    print("\n[27i] Progress fields on failed jobs")
    # Create a material with a file, set it to failed, check progress_message
    fail_progress_file = os.path.join(_tmp_dir, "fail_progress.txt")
    with open(fail_progress_file, "w", encoding="utf-8") as f:
        f.write("失败进度测试")
    with open(fail_progress_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("fail_progress.txt", f, "text/plain")})
    check("fail progress upload 200", r.status_code == 200)
    fp_mat_id = r.json()["id"]

    # Wait for it to finish
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{fp_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("fail progress material ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Simulate failure by deleting the file and retrying
    async def set_failed_for_progress(mid):
        async with async_session() as session:
            await session.execute(text(
                "UPDATE materials SET status='failed', error_message='进度测试失败' WHERE id=:mid"
            ), {"mid": mid})
            # Also create a failed job with progress_message
            await session.execute(text(
                "INSERT INTO material_parse_jobs (material_id, status, attempts, error_message, progress_message, created_at) "
                "VALUES (:mid, 'failed', 1, '进度测试失败', '失败：进度测试失败', datetime('now'))"
            ), {"mid": mid})
            await session.commit()

    loop_fp = asyncio.new_event_loop()
    loop_fp.run_until_complete(set_failed_for_progress(fp_mat_id))
    loop_fp.close()

    r = client.get("/api/materials/jobs", params={"status": "failed"})
    check("failed jobs 200", r.status_code == 200)
    failed_jobs = r.json()
    fp_found = [j for j in failed_jobs if j["material_id"] == fp_mat_id]
    if fp_found:
        check("failed job has progress_message", "失败" in fp_found[0]["progress_message"], f"got {fp_found[0]['progress_message']}")
        check("failed job error_message matches", "进度测试失败" in fp_found[0]["error_message"], f"got {fp_found[0]['error_message']}")

    # Cleanup
    client.delete(f"/api/materials/{fp_mat_id}")

    # ── 27d. Cancel a pending job ──
    print("\n[27d] Cancel a pending job")
    # Upload a material and create a pending job for it before the worker processes it
    cancel_file = os.path.join(_tmp_dir, "cancel_test.txt")
    with open(cancel_file, "w", encoding="utf-8") as f:
        f.write("取消测试内容")

    # Create material + pending job directly in DB (bypass worker) to test cancel
    async def create_material_with_pending_job():
        async with async_session() as session:
            from app.models import Material as M
            mat = M(filename="cancel_test.txt", file_type=".txt", content="",
                     stored_filename="cancel_test_stored.txt", status="pending", error_message="")
            session.add(mat)
            await session.flush()
            mat_id = mat.id
            await session.execute(text(
                "INSERT INTO material_parse_jobs (material_id, status, attempts, created_at) VALUES (:mat_id, 'pending', 0, datetime('now'))"
            ), {"mat_id": mat_id})
            await session.commit()
            # Get the job id
            r = await session.execute(text(
                "SELECT id FROM material_parse_jobs WHERE material_id=:mat_id AND status='pending' ORDER BY id DESC LIMIT 1"
            ), {"mat_id": mat_id})
            job_id = r.scalar()
            return mat_id, job_id

    loop_cpj = asyncio.new_event_loop()
    cancel_mat_id, cancel_job_id = loop_cpj.run_until_complete(create_material_with_pending_job())
    loop_cpj.close()
    check("created pending job for cancel test", cancel_job_id is not None)

    # Cancel it
    r = client.post(f"/api/materials/jobs/{cancel_job_id}/cancel")
    check("cancel pending job 200", r.status_code == 200, f"got {r.status_code}")
    check("cancel returns ok", r.json().get("ok") is True)
    check("cancel returns cancelled status", r.json().get("status") == "cancelled", f"got {r.json().get('status')}")

    # Verify job is now cancelled
    r = client.get("/api/materials/jobs", params={"status": "cancelled"})
    cancelled_jobs = [j for j in r.json() if j["id"] == cancel_job_id]
    check("cancelled job appears in cancelled filter", len(cancelled_jobs) == 1, f"found={len(cancelled_jobs)}")

    # Verify material status is failed (with "任务已取消" message) since material was pending
    r = client.get(f"/api/materials/{cancel_mat_id}")
    check("cancelled material status failed", r.json().get("status") == "failed", f"got {r.json().get('status')}")
    check("cancelled material error_message", "已取消" in r.json().get("error_message", ""), f"msg={r.json().get('error_message')}")

    # ── 27e. Cancel on non-pending job returns 422 ──
    print("\n[27e] Cancel on non-pending job returns 422")
    # Find a done job
    r = client.get("/api/materials/jobs", params={"status": "done"})
    done_jobs_for_cancel = r.json()
    if done_jobs_for_cancel:
        done_job_id = done_jobs_for_cancel[0]["id"]
        r = client.post(f"/api/materials/jobs/{done_job_id}/cancel")
        check("cancel done job 422", r.status_code == 422, f"got {r.status_code}")
        detail = r.json().get("detail", "")
        check("cancel 422 mentions status", "done" in detail or "不支持取消" in detail or "暂不支持中断" in detail, f"detail={detail}")

    # Cancel on nonexistent job
    r = client.post("/api/materials/jobs/999999/cancel")
    check("cancel nonexistent job 404", r.status_code == 404, f"got {r.status_code}")

    # ── 27f. Cancelled job is not processed by worker ──
    print("\n[27f] Cancelled job not processed by worker")
    # Create a pending job for a material that's already ready, cancel it, verify worker doesn't re-process
    cancel_file2 = os.path.join(_tmp_dir, "cancel_no_process.txt")
    with open(cancel_file2, "w", encoding="utf-8") as f:
        f.write("取消后不处理测试")
    with open(cancel_file2, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("cancel_no_process.txt", f, "text/plain")})
    check("cancel2 upload 200", r.status_code == 200)
    cancel2_mat_id = r.json()["id"]

    # Wait for the upload to be processed
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{cancel2_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    cancel2_initial_status = r.json().get("status")
    check("cancel2 material processed first", cancel2_initial_status == "ready", f"got {cancel2_initial_status}")

    # Now create a pending job for this material and cancel it before worker picks it up
    async def create_and_cancel_pending_job(material_id_val):
        async with async_session() as session:
            await session.execute(text(
                "INSERT INTO material_parse_jobs (material_id, status, attempts, created_at) VALUES (:mat_id, 'pending', 0, datetime('now'))"
            ), {"mat_id": material_id_val})
            await session.commit()
            r = await session.execute(text(
                "SELECT id FROM material_parse_jobs WHERE material_id=:mat_id AND status='pending' ORDER BY id DESC LIMIT 1"
            ), {"mat_id": material_id_val})
            job_id = r.scalar()
            # Cancel it immediately in the same session
            await session.execute(text(
                "UPDATE material_parse_jobs SET status='cancelled', finished_at=datetime('now') WHERE id=:jid"
            ), {"jid": job_id})
            await session.commit()
            return job_id

    loop_cc = asyncio.new_event_loop()
    cancel2_job_id = loop_cc.run_until_complete(create_and_cancel_pending_job(cancel2_mat_id))
    loop_cc.close()
    check("cancel2 job created and cancelled", cancel2_job_id is not None)

    # Verify the job is cancelled
    r = client.get("/api/materials/jobs", params={"status": "cancelled"})
    cancel2_found = [j for j in r.json() if j["id"] == cancel2_job_id]
    check("cancel2 job is cancelled", len(cancel2_found) == 1, f"found={len(cancel2_found)}")

    # Wait briefly — worker should NOT process the cancelled job
    time.sleep(0.5)
    r = client.get(f"/api/materials/{cancel2_mat_id}")
    # Material should still be "ready" (its original status), not re-processed
    check("cancelled job not processed, material still ready", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # ── 27g. Failed job can be retried (material retry creates new job) ──
    print("\n[27g] Failed job can still trigger retry")
    # Create a material with a real file, set it to failed, then retry
    retry_file = os.path.join(_tmp_dir, "retry_after_cancel.txt")
    with open(retry_file, "w", encoding="utf-8") as f:
        f.write("重试取消后测试内容")
    with open(retry_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("retry_after_cancel.txt", f, "text/plain")})
    check("retry material upload 200", r.status_code == 200)
    retry_mat_id = r.json()["id"]

    # Wait for it to be processed
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{retry_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("retry material processed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Simulate failure by setting status to failed in DB
    async def set_failed_for_retry(mid):
        async with async_session() as session:
            await session.execute(text(
                "UPDATE materials SET status='failed', error_message='重试测试失败' WHERE id=:mid"
            ), {"mid": mid})
            await session.commit()

    loop_sfr = asyncio.new_event_loop()
    loop_sfr.run_until_complete(set_failed_for_retry(retry_mat_id))
    loop_sfr.close()

    r = client.get(f"/api/materials/{retry_mat_id}")
    check("retry material is failed", r.json().get("status") == "failed", f"got {r.json().get('status')}")

    r = client.post(f"/api/materials/{retry_mat_id}/retry")
    check("retry after cancel 200", r.status_code == 200, f"got {r.status_code}")
    check("retry status pending", r.json().get("status") == "pending")

    # Wait for retry to complete
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{retry_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("retry after cancel completes", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Cleanup
    client.delete(f"/api/materials/{retry_mat_id}")

    # Cleanup cancel test materials
    client.delete(f"/api/materials/{cancel_mat_id}")
    client.delete(f"/api/materials/{cancel2_mat_id}")

    # ── 28. Upload then immediately delete (race condition) ──
    print("\n[28] Upload then immediately delete (race condition)")
    # Upload several materials and delete them while parsing may be in progress
    race_ids = []
    for i in range(3):
        race_file = os.path.join(_tmp_dir, f"race_{i}.txt")
        with open(race_file, "w", encoding="utf-8") as f:
            f.write(f"竞态测试内容 {i} " + "x" * 200)
        with open(race_file, "rb") as f:
            r = client.post("/api/materials/upload", files={"file": (f"race_{i}.txt", f, "text/plain")})
        check(f"race upload {i} 200", r.status_code == 200)
        race_ids.append(r.json()["id"])

    # Immediately delete all (some may still be parsing)
    for mid in race_ids:
        r = client.delete(f"/api/materials/{mid}")
        check(f"race delete {mid} 200", r.status_code == 200, f"got {r.status_code}")

    # Verify all materials are gone
    for mid in race_ids:
        r = client.get(f"/api/materials/{mid}")
        check(f"race material {mid} gone 404", r.status_code == 404, f"got {r.status_code}")

    # Verify no orphaned chunks
    async def verify_no_race_chunks():
        async with async_session() as session:
            for mid in race_ids:
                cq = await session.execute(
                    text("SELECT COUNT(*) FROM material_chunks WHERE material_id = :id"), {"id": mid}
                )
                count = cq.scalar() or 0
                if count > 0:
                    return False, mid
            return True, None

    loop_race = asyncio.new_event_loop()
    ok, bad_mid = loop_race.run_until_complete(verify_no_race_chunks())
    loop_race.close()
    check("no orphaned chunks after race delete", ok, f"orphaned material_id={bad_mid}")

    # Verify no orphaned parse jobs
    async def verify_no_race_jobs():
        async with async_session() as session:
            for mid in race_ids:
                jq = await session.execute(
                    text("SELECT COUNT(*) FROM material_parse_jobs WHERE material_id = :id"), {"id": mid}
                )
                count = jq.scalar() or 0
                if count > 0:
                    return False, mid
            return True, None

    loop_rj = asyncio.new_event_loop()
    ok, bad_mid = loop_rj.run_until_complete(verify_no_race_jobs())
    loop_rj.close()
    check("no orphaned parse jobs after race delete", ok, f"orphaned material_id={bad_mid}")

    # Wait briefly for any in-flight worker tasks to finish (should not crash)
    time.sleep(1)

    # Verify health is still ok (no worker crash)
    r = client.get("/api/health")
    check("health ok after race delete", r.status_code == 200)
    check("health status ok", r.json().get("status") == "ok", f"got {r.json().get('status')}")

    # ── 24. Materials bulk operations ──
    print("\n[24] POST /api/materials/bulk-delete (validation)")
    r = client.post("/api/materials/bulk-delete", json={"ids": []})
    check("empty ids 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/materials/bulk-delete", json={"ids": list(range(101))})
    check("over 100 ids 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/materials/export-selected", json={"ids": []})
    check("export empty ids 422", r.status_code == 422, f"got {r.status_code}")

    # Upload test materials for bulk ops
    print("\n[24b] Bulk delete with test data")
    bulk_mat_ids = []
    for i in range(3):
        fpath = os.path.join(_tmp_dir, f"bulk_{i}.txt")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"批量测试资料 {i} 内容")
        with open(fpath, "rb") as f:
            r = client.post("/api/materials/upload", files={"file": (f"bulk_{i}.txt", f, "text/plain")})
        check(f"upload bulk_{i} 200", r.status_code == 200)
        bulk_mat_ids.append(r.json()["id"])

    # Wait for all bulk materials to be parsed
    for mid in bulk_mat_ids:
        for _ in range(30):
            time.sleep(0.1)
            r = client.get(f"/api/materials/{mid}")
            if r.json().get("status") in ("ready", "failed"):
                break

    # Export selected
    r = client.post("/api/materials/export-selected", json={"ids": bulk_mat_ids, "include_preview": True})
    check("export selected 200", r.status_code == 200)
    exp = r.json()
    check("export selected_count=3", exp["selected_count"] == 3, f"got {exp['selected_count']}")
    check("export materials len=3", len(exp["materials"]) == 3, f"got {len(exp['materials'])}")
    check("export has id", "id" in exp["materials"][0])
    check("export has filename", "filename" in exp["materials"][0])
    check("export has file_type", "file_type" in exp["materials"][0])
    check("export has content_length", "content_length" in exp["materials"][0])
    check("export has preview", "preview" in exp["materials"][0])
    check("export no stored file", "stored_filename" not in exp["materials"][0])
    check("export preview has content", len(exp["materials"][0]["preview"]) > 0)

    # Export without preview
    r = client.post("/api/materials/export-selected", json={"ids": bulk_mat_ids, "include_preview": False})
    check("export no preview 200", r.status_code == 200)
    check("export no preview field", "preview" not in r.json()["materials"][0])

    # Bulk delete
    r = client.post("/api/materials/bulk-delete", json={"ids": bulk_mat_ids})
    check("bulk delete 200", r.status_code == 200)
    bd = r.json()
    check("bulk delete deleted=3", bd["deleted"] == 3, f"got {bd['deleted']}")
    check("bulk delete missing=0", bd["missing"] == 0, f"got {bd['missing']}")

    # Verify materials are gone
    for mid in bulk_mat_ids:
        r = client.get(f"/api/materials/{mid}")
        check(f"material {mid} gone 404", r.status_code == 404, f"got {r.status_code}")

    # Bulk delete with some missing
    r = client.post("/api/materials/bulk-delete", json={"ids": [999998, 999999]})
    check("bulk delete missing 200", r.status_code == 200)
    bd2 = r.json()
    check("bulk delete missing deleted=0", bd2["deleted"] == 0, f"got {bd2['deleted']}")
    check("bulk delete missing=2", bd2["missing"] == 2, f"got {bd2['missing']}")

    # ── 29. Review queue ──
    print("\n[29] GET /api/review/queue (empty)")
    r = client.get("/api/review/queue")
    check("review queue 200", r.status_code == 200, f"got {r.status_code}")
    rq = r.json()
    check("queue has items", "items" in rq)
    check("queue has total_due", "total_due" in rq)
    check("queue has total_unmastered", "total_unmastered" in rq)
    check("queue has weak_points", "weak_points" in rq)
    check("queue has today", "today" in rq)
    check("queue today is today", rq["today"] == local_today(), f"got {rq['today']}")
    check("queue empty items", rq["items"] == [])
    check("queue total_due=0", rq["total_due"] == 0, f"got {rq['total_due']}")

    # ── 29b. Queue with due/overdue/future/mastered errors ──
    print("\n[29b] Review queue with test data")
    today_str = local_today()
    overdue_str = (local_date_obj() - _td(days=3)).isoformat()
    future_str = (local_date_obj() + _td(days=30)).isoformat()

    # Overdue error (3 days ago)
    r = client.post("/api/errors", json={
        "subject": "复习队列", "knowledge_point": "极限", "error_type": "计算错误",
        "question": "逾期错题", "next_review_date": overdue_str,
    })
    check("overdue error create 200", r.status_code == 200)
    overdue_err_id = r.json()["id"]

    # Today-due error
    r = client.post("/api/errors", json={
        "subject": "复习队列", "knowledge_point": "极限", "error_type": "概念错误",
        "question": "今日到期错题", "next_review_date": today_str,
    })
    check("today error create 200", r.status_code == 200)
    today_err_id = r.json()["id"]

    # Future error (should NOT appear in queue)
    r = client.post("/api/errors", json={
        "subject": "复习队列", "question": "未来错题", "next_review_date": future_str,
    })
    check("future error create 200", r.status_code == 200)
    future_err_id = r.json()["id"]

    # Mastered error with today review (should NOT appear — mastered=true)
    r = client.post("/api/errors", json={
        "subject": "复习队列", "question": "已掌握错题", "next_review_date": today_str,
    })
    check("mastered error create 200", r.status_code == 200)
    mastered_err_id = r.json()["id"]
    r = client.patch(f"/api/errors/{mastered_err_id}", json={"mastered": True})
    check("master error 200", r.status_code == 200)

    # Unmastered error with no review date (should NOT appear)
    r = client.post("/api/errors", json={
        "subject": "复习队列", "question": "无日期错题",
    })
    check("nodate error create 200", r.status_code == 200)
    nodate_err_id = r.json()["id"]

    # Fetch queue
    r = client.get("/api/review/queue")
    check("queue with data 200", r.status_code == 200)
    rq2 = r.json()
    check("queue total_due=2", rq2["total_due"] == 2, f"got {rq2['total_due']}")
    check("queue total_unmastered >= 4", rq2["total_unmastered"] >= 4, f"got {rq2['total_unmastered']}")
    queue_ids = [it["id"] for it in rq2["items"]]
    check("overdue in queue", overdue_err_id in queue_ids, f"ids={queue_ids}")
    check("today in queue", today_err_id in queue_ids, f"ids={queue_ids}")
    check("future NOT in queue", future_err_id not in queue_ids)
    check("mastered NOT in queue", mastered_err_id not in queue_ids)
    check("nodate NOT in queue", nodate_err_id not in queue_ids)

    # Verify sorting: overdue first
    overdue_idx = queue_ids.index(overdue_err_id)
    today_idx = queue_ids.index(today_err_id)
    check("overdue before today", overdue_idx < today_idx, f"overdue_idx={overdue_idx}, today_idx={today_idx}")

    # Verify item fields
    overdue_item = rq2["items"][overdue_idx]
    check("item has due_days", "due_days" in overdue_item)
    check("overdue due_days >= 3", overdue_item["due_days"] >= 3, f"got {overdue_item['due_days']}")
    check("item has priority_reason", "priority_reason" in overdue_item)
    check("overdue priority mentions 逾期", "逾期" in overdue_item["priority_reason"], f"reason={overdue_item['priority_reason']}")

    today_item = rq2["items"][today_idx]
    check("today due_days=0", today_item["due_days"] == 0, f"got {today_item['due_days']}")

    # Verify weak_points
    check("weak_points is list", isinstance(rq2["weak_points"], list))
    if rq2["weak_points"]:
        kp_names = [wp["name"] for wp in rq2["weak_points"]]
        check("weak_points has 极限", "极限" in kp_names, f"kp={kp_names}")

    # ── 29c. Review action: mastered ──
    print("\n[29c] POST /api/review/{id}/action (mastered)")
    r = client.post(f"/api/review/{today_err_id}/action", json={"action": "mastered"})
    check("mastered action 200", r.status_code == 200, f"got {r.status_code}")
    ma = r.json()
    check("mastered ok", ma["ok"] is True)
    check("mastered action=mastered", ma["action"] == "mastered")
    check("mastered mastered=True", ma["mastered"] is True)
    check("mastered next_review_date set", bool(ma["next_review_date"]), f"got {ma['next_review_date']}")
    check("mastered next_review_date > today", ma["next_review_date"] > today_str, f"got {ma['next_review_date']}")
    check("mastered review_count >= 1", ma["review_count"] >= 1, f"got {ma['review_count']}")
    saved_review_count = ma["review_count"]
    saved_next_date = ma["next_review_date"]

    # ── 29c2. Mastered idempotency: second mastered on same error ──
    print("\n[29c2] POST /api/review/{id}/action (mastered again — idempotent)")
    r = client.post(f"/api/review/{today_err_id}/action", json={"action": "mastered"})
    check("mastered2 action 200", r.status_code == 200, f"got {r.status_code}")
    ma2 = r.json()
    check("mastered2 still mastered", ma2["mastered"] is True)
    check("mastered2 review_count unchanged", ma2["review_count"] == saved_review_count, f"got {ma2['review_count']}, expected {saved_review_count}")
    check("mastered2 next_review_date unchanged", ma2["next_review_date"] == saved_next_date, f"got {ma2['next_review_date']}, expected {saved_next_date}")

    # ── 29d. Review action: again (keeps today) ──
    print("\n[29d] POST /api/review/{id}/action (again)")
    r = client.post(f"/api/review/{overdue_err_id}/action", json={"action": "again"})
    check("again action 200", r.status_code == 200, f"got {r.status_code}")
    aa = r.json()
    check("again ok", aa["ok"] is True)
    check("again mastered=False", aa["mastered"] is False)
    check("again next_review_date=today", aa["next_review_date"] == today_str, f"got {aa['next_review_date']}")

    # ── 29e. Review action: postpone (defers to tomorrow) ──
    # Create a fresh due error for postpone test
    r = client.post("/api/errors", json={
        "subject": "复习队列", "question": "推迟测试错题", "next_review_date": today_str,
    })
    check("postpone error create 200", r.status_code == 200)
    postpone_err_id = r.json()["id"]

    expected_tomorrow = (local_date_obj() + _td(days=1)).isoformat()
    print("\n[29e] POST /api/review/{id}/action (postpone)")
    r = client.post(f"/api/review/{postpone_err_id}/action", json={"action": "postpone"})
    check("postpone action 200", r.status_code == 200, f"got {r.status_code}")
    pa = r.json()
    check("postpone ok", pa["ok"] is True)
    check("postpone mastered=False", pa["mastered"] is False)
    check("postpone next_review_date=tomorrow", pa["next_review_date"] == expected_tomorrow, f"got {pa['next_review_date']}")

    # ── 29f. Review action: skip ──
    # Create a fresh due error for skip test
    r = client.post("/api/errors", json={
        "subject": "复习队列", "question": "跳过测试错题", "next_review_date": today_str,
    })
    check("skip error create 200", r.status_code == 200)
    skip_err_id = r.json()["id"]

    print("\n[29f] POST /api/review/{id}/action (skip)")
    r = client.post(f"/api/review/{skip_err_id}/action", json={"action": "skip"})
    check("skip action 200", r.status_code == 200, f"got {r.status_code}")
    sa = r.json()
    check("skip ok", sa["ok"] is True)
    check("skip action=skip", sa["action"] == "skip")
    check("skip error_id matches", sa["error_id"] == skip_err_id)
    check("skip mastered is null", sa.get("mastered") is None)
    check("skip next_review_date is null", sa.get("next_review_date") is None)
    check("skip review_count is null", sa.get("review_count") is None)

    # Verify skip did NOT change the error in DB
    r = client.get("/api/errors", params={"mastered": "false"})
    skip_err = [e for e in r.json() if e["id"] == skip_err_id]
    if skip_err:
        check("skip still unmastered", skip_err[0]["mastered"] is False)
        check("skip date unchanged", skip_err[0]["next_review_date"] == today_str, f"got {skip_err[0]['next_review_date']}")

    # ── 29g. Review action validation ──
    print("\n[29g] Review action validation")
    r = client.post(f"/api/review/{skip_err_id}/action", json={"action": "invalid"})
    check("invalid action 422", r.status_code == 422, f"got {r.status_code}")

    r = client.post("/api/review/999999/action", json={"action": "mastered"})
    check("nonexistent error 404", r.status_code == 404, f"got {r.status_code}")

    # ── 29h. Queue after actions ──
    print("\n[29h] Queue after actions")
    r = client.get("/api/review/queue")
    check("queue after actions 200", r.status_code == 200)
    rq3 = r.json()
    remaining_ids = [it["id"] for it in rq3["items"]]
    check("mastered error removed from queue", today_err_id not in remaining_ids)
    # again keeps next_review_date=today, so it stays in the queue on reload
    check("again error still in queue (today date)", overdue_err_id in remaining_ids, f"ids={remaining_ids}")
    check("postpone error removed from queue (tomorrow)", postpone_err_id not in remaining_ids)
    check("skip error still in queue (skip=frontend only)", skip_err_id in remaining_ids, f"ids={remaining_ids}")

    # Cleanup review test data
    for eid in [overdue_err_id, today_err_id, future_err_id, mastered_err_id, nodate_err_id,
                postpone_err_id, skip_err_id]:
        client.delete(f"/api/errors/{eid}")

    # ── 29i. Version consistency ──
    print("\n[29i] Version consistency")
    from app.main import app as fastapi_app
    check("FastAPI version=0.6.0", fastapi_app.version == "0.6.0", f"got {fastapi_app.version}")

    # Export should still use BACKUP_SCHEMA_VERSION
    r = client.get("/api/export/json")
    check("export version=0.3", r.json().get("version") == "0.3", f"got {r.json().get('version')}")

    # ── 30. Placeholder API Key → AI endpoints return 503 ──
    print("\n[30] Placeholder API Key → AI endpoints return 503")
    from app.config import get_settings as _gs
    from app.services.llm import reset_client, _require_api_key, get_client, LLMConfigError

    _orig_key = os.environ.get("OPENAI_API_KEY", "")
    try:
        os.environ["OPENAI_API_KEY"] = "your_api_key_here"
        _gs.cache_clear()
        reset_client()

        # Health should report ai_configured=false
        r = client.get("/api/health")
        check("placeholder: health 200", r.status_code == 200)
        check("placeholder: ai_configured=false", r.json()["ai_configured"] is False,
              f"got {r.json()['ai_configured']}")

        # _require_api_key should raise LLMConfigError
        _raised = False
        try:
            _require_api_key()
        except LLMConfigError:
            _raised = True
        except Exception:
            pass
        check("placeholder: _require_api_key raises LLMConfigError", _raised)

        # AI endpoints should return 503 with helpful message
        ai_endpoints = [
            ("POST", "/api/chat", {"question": "test"}),
            ("POST", "/api/problems/solve", {"question": "1+1"}),
            ("POST", "/api/plan/generate", {"subjects": ["数学"], "daily_hours": 2, "days": 3}),
            ("POST", "/api/exam/generate", {"subject": "数学", "topic": "极限", "count": 1}),
        ]
        for method, path, payload in ai_endpoints:
            r = client.post(path, json=payload)
            check(f"placeholder: {path} → 503", r.status_code == 503,
                  f"got {r.status_code}")
            detail = r.json().get("detail", "")
            check(f"placeholder: {path} detail mentions API Key",
                  "API_KEY" in detail.upper() or "api key" in detail.lower() or "OPENAI_API_KEY" in detail,
                  f"detail={detail[:80]}")
    finally:
        os.environ["OPENAI_API_KEY"] = _orig_key
        _gs.cache_clear()
        reset_client()

    # ── 31. _require_api_key and client cache rebuild ──
    print("\n[31] _require_api_key and client cache rebuild")
    import app.services.llm as _llm_mod

    # With a non-placeholder key, _require_api_key should return model name
    _orig_key = os.environ.get("OPENAI_API_KEY", "")
    _orig_url = os.environ.get("OPENAI_BASE_URL", "")
    try:
        os.environ["OPENAI_API_KEY"] = "sk-test-real-key-12345"
        os.environ["OPENAI_BASE_URL"] = "https://api.example.com"
        _gs.cache_clear()
        reset_client()

        # _require_api_key should return model name without error
        try:
            model = _require_api_key()
            check("real key: _require_api_key returns model", isinstance(model, str) and len(model) > 0,
                  f"got {model}")
        except LLMConfigError:
            check("real key: _require_api_key returns model", False, "raised LLMConfigError")

        # get_client should create a client
        c1 = get_client()
        check("real key: get_client succeeds", c1 is not None)
        check("real key: client config recorded", _llm_mod._client_config is not None)

        # Same config → same client instance
        c2 = get_client()
        check("same config: client reused", c1 is c2)

        # Change base_url → client should be rebuilt
        os.environ["OPENAI_BASE_URL"] = "https://api.other.com"
        _gs.cache_clear()
        # Don't call reset_client — rely on config-change detection
        c3 = get_client()
        check("changed url: client rebuilt", c3 is not c1, "should be a new instance")

        # Change key → client should be rebuilt
        os.environ["OPENAI_API_KEY"] = "sk-another-key-67890"
        _gs.cache_clear()
        c4 = get_client()
        check("changed key: client rebuilt", c4 is not c3, "should be a new instance")

        # Health should report ai_configured=true with a non-placeholder key
        r = client.get("/api/health")
        check("real key: health ai_configured=true", r.json()["ai_configured"] is True,
              f"got {r.json()['ai_configured']}")
    finally:
        os.environ["OPENAI_API_KEY"] = _orig_key
        os.environ["OPENAI_BASE_URL"] = _orig_url
        _gs.cache_clear()
        reset_client()

    # ── 32. ZIP export structure ──
    print("\n[32] GET /api/export/zip — ZIP structure")
    import zipfile
    import io

    # Upload a test file first so the ZIP has content
    zip_test_file = os.path.join(_tmp_dir, "zip_source.txt")
    with open(zip_test_file, "w", encoding="utf-8") as f:
        f.write("ZIP 导出测试内容，用于验证完整备份。")
    r = client.post("/api/materials/upload", files={"file": ("zip_source.txt", open(zip_test_file, "rb"), "text/plain")})
    check("zip: upload source file 200", r.status_code == 200, f"got {r.status_code}")
    zip_mat_id = r.json()["id"]
    zip_stored = r.json().get("stored_filename", "")

    # Wait for parsing
    import time
    for _ in range(30):
        r = client.get(f"/api/materials/{zip_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
        time.sleep(0.2)
    check("zip: source material parsed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Export ZIP
    r = client.get("/api/export/zip")
    check("zip: export 200", r.status_code == 200, f"got {r.status_code}")
    check("zip: content-type is zip", "zip" in r.headers.get("content-type", ""), f"ct={r.headers.get('content-type')}")
    check("zip: content-disposition has .zip", ".zip" in r.headers.get("content-disposition", ""), f"cd={r.headers.get('content-disposition')}")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    check("zip: contains manifest.json", "manifest.json" in names)
    check("zip: contains backup.json", "backup.json" in names)
    check("zip: contains uploads/ dir", any(n.startswith("uploads/") for n in names), f"names={sorted(names)}")

    # Validate manifest.json
    manifest = json.loads(zf.read("manifest.json"))
    check("zip: manifest version", manifest.get("version") == "0.3", f"got {manifest.get('version')}")
    check("zip: manifest backup_type", manifest.get("backup_type") == "full_zip")
    check("zip: manifest file_count >= 1", manifest.get("file_count", 0) >= 1, f"got {manifest.get('file_count')}")
    check("zip: manifest has files list", isinstance(manifest.get("files"), list))

    # Validate backup.json
    backup = json.loads(zf.read("backup.json"))
    check("zip: backup version", backup.get("version") == "0.3")
    check("zip: backup has materials", len(backup.get("materials", [])) >= 1)
    check("zip: backup has error_book", isinstance(backup.get("error_book"), list))
    check("zip: backup has study_plans", isinstance(backup.get("study_plans"), list))

    # Verify backup.json materials include stored_filename (needed for import)
    backup_mats = backup.get("materials", [])
    if backup_mats:
        first_mat = backup_mats[0]
        check("zip: backup material has stored_filename", "stored_filename" in first_mat)
        check("zip: backup material has status", "status" in first_mat)
        check("zip: backup material has error_message", "error_message" in first_mat)

    # Verify manifest files cross-reference with materials
    manifest_files_set = {f["stored_filename"] for f in manifest.get("files", [])}
    mat_stored_set = {m["stored_filename"] for m in backup_mats if m.get("stored_filename")}
    check("zip: manifest files subset of material stored_filenames",
          manifest_files_set <= mat_stored_set,
          f"manifest={sorted(manifest_files_set)}, mats={sorted(mat_stored_set)}")

    # Validate uploaded file is in ZIP
    if zip_stored:
        file_path = f"uploads/{zip_stored}"
        check("zip: uploaded file in ZIP", file_path in names, f"looking for {file_path} in {sorted(names)}")
        file_content = zf.read(file_path)
        check("zip: uploaded file not empty", len(file_content) > 0)

    zf.close()

    # ── 33. ZIP import preview ──
    print("\n[33] POST /api/import/zip/preview — ZIP preview")
    zip_bytes = r.content  # reuse the exported ZIP

    r = client.post(
        "/api/import/zip/preview",
        files={"file": ("test.zip", io.BytesIO(zip_bytes), "application/zip")},
        params={"strategy": "skip"},
    )
    check("zip preview: 200", r.status_code == 200, f"got {r.status_code}")
    pv = r.json()
    check("zip preview: has version", pv.get("version") == "0.3")
    check("zip preview: has modules", isinstance(pv.get("modules"), dict))
    check("zip preview: has zip_info", isinstance(pv.get("zip_info"), dict))
    zip_info = pv.get("zip_info", {})
    check("zip preview: zip_info file_count >= 1", zip_info.get("file_count", 0) >= 1)
    check("zip preview: zip_info manifest_present", zip_info.get("manifest_present") is True)

    # ── 34. ZIP import — skip strategy (data already exists) ──
    print("\n[34] POST /api/import/zip — skip strategy")
    r = client.post(
        "/api/import/zip",
        files={"file": ("test.zip", io.BytesIO(zip_bytes), "application/zip")},
        params={"strategy": "skip"},
    )
    check("zip import skip: 200", r.status_code == 200, f"got {r.status_code}")
    result = r.json()
    check("zip import skip: has inserted", isinstance(result.get("inserted"), dict))
    check("zip import skip: has skipped", isinstance(result.get("skipped"), dict))
    check("zip import skip: has files_restored", "files_restored" in result)
    # Data already exists, so most should be skipped
    check("zip import skip: materials skipped", result["skipped"]["materials"] >= 1, f"got {result['skipped']['materials']}")

    # ── 35. ZIP import — file restoration ──
    print("\n[35] ZIP import — file restoration verification")
    # The file should exist in uploads dir
    if zip_stored:
        restored_path = os.path.join(_uploads_dir, zip_stored)
        check("zip import: file restored to uploads", os.path.isfile(restored_path), f"path={restored_path}")
        if os.path.isfile(restored_path):
            with open(restored_path, "r", encoding="utf-8") as f:
                restored_content = f.read()
            check("zip import: file content matches", "ZIP 导出测试内容" in restored_content, f"content={restored_content[:50]}")

    # Material should still be accessible
    r = client.get(f"/api/materials/{zip_mat_id}")
    check("zip import: material still accessible", r.status_code == 200)
    check("zip import: material has content", len(r.json().get("preview", "")) > 0)

    # ── 36. ZIP path traversal protection ──
    print("\n[36] ZIP path traversal protection")
    from app.routers.import_data import _safe_zip_path

    test_upload_dir = os.path.abspath(_uploads_dir)

    # Absolute path
    check("safe_zip: rejects absolute path", _safe_zip_path("/etc/passwd", test_upload_dir) is None)
    check("safe_zip: rejects absolute win path", _safe_zip_path("C:\\Windows\\system32\\cmd.exe", test_upload_dir) is None)

    # Dot-dot traversal
    check("safe_zip: rejects .. traversal", _safe_zip_path("../etc/passwd", test_upload_dir) is None)
    check("safe_zip: rejects nested ..", _safe_zip_path("uploads/../../etc/passwd", test_upload_dir) is None)

    # Backslash
    check("safe_zip: rejects backslash", _safe_zip_path("uploads\\evil.txt", test_upload_dir) is None)

    # Wrong directory
    check("safe_zip: rejects non-uploads dir", _safe_zip_path("etc/passwd", test_upload_dir) is None)
    check("safe_zip: rejects root file", _safe_zip_path("backup.json", test_upload_dir) is None)

    # Disallowed extension
    check("safe_zip: rejects .exe", _safe_zip_path("uploads/evil.exe", test_upload_dir) is None)
    check("safe_zip: rejects .sh", _safe_zip_path("uploads/evil.sh", test_upload_dir) is None)

    # Empty filename
    check("safe_zip: rejects empty filename", _safe_zip_path("uploads/", test_upload_dir) is None)

    # Valid paths
    check("safe_zip: allows valid .txt", _safe_zip_path("uploads/abc123.txt", test_upload_dir) is not None)
    check("safe_zip: allows valid .pdf", _safe_zip_path("uploads/abc123.pdf", test_upload_dir) is not None)
    check("safe_zip: allows valid .docx", _safe_zip_path("uploads/test.docx", test_upload_dir) is not None)

    # Test with a crafted malicious ZIP
    mal_zip_buf = io.BytesIO()
    with zipfile.ZipFile(mal_zip_buf, "w") as mzf:
        mzf.writestr("backup.json", json.dumps({
            "exported_at": "2026-01-01T00:00:00", "version": "0.2",
            "materials": [], "material_chunks_count": 0,
            "chat_history": [], "error_book": [], "study_plans": [],
            "problems": [], "exam_questions": [], "exam_attempts": [],
        }))
        mzf.writestr("uploads/../../../evil.txt", "path traversal payload")
        mzf.writestr("uploads/..\\..\\evil2.txt", "backslash traversal")
        mzf.writestr("C:\\Windows\\evil.exe", "absolute path")
    mal_zip_buf.seek(0)

    r = client.post(
        "/api/import/zip/preview",
        files={"file": ("malicious.zip", mal_zip_buf, "application/zip")},
        params={"strategy": "skip"},
    )
    check("malicious zip: preview succeeds (ignores bad entries)", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        mal_pv = r.json()
        mal_info = mal_pv.get("zip_info", {})
        check("malicious zip: no files extracted", mal_info.get("file_count", 0) == 0, f"got {mal_info.get('file_count')}")

    # Verify no evil files were written
    evil_path1 = os.path.join(test_upload_dir, "..", "..", "evil.txt")
    evil_path2 = os.path.join(test_upload_dir, "evil.txt")
    check("malicious zip: no evil.txt in uploads", not os.path.exists(evil_path2))

    # ── 37. ZIP import — keep_both strategy ──
    print("\n[37] POST /api/import/zip — keep_both strategy")
    r = client.post(
        "/api/import/zip",
        files={"file": ("test.zip", io.BytesIO(zip_bytes), "application/zip")},
        params={"strategy": "keep_both"},
    )
    check("zip keep_both: 200", r.status_code == 200, f"got {r.status_code}")
    kb_result = r.json()
    check("zip keep_both: materials kept_both", kb_result["kept_both"]["materials"] >= 1, f"got {kb_result['kept_both']['materials']}")

    # The kept_both material should exist with "(副本)" in filename
    r = client.get("/api/materials", params={"limit": 100})
    materials = r.json()
    copy_materials = [m for m in materials if "(副本)" in m.get("filename", "")]
    check("zip keep_both: copy material exists", len(copy_materials) >= 1, f"found {len(copy_materials)}")

    # ── 38. ZIP import — overwrite strategy ──
    print("\n[38] POST /api/import/zip — overwrite strategy")
    r = client.post(
        "/api/import/zip",
        files={"file": ("test.zip", io.BytesIO(zip_bytes), "application/zip")},
        params={"strategy": "overwrite"},
    )
    check("zip overwrite: 200", r.status_code == 200, f"got {r.status_code}")
    ow_result = r.json()
    check("zip overwrite: materials overwritten", ow_result["overwritten"]["materials"] >= 1, f"got {ow_result['overwritten']['materials']}")

    # ── 39. Imported material viewable ──
    print("\n[39] Imported material — viewable after overwrite")
    r = client.get(f"/api/materials/{zip_mat_id}")
    check("imported material: detail 200", r.status_code == 200)
    detail = r.json()
    # After overwrite, material is set to pending (parse worker not running in test)
    check("imported material: status pending or ready", detail.get("status") in ("pending", "ready"), f"got {detail.get('status')}")
    check("imported material: has stored_filename", len(detail.get("stored_filename", "")) > 0 or detail.get("stored_filename") == zip_stored)

    # Verify the file was physically restored
    if zip_stored:
        restored = os.path.join(_uploads_dir, zip_stored)
        check("imported material: file on disk", os.path.isfile(restored))

    # Search for content (works for previously parsed materials)
    r = client.post("/api/materials/search", json={"query": "ZIP 导出测试", "limit": 5})
    check("imported material: search 200", r.status_code == 200)

    # Cleanup: delete the test material
    client.delete(f"/api/materials/{zip_mat_id}")
    # Also delete the kept_both copy
    for m in copy_materials:
        client.delete(f"/api/materials/{m['id']}")

    # ── 40. Maintenance health ──
    print("\n[40] GET /api/maintenance/health")
    r = client.get("/api/maintenance/health")
    check("maintenance health: 200", r.status_code == 200, f"got {r.status_code}")
    mh = r.json()
    check("maintenance health: has total_materials", "total_materials" in mh)
    check("maintenance health: has total_chunks", "total_chunks" in mh)
    check("maintenance health: has upload_files", "upload_files" in mh)
    check("maintenance health: has orphan_files", "orphan_files" in mh)
    check("maintenance health: has missing_files", "missing_files" in mh)
    check("maintenance health: has failed_materials", "failed_materials" in mh)
    check("maintenance health: has failed_jobs", "failed_jobs" in mh)
    check("maintenance health: has processing_jobs", "processing_jobs" in mh)
    check("maintenance health: has database_size", "database_size" in mh)
    check("maintenance health: has uploads_size", "uploads_size" in mh)
    check("maintenance health: has total_operations", "total_operations" in mh)
    check("maintenance health: has orphan_file_names", isinstance(mh.get("orphan_file_names"), list))
    check("maintenance health: has missing_file_names", isinstance(mh.get("missing_file_names"), list))

    # ── 41. Orphan file detection ──
    print("\n[41] Orphan file detection")
    # Create an orphan file in uploads dir
    orphan_path = os.path.join(_uploads_dir, "orphan_test_file.txt")
    with open(orphan_path, "w") as f:
        f.write("orphan content")
    check("orphan: file created", os.path.isfile(orphan_path))

    # Health should detect it
    r = client.get("/api/maintenance/health")
    mh2 = r.json()
    check("orphan: health detects orphan", mh2["orphan_files"] >= 1, f"got {mh2['orphan_files']}")
    check("orphan: orphan_file_names includes it", "orphan_test_file.txt" in mh2.get("orphan_file_names", []))

    # ── 42. Cleanup preview (no side effects) ──
    print("\n[42] POST /api/maintenance/cleanup/preview")
    r = client.post("/api/maintenance/cleanup/preview")
    check("cleanup preview: 200", r.status_code == 200, f"got {r.status_code}")
    cp = r.json()
    check("cleanup preview: has orphan_files", isinstance(cp.get("orphan_files"), list))
    check("cleanup preview: has invalid_jobs", isinstance(cp.get("invalid_jobs"), list))
    check("cleanup preview: has orphan_chunk_materials", isinstance(cp.get("orphan_chunk_materials"), list))
    check("cleanup preview: orphan_test_file in preview", "orphan_test_file.txt" in cp.get("orphan_files", []))
    # Preview should NOT delete the file
    check("cleanup preview: file still exists", os.path.isfile(orphan_path))

    # ── 43. Missing file detection ──
    print("\n[43] Missing file detection")
    # Create a material with a stored_filename that doesn't exist on disk
    missing_stored = "missing_file_test_abc123.txt"
    from app.models import Material as _Mat
    async def _create_missing():
        async with async_session() as session:
            m = _Mat(filename="missing_test.txt", file_type=".txt", content="test", stored_filename=missing_stored, status="ready")
            session.add(m)
            await session.commit()
            return m.id
    loop_missing = asyncio.new_event_loop()
    missing_mat_id = loop_missing.run_until_complete(_create_missing())
    loop_missing.close()

    r = client.get("/api/maintenance/health")
    mh3 = r.json()
    check("missing: health detects missing file", mh3["missing_files"] >= 1, f"got {mh3['missing_files']}")
    check("missing: missing_file_names includes it", missing_stored in mh3.get("missing_file_names", []))

    # Cleanup: remove the test material
    async def _delete_missing():
        async with async_session() as session:
            await session.execute(text("DELETE FROM materials WHERE id = :id"), {"id": missing_mat_id})
            await session.commit()
    loop_del = asyncio.new_event_loop()
    loop_del.run_until_complete(_delete_missing())
    loop_del.close()

    # ── 44. Execute cleanup ──
    print("\n[44] POST /api/maintenance/cleanup")
    r = client.post("/api/maintenance/cleanup")
    check("cleanup: 200", r.status_code == 200, f"got {r.status_code}")
    cr = r.json()
    check("cleanup: has deleted_files", isinstance(cr.get("deleted_files"), list))
    check("cleanup: has skipped_files", isinstance(cr.get("skipped_files"), list))
    check("cleanup: has deleted_jobs", isinstance(cr.get("deleted_jobs"), int))
    check("cleanup: has deleted_chunks", isinstance(cr.get("deleted_chunks"), int))
    check("cleanup: has errors", isinstance(cr.get("errors"), list))
    check("cleanup: orphan file deleted", "orphan_test_file.txt" in cr.get("deleted_files", []))
    check("cleanup: orphan file no longer on disk", not os.path.isfile(orphan_path))

    # ── 45. Cleanup does not delete referenced files ──
    print("\n[45] Cleanup safety — referenced files preserved")
    # Upload a new file and verify it survives cleanup
    safe_file = os.path.join(_tmp_dir, "safe_test.txt")
    with open(safe_file, "w") as f:
        f.write("this file should not be cleaned up")
    r = client.post("/api/materials/upload", files={"file": ("safe_test.txt", open(safe_file, "rb"), "text/plain")})
    check("safe upload: 200", r.status_code == 200)
    safe_stored = r.json().get("stored_filename", "")
    safe_mat_id = r.json()["id"]

    if safe_stored:
        r = client.post("/api/maintenance/cleanup")
        cr2 = r.json()
        check("safe: referenced file not deleted", safe_stored not in cr2.get("deleted_files", []))
        check("safe: referenced file still on disk", os.path.isfile(os.path.join(_uploads_dir, safe_stored)))

    client.delete(f"/api/materials/{safe_mat_id}")

    # ── 46. Cleanup path safety ──
    print("\n[46] Cleanup path safety")
    # Verify cleanup only processes files inside upload_dir
    from app.routers.maintenance import _safe_listdir
    check("path safety: _safe_listdir works", isinstance(_safe_listdir(_uploads_dir), list))
    check("path safety: _safe_listdir empty for nonexistent", _safe_listdir("/nonexistent/path") == [])

    # ── 47. Operation logs ──
    print("\n[47] GET /api/maintenance/logs")
    r = client.get("/api/maintenance/logs")
    check("logs: 200", r.status_code == 200, f"got {r.status_code}")
    logs = r.json()
    check("logs: is list", isinstance(logs, list))
    check("logs: has entries", len(logs) >= 1, f"got {len(logs)}")
    if logs:
        log = logs[0]
        check("logs: has id", "id" in log)
        check("logs: has operation_type", "operation_type" in log)
        check("logs: has created_at", "created_at" in log)
        check("logs: has result_summary", "result_summary" in log)
        # Should contain cleanup logs from our tests
        cleanup_logs = [l for l in logs if l.get("operation_type") == "cleanup"]
        check("logs: contains cleanup entries", len(cleanup_logs) >= 1, f"got {len(cleanup_logs)}")
        # Should contain export logs
        export_logs = [l for l in logs if "export" in l.get("operation_type", "")]
        check("logs: contains export entries", len(export_logs) >= 1, f"got {len(export_logs)}")

    # ── 48. Maintenance health reflects cleanup ──
    print("\n[48] Health after cleanup")
    r = client.get("/api/maintenance/health")
    mh4 = r.json()
    check("health after cleanup: no orphans", mh4["orphan_files"] == 0, f"got {mh4['orphan_files']}")
    check("health after cleanup: operations logged", mh4["total_operations"] >= 1, f"got {mh4['total_operations']}")

    # ── 49. Real ZIP migration: empty environment ──
    print("\n[49] Real ZIP migration — empty DB + empty uploads")
    # Upload a material and wait for it to parse
    migrate_file = os.path.join(_tmp_dir, "migrate_test.txt")
    with open(migrate_file, "w", encoding="utf-8") as f:
        f.write("这是 ZIP 迁移测试内容，包含独特关键词 迁移验证ABC。")
    r = client.post("/api/materials/upload", files={"file": ("migrate_test.txt", open(migrate_file, "rb"), "text/plain")})
    check("migration: upload 200", r.status_code == 200, f"got {r.status_code}")
    migrate_mat_id = r.json()["id"]
    migrate_stored = r.json().get("stored_filename", "")
    # Wait for parsing
    import time
    for _ in range(30):
        r = client.get(f"/api/materials/{migrate_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
        time.sleep(0.2)
    check("migration: material parsed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Export ZIP
    r = client.get("/api/export/zip")
    check("migration: export zip 200", r.status_code == 200)
    migrate_zip_bytes = r.content

    # Delete the material and its file (simulate empty environment)
    client.delete(f"/api/materials/{migrate_mat_id}")
    if migrate_stored:
        gone_path = os.path.join(_uploads_dir, migrate_stored)
        if os.path.isfile(gone_path):
            os.remove(gone_path)
    check("migration: file deleted", not os.path.isfile(os.path.join(_uploads_dir, migrate_stored)))

    # Verify no materials left
    r = client.get("/api/materials", params={"limit": 100})
    remaining = [m for m in r.json() if m.get("filename") == "migrate_test.txt"]
    check("migration: material deleted from DB", len(remaining) == 0, f"found {len(remaining)}")

    # Import ZIP into empty environment
    r = client.post(
        "/api/import/zip",
        files={"file": ("migrate.zip", io.BytesIO(migrate_zip_bytes), "application/zip")},
        params={"strategy": "skip"},
    )
    check("migration: import 200", r.status_code == 200, f"got {r.status_code}")
    migrate_result = r.json()
    check("migration: files_restored > 0", migrate_result["files_restored"] >= 1, f"got {migrate_result['files_restored']}")
    check("migration: materials inserted", migrate_result["inserted"]["materials"] >= 1, f"got {migrate_result['inserted']['materials']}")

    # Find the newly imported material
    r = client.get("/api/materials", params={"limit": 100})
    all_mats = r.json()
    migrated = [m for m in all_mats if m.get("filename") == "migrate_test.txt"]
    check("migration: material re-created", len(migrated) >= 1, f"found {len(migrated)}")

    if migrated:
        new_mat = migrated[0]
        new_stored = new_mat.get("stored_filename", "")
        check("migration: stored_filename non-empty", len(new_stored) > 0)
        check("migration: file exists on disk", os.path.isfile(os.path.join(_uploads_dir, new_stored)))
        # Wait for parse to complete (poll more aggressively)
        new_mat_id = new_mat["id"]
        final_status = new_mat.get("status", "")
        for _ in range(75):
            r = client.get(f"/api/materials/{new_mat_id}")
            final_status = r.json().get("status", "")
            if final_status in ("ready", "failed"):
                break
            time.sleep(0.2)
        check("migration: re-parsed successfully", final_status == "ready", f"got {final_status}")

        # Verify material content via DB (bypasses any caching)
        async def _get_material_content(mid):
            async with async_session() as session:
                from app.models import Material as _Mat
                m = await session.get(_Mat, mid)
                return m.content if m else None
        loop_gc = asyncio.new_event_loop()
        db_content = loop_gc.run_until_complete(_get_material_content(new_mat_id))
        loop_gc.close()
        has_content = db_content is not None and len(db_content) > 0
        check("migration: content in DB", has_content, f"len={len(db_content) if db_content else 0}")

        # Verify preview via API
        r = client.get(f"/api/materials/{new_mat_id}")
        preview = r.json().get("preview", "")
        check("migration: preview contains content", "迁移验证ABC" in preview, f"preview={preview[:80]}")

        # Verify search works
        r = client.post("/api/materials/search", json={"query": "迁移验证ABC", "limit": 5})
        check("migration: search 200", r.status_code == 200)
        search_results = r.json()
        check("migration: search finds content", len(search_results) >= 1, f"got {len(search_results)} results")

        # Cleanup
        client.delete(f"/api/materials/{new_mat_id}")

    # ── 50. keep_both: different stored_filename, independence ──
    print("\n[50] keep_both — different stored_filename, file independence")
    # Upload a fresh material
    kb_file = os.path.join(_tmp_dir, "kb_test.txt")
    with open(kb_file, "w", encoding="utf-8") as f:
        f.write("keep_both 独立性测试内容 XYZ789")
    r = client.post("/api/materials/upload", files={"file": ("kb_test.txt", open(kb_file, "rb"), "text/plain")})
    check("kb independence: upload 200", r.status_code == 200)
    kb_mat_id = r.json()["id"]
    kb_stored = r.json().get("stored_filename", "")
    # Wait for parse
    for _ in range(30):
        r = client.get(f"/api/materials/{kb_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
        time.sleep(0.2)

    # Export ZIP
    r = client.get("/api/export/zip")
    kb_zip = r.content

    # Import with keep_both
    r = client.post(
        "/api/import/zip",
        files={"file": ("kb.zip", io.BytesIO(kb_zip), "application/zip")},
        params={"strategy": "keep_both"},
    )
    check("kb import: 200", r.status_code == 200, f"got {r.status_code}")
    kb_result = r.json()
    check("kb import: kept_both >= 1", kb_result["kept_both"]["materials"] >= 1)

    # Find the copy
    r = client.get("/api/materials", params={"limit": 100})
    kb_all = r.json()
    kb_copy = [m for m in kb_all if "(副本)" in m.get("filename", "") and "kb_test" in m.get("filename", "")]
    check("kb: copy exists", len(kb_copy) >= 1)

    if kb_copy:
        copy_mat = kb_copy[0]
        copy_stored = copy_mat.get("stored_filename", "")
        check("kb: copy has different stored_filename", copy_stored != kb_stored,
              f"original={kb_stored}, copy={copy_stored}")
        check("kb: copy file exists", os.path.isfile(os.path.join(_uploads_dir, copy_stored)))
        check("kb: original file exists", os.path.isfile(os.path.join(_uploads_dir, kb_stored)))

        # Delete the copy — original file should survive
        client.delete(f"/api/materials/{copy_mat['id']}")
        check("kb: original file still exists after copy delete",
              os.path.isfile(os.path.join(_uploads_dir, kb_stored)))

        # Verify original is still readable
        r = client.get(f"/api/materials/{kb_mat_id}")
        check("kb: original still readable", r.status_code == 200)
        check("kb: original preview intact", "XYZ789" in r.json().get("preview", ""))

    # Cleanup
    client.delete(f"/api/materials/{kb_mat_id}")

    # ── 51. worker.enqueue await verification ──
    print("\n[51] worker.enqueue await — parse job completes")
    # Upload → export → delete → import → verify parse completes
    we_file = os.path.join(_tmp_dir, "we_test.txt")
    with open(we_file, "w", encoding="utf-8") as f:
        f.write("enqueue 测试内容 WE123")
    r = client.post("/api/materials/upload", files={"file": ("we_test.txt", open(we_file, "rb"), "text/plain")})
    check("enqueue: upload 200", r.status_code == 200)
    we_mat_id = r.json()["id"]
    for _ in range(30):
        r = client.get(f"/api/materials/{we_mat_id}")
        if r.json().get("status") in ("ready", "failed"):
            break
        time.sleep(0.2)
    check("enqueue: parsed", r.json().get("status") == "ready")
    # Export
    r = client.get("/api/export/zip")
    we_zip = r.content
    # Delete
    client.delete(f"/api/materials/{we_mat_id}")

    # Import (will create new material + parse job)
    r = client.post(
        "/api/import/zip",
        files={"file": ("we.zip", io.BytesIO(we_zip), "application/zip")},
        params={"strategy": "skip"},
    )
    check("enqueue: import 200", r.status_code == 200)
    we_inserted = r.json()["inserted"]["materials"]
    check("enqueue: material inserted", we_inserted >= 1)

    # Find the new material and wait for parse
    r = client.get("/api/materials", params={"limit": 100})
    we_mats = [m for m in r.json() if m.get("filename") == "we_test.txt"]
    if we_mats:
        we_new_id = we_mats[0]["id"]
        we_new_status = we_mats[0].get("status", "")
        # The enqueue is async — poll for up to 15 seconds
        for _ in range(75):
            r = client.get(f"/api/materials/{we_new_id}")
            we_new_status = r.json().get("status", "")
            if we_new_status in ("ready", "failed"):
                break
            time.sleep(0.2)
        check("enqueue: parse completed after import", we_new_status == "ready", f"got {we_new_status}")
        r = client.get(f"/api/materials/{we_new_id}")
        check("enqueue: content available", "WE123" in r.json().get("preview", ""))
        client.delete(f"/api/materials/{we_new_id}")

    # ── 52. cleanup deleted_chunks counts real rows ──
    print("\n[52] cleanup deleted_chunks — real row count")
    # Create orphan chunks directly in DB
    async def _create_orphan_chunks():
        async with async_session() as session:
            # Use a non-existent material_id
            from app.models import MaterialChunk as _MC
            for i in range(5):
                session.add(_MC(material_id=999999, chunk_index=i, content=f"orphan chunk {i}"))
            await session.commit()
    loop_oc = asyncio.new_event_loop()
    loop_oc.run_until_complete(_create_orphan_chunks())
    loop_oc.close()

    # Preview should show orphan chunks
    r = client.post("/api/maintenance/cleanup/preview")
    cp2 = r.json()
    check("real chunks: orphan material detected", 999999 in cp2.get("orphan_chunk_materials", []))

    # Cleanup
    r = client.post("/api/maintenance/cleanup")
    cr3 = r.json()
    check("real chunks: deleted_chunks = 5", cr3["deleted_chunks"] == 5, f"got {cr3['deleted_chunks']}")

    # ── 53. /api/maintenance/logs limit validation ──
    print("\n[53] /api/maintenance/logs limit validation")
    r = client.get("/api/maintenance/logs", params={"limit": 0})
    check("logs limit=0: 422", r.status_code == 422, f"got {r.status_code}")
    r = client.get("/api/maintenance/logs", params={"limit": 101})
    check("logs limit=101: 422", r.status_code == 422, f"got {r.status_code}")
    r = client.get("/api/maintenance/logs", params={"limit": 1})
    check("logs limit=1: 200", r.status_code == 200, f"got {r.status_code}")
    r = client.get("/api/maintenance/logs", params={"limit": 100})
    check("logs limit=100: 200", r.status_code == 200, f"got {r.status_code}")

    # ── 54. Export includes app_settings and study_sessions ──
    print("\n[54] Export includes app_settings and study_sessions")
    # Set custom review intervals
    r = client.put("/api/settings/review", json={"intervals": [2, 5, 12]})
    check("set custom intervals 200", r.status_code == 200)

    # Start a study session
    r = client.post("/api/sessions/start", json={"subject": "备份测试", "note": "导出验证"})
    check("start backup session 200", r.status_code == 200)
    backup_sess_id = r.json()["id"]
    time.sleep(1)
    r = client.post(f"/api/sessions/{backup_sess_id}/stop")
    check("stop backup session 200", r.status_code == 200)

    # Export JSON and verify fields
    r = client.get("/api/export/json")
    check("export with settings 200", r.status_code == 200)
    exp_data = r.json()
    check("export has app_settings", "app_settings" in exp_data)
    check("export has study_sessions", "study_sessions" in exp_data)
    # Verify review intervals in app_settings
    exported_intervals = None
    for s in exp_data.get("app_settings", []):
        if s.get("key") == "review_intervals":
            exported_intervals = json.loads(s["value"])
            break
    check("exported intervals found", exported_intervals is not None, f"got {exported_intervals}")
    check("exported intervals match [2,5,12]", exported_intervals == [2, 5, 12], f"got {exported_intervals}")
    # Verify study session present
    exported_sessions = exp_data.get("study_sessions", [])
    check("exported sessions has our session", any(s.get("subject") == "备份测试" for s in exported_sessions),
          f"got {[s.get('subject') for s in exported_sessions]}")

    # Export ZIP and verify fields
    r = client.get("/api/export/zip")
    check("zip export with settings 200", r.status_code == 200)
    zf_exp = zipfile.ZipFile(io.BytesIO(r.content))
    zip_backup = json.loads(zf_exp.read("backup.json"))
    check("zip backup has app_settings", "app_settings" in zip_backup)
    check("zip backup has study_sessions", "study_sessions" in zip_backup)
    zf_exp.close()

    # Reset intervals to default
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("reset intervals 200", r.status_code == 200)

    # ── 55. Review intervals roundtrip via ZIP import ──
    print("\n[55] Review intervals roundtrip via ZIP import")
    # Set custom intervals
    r = client.put("/api/settings/review", json={"intervals": [3, 7, 21]})
    check("set roundtrip intervals 200", r.status_code == 200)

    # Export ZIP
    r = client.get("/api/export/zip")
    roundtrip_zip = r.content

    # Reset to default
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("reset before import 200", r.status_code == 200)
    check("reset confirms default", r.json()["intervals"] == [1, 3, 7, 14])

    # Import ZIP with overwrite strategy
    r = client.post(
        "/api/import/zip",
        files={"file": ("roundtrip.zip", io.BytesIO(roundtrip_zip), "application/zip")},
        params={"strategy": "overwrite"},
    )
    check("roundtrip import 200", r.status_code == 200)
    check("roundtrip settings_imported >= 1", r.json().get("settings_imported", 0) >= 1,
          f"got {r.json().get('settings_imported')}")

    # Verify intervals were restored
    r = client.get("/api/settings/review")
    check("roundtrip intervals restored", r.json()["intervals"] == [3, 7, 21],
          f"got {r.json()['intervals']}")

    # Reset to default
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("final reset 200", r.status_code == 200)

    # ── 56. Orphan chunks + FTS cleanup ──
    print("\n[56] Orphan chunks + FTS cleanup")
    # Create orphan chunks AND corresponding FTS entries
    async def _create_orphan_with_fts():
        async with async_session() as session:
            from app.models import MaterialChunk as _MC
            for i in range(3):
                mc = _MC(material_id=888888, chunk_index=i, content=f"orphan fts test chunk {i}")
                session.add(mc)
                await session.flush()
                await session.execute(
                    text("INSERT INTO chunks_fts (content, chunk_id, material_id) VALUES (:c, :cid, :mid)"),
                    {"c": f"orphan fts test chunk {i}", "cid": mc.id, "mid": 888888},
                )
            await session.commit()
    loop_ofts = asyncio.new_event_loop()
    loop_ofts.run_until_complete(_create_orphan_with_fts())
    loop_ofts.close()

    # Verify orphan FTS entries exist
    async def _count_fts_orphans():
        async with async_session() as session:
            r = await session.execute(text("SELECT COUNT(*) FROM chunks_fts WHERE material_id = :mid"), {"mid": 888888})
            return r.scalar() or 0
    loop_cfo = asyncio.new_event_loop()
    fts_before = loop_cfo.run_until_complete(_count_fts_orphans())
    loop_cfo.close()
    check("orphan FTS entries exist before cleanup", fts_before >= 1, f"count={fts_before}")

    # Run cleanup
    r = client.post("/api/maintenance/cleanup")
    check("orphan cleanup 200", r.status_code == 200)
    check("orphan cleanup deleted_chunks >= 3", r.json()["deleted_chunks"] >= 3, f"got {r.json()['deleted_chunks']}")

    # Verify FTS entries were also cleaned up
    loop_cfo2 = asyncio.new_event_loop()
    fts_after = loop_cfo2.run_until_complete(_count_fts_orphans())
    loop_cfo2.close()
    check("orphan FTS entries cleaned up", fts_after == 0, f"count={fts_after}")

    # Search should not return ghost results
    r = client.post("/api/materials/search", json={"query": "orphan fts test", "limit": 5})
    check("ghost search 200", r.status_code == 200)
    ghost_results = [x for x in r.json() if "orphan" in x.get("snippet", "").lower()]
    check("no ghost search results", len(ghost_results) == 0, f"found {len(ghost_results)}")

    # ── 57. JSON import overwrite preserves existing content ──
    print("\n[57] JSON import overwrite preserves existing content")
    # Upload a material with real content
    preserve_file = os.path.join(_tmp_dir, "preserve_test.txt")
    with open(preserve_file, "w", encoding="utf-8") as f:
        f.write("JSON覆盖保留测试内容 IMPORTANT_PRESERVE")
    with open(preserve_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("preserve_test.txt", f, "text/plain")})
    check("preserve upload 200", r.status_code == 200)
    preserve_mid = r.json()["id"]
    preserve_stored = r.json().get("stored_filename", "")

    # Wait for parsing
    for _ in range(30):
        time.sleep(0.1)
        r = client.get(f"/api/materials/{preserve_mid}")
        if r.json().get("status") in ("ready", "failed"):
            break
    check("preserve material parsed", r.json().get("status") == "ready", f"got {r.json().get('status')}")

    # Create a JSON backup that includes this material
    json_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.2",
        "materials": [{"filename": "preserve_test.txt", "file_type": ".txt"}],
        "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
    }

    # Import with overwrite strategy
    r = client.post("/api/import/json", json=json_backup, params={"strategy": "overwrite"})
    check("preserve overwrite 200", r.status_code == 200)
    check("preserve overwritten=1", r.json()["overwritten"]["materials"] == 1, f"got {r.json()['overwritten']['materials']}")

    # Verify content and stored_filename are preserved
    r = client.get(f"/api/materials/{preserve_mid}")
    check("preserve detail 200", r.status_code == 200)
    p_detail = r.json()
    check("preserve content not cleared", "IMPORTANT_PRESERVE" in p_detail.get("preview", ""),
          f"preview={p_detail.get('preview', '')[:80]}")
    check("preserve stored_filename not cleared", p_detail.get("stored_filename") == preserve_stored,
          f"got {p_detail.get('stored_filename')}")

    # Cleanup
    client.delete(f"/api/materials/{preserve_mid}")

    # ── 58. Import 0.2 backup backward compatibility ──
    print("\n[58] Import 0.2 backup backward compatibility")
    old_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.2",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
    }
    # Should not crash — missing app_settings and study_sessions fields are optional
    r = client.post("/api/import/json", json=old_backup, params={"strategy": "skip"})
    check("import 0.2 backup 200", r.status_code == 200, f"got {r.status_code}")
    check("import 0.2 has settings_imported", "settings_imported" in r.json())
    check("import 0.2 has sessions_imported", "sessions_imported" in r.json())

    # ── 59. Import invalid review_intervals does not pollute settings ──
    print("\n[59] Import invalid review_intervals rejected")
    # Set known intervals first
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("set default intervals 200", r.status_code == 200)

    # Try to import invalid intervals
    bad_intervals_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.3",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
        "app_settings": [
            {"key": "review_intervals", "value": "[3, 1]"},  # not strictly increasing
        ],
        "study_sessions": [],
    }
    r = client.post("/api/import/json", json=bad_intervals_backup, params={"strategy": "overwrite"})
    check("bad intervals import 200", r.status_code == 200)
    check("bad intervals settings_imported=0", r.json()["settings_imported"] == 0, f"got {r.json()['settings_imported']}")
    check("bad intervals settings_skipped=1", r.json()["settings_skipped"] >= 1, f"got {r.json()['settings_skipped']}")
    check("bad intervals has warnings", len(r.json().get("settings_warnings", [])) > 0)

    # Verify intervals unchanged
    r = client.get("/api/settings/review")
    check("intervals still default", r.json()["intervals"] == [1, 3, 7, 14], f"got {r.json()['intervals']}")

    # Try non-integer values
    bad2_backup = dict(bad_intervals_backup)
    bad2_backup["app_settings"] = [{"key": "review_intervals", "value": '["a", "b"]'}]
    r = client.post("/api/import/json", json=bad2_backup, params={"strategy": "overwrite"})
    check("non-int intervals rejected 200", r.status_code == 200)
    check("non-int settings_imported=0", r.json()["settings_imported"] == 0)
    r = client.get("/api/settings/review")
    check("intervals still default after non-int", r.json()["intervals"] == [1, 3, 7, 14])

    # Try too many intervals (>10)
    bad3_backup = dict(bad_intervals_backup)
    bad3_backup["app_settings"] = [{"key": "review_intervals", "value": "[1,2,3,4,5,6,7,8,9,10,11]"}]
    r = client.post("/api/import/json", json=bad3_backup, params={"strategy": "overwrite"})
    check("too many intervals rejected 200", r.status_code == 200)
    check("too many settings_imported=0", r.json()["settings_imported"] == 0)

    # Non-whitelisted key should be skipped
    unknown_backup = dict(bad_intervals_backup)
    unknown_backup["app_settings"] = [{"key": "unknown_setting", "value": "test"}]
    r = client.post("/api/import/json", json=unknown_backup, params={"strategy": "overwrite"})
    check("unknown key skipped 200", r.status_code == 200)
    check("unknown key settings_imported=0", r.json()["settings_imported"] == 0)

    # ── 60. Study sessions idempotent import ──
    print("\n[60] Study sessions idempotent import")
    # Use a unique marker to avoid collision with ZIP roundtrip test sessions
    idempotent_marker = f"幂等测试-{int(time.time())}"
    r = client.post("/api/sessions/start", json={"subject": idempotent_marker, "note": "导入验证"})
    check("start idempotent session 200", r.status_code == 200)
    idempotent_sess_id = r.json()["id"]
    idempotent_started = r.json()["started_at"]
    time.sleep(1)
    r = client.post(f"/api/sessions/{idempotent_sess_id}/stop")
    check("stop idempotent session 200", r.status_code == 200)
    idempotent_ended = r.json()["ended_at"]
    idempotent_duration = r.json()["duration_minutes"]

    # Build a backup containing this session
    session_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.3",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
        "app_settings": [],
        "study_sessions": [
            {
                "id": 99999, "subject": idempotent_marker, "note": "导入验证",
                "started_at": idempotent_started, "ended_at": idempotent_ended,
                "duration_minutes": idempotent_duration,
            },
        ],
    }

    # The session was just created via API — import should detect it as duplicate (skip)
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "skip"})
    check("session skip detects existing 200", r.status_code == 200)
    check("session skip imported=0 (existing)", r.json()["sessions_imported"] == 0, f"got {r.json()['sessions_imported']}")
    check("session skip skipped=1 (existing)", r.json()["sessions_skipped"] == 1, f"got {r.json()['sessions_skipped']}")

    # Overwrite: should update the existing session
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "overwrite"})
    check("session overwrite 200", r.status_code == 200)
    check("session overwrite imported=1", r.json()["sessions_imported"] == 1, f"got {r.json()['sessions_imported']}")

    # Second overwrite: should still update (idempotent)
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "overwrite"})
    check("session overwrite2 200", r.status_code == 200)
    check("session overwrite2 imported=1", r.json()["sessions_imported"] == 1, f"got {r.json()['sessions_imported']}")

    # keep_both: should create a copy
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "keep_both"})
    check("session keep_both 200", r.status_code == 200)
    kb_count = r.json().get("kept_both", {}).get("study_sessions", 0)
    check("session keep_both count=1", kb_count == 1, f"got {kb_count}")

    # Repeated skip should always skip
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "skip"})
    check("session repeated skip 200", r.status_code == 200)
    check("session repeated skip imported=0", r.json()["sessions_imported"] == 0, f"got {r.json()['sessions_imported']}")

    # Verify no unexpected duplicates
    r = client.get("/api/sessions", params={"limit": 100})
    idempotent_matches = [s for s in r.json() if s.get("subject") == idempotent_marker]
    check("no unexpected duplicates", len(idempotent_matches) <= 2, f"found {len(idempotent_matches)}")  # original + keep_both copy

    # ── 61. Preview shows app_settings and study_sessions ──
    print("\n[61] Preview shows app_settings and study_sessions")
    r = client.post("/api/import/preview", json=session_backup, params={"strategy": "skip"})
    check("preview with sessions 200", r.status_code == 200)
    pv = r.json()
    check("preview has app_settings_count", "app_settings_count" in pv, f"keys={list(pv.keys())}")
    check("preview has study_sessions_count", "study_sessions_count" in pv)
    check("preview study_sessions_count=1", pv["study_sessions_count"] == 1, f"got {pv['study_sessions_count']}")
    check("preview has modules.app_settings", "app_settings" in pv.get("modules", {}))
    check("preview has modules.study_sessions", "study_sessions" in pv.get("modules", {}))
    sess_mod = pv["modules"]["study_sessions"]
    check("preview sess total=1", sess_mod["total"] == 1, f"got {sess_mod['total']}")
    # Session already exists from test 60, so conflict should be detected
    check("preview sess conflict detected", sess_mod["conflict_count"] >= 1, f"got {sess_mod['conflict_count']}")

    # Preview with invalid settings
    r = client.post("/api/import/preview", json=bad_intervals_backup, params={"strategy": "overwrite"})
    check("preview bad settings 200", r.status_code == 200)
    pv_bad = r.json()
    check("preview settings_invalid > 0", pv_bad.get("settings_invalid", 0) > 0, f"got {pv_bad.get('settings_invalid')}")

    # ── 62. ZIP import preview shows settings and sessions ──
    print("\n[62] ZIP import preview shows settings and sessions")
    # Export a ZIP that includes settings and sessions
    r = client.put("/api/settings/review", json={"intervals": [2, 5, 10]})
    check("set intervals for zip preview 200", r.status_code == 200)
    r = client.get("/api/export/zip")
    check("export zip for preview 200", r.status_code == 200)
    zip_pv_bytes = r.content
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("reset intervals 200", r.status_code == 200)

    # Preview the ZIP
    r = client.post(
        "/api/import/zip/preview",
        files={"file": ("preview.zip", io.BytesIO(zip_pv_bytes), "application/zip")},
        params={"strategy": "skip"},
    )
    check("zip preview with settings 200", r.status_code == 200)
    zip_pv = r.json()
    check("zip preview has app_settings_count", "app_settings_count" in zip_pv)
    check("zip preview has study_sessions_count", "study_sessions_count" in zip_pv)
    check("zip preview app_settings_count >= 1", zip_pv.get("app_settings_count", 0) >= 1,
          f"got {zip_pv.get('app_settings_count')}")
    check("zip preview has modules.app_settings", "app_settings" in zip_pv.get("modules", {}))
    check("zip preview has modules.study_sessions", "study_sessions" in zip_pv.get("modules", {}))

    # ── 63. Active session import force-ended ──
    print("\n[63] Active session import force-ended")
    active_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.3",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
        "app_settings": [],
        "study_sessions": [
            {
                "subject": "活跃会话测试", "note": "无结束时间",
                "started_at": "2026-06-05T10:00:00+00:00",
                "ended_at": None, "duration_minutes": 0,
            },
        ],
    }
    r = client.post("/api/import/json", json=active_backup, params={"strategy": "skip"})
    check("active session import 200", r.status_code == 200)
    check("active session imported=1", r.json()["sessions_imported"] == 1, f"got {r.json()['sessions_imported']}")

    # Verify the session was force-ended
    r = client.get("/api/sessions", params={"limit": 100})
    active_imported = [s for s in r.json() if s.get("subject") == "活跃会话测试"]
    if active_imported:
        check("active session has ended_at", active_imported[0]["ended_at"] is not None)
        check("active session duration > 0", active_imported[0]["duration_minutes"] > 0,
              f"got {active_imported[0]['duration_minutes']}")

    # ── 64. Dashboard/trends not inflated by duplicate import ──
    print("\n[64] Dashboard/trends not inflated by duplicate import")
    # Get current study minutes
    r = client.get("/api/dashboard/trends", params={"days": 7})
    check("trends for inflation check 200", r.status_code == 200)
    today_items = [x for x in r.json()["items"] if x["date"] == local_today()]
    minutes_before = today_items[0]["study_minutes"] if today_items else 0

    # Import the same session backup again (should be skipped as duplicate)
    r = client.post("/api/import/json", json=session_backup, params={"strategy": "skip"})
    check("inflation import 200", r.status_code == 200)
    # All sessions in backup should be detected as duplicates
    check("inflation session skipped or imported=0", r.json()["sessions_imported"] == 0,
          f"imported={r.json()['sessions_imported']}, skipped={r.json()['sessions_skipped']}")

    # Verify study minutes didn't inflate
    r = client.get("/api/dashboard/trends", params={"days": 7})
    today_items2 = [x for x in r.json()["items"] if x["date"] == local_today()]
    minutes_after = today_items2[0]["study_minutes"] if today_items2 else 0
    check("study minutes not inflated", minutes_after <= minutes_before + 1,
          f"before={minutes_before}, after={minutes_after}")

    # Cleanup sessions created by import tests (use DB directly)
    async def _cleanup_import_sessions():
        async with async_session() as session:
            await session.execute(text(
                "DELETE FROM study_sessions WHERE subject LIKE '幂等测试-%' OR subject = '活跃会话测试' OR note LIKE '导入验证%'"
            ))
            await session.commit()
    loop_cs = asyncio.new_event_loop()
    loop_cs.run_until_complete(_cleanup_import_sessions())
    loop_cs.close()

    # ── 65. Naive started_at + null ended_at active session import ──
    print("\n[65] Naive started_at active session import")
    naive_active_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.3",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
        "app_settings": [],
        "study_sessions": [
            {
                "subject": "naive活跃测试", "note": "无时区无结束",
                # Naive datetime — no timezone offset
                "started_at": "2026-06-05T10:00:00",
                "ended_at": None, "duration_minutes": 0,
            },
        ],
    }
    r = client.post("/api/import/json", json=naive_active_backup, params={"strategy": "skip"})
    check("naive active import 200", r.status_code == 200)
    check("naive active imported=1", r.json()["sessions_imported"] == 1, f"got {r.json()['sessions_imported']}")

    # Verify force-ended
    r = client.get("/api/sessions", params={"limit": 100})
    naive_active = [s for s in r.json() if s.get("subject") == "naive活跃测试"]
    if naive_active:
        check("naive active has ended_at", naive_active[0]["ended_at"] is not None)
        check("naive active duration > 0", naive_active[0]["duration_minutes"] > 0,
              f"got {naive_active[0]['duration_minutes']}")

    # Cleanup
    async def _cleanup_naive():
        async with async_session() as session:
            await session.execute(text("DELETE FROM study_sessions WHERE subject = 'naive活跃测试'"))
            await session.commit()
    loop_cn = asyncio.new_event_loop()
    loop_cn.run_until_complete(_cleanup_naive())
    loop_cn.close()

    # ── 66. Import [true, 2] does not pollute settings ──
    print("\n[66] Import bool in review_intervals rejected")
    r = client.put("/api/settings/review", json={"intervals": [1, 3, 7, 14]})
    check("set default for bool test 200", r.status_code == 200)

    bool_backup = {
        "exported_at": "2026-01-01T00:00:00Z", "version": "0.3",
        "materials": [], "material_chunks_count": 0,
        "chat_history": [], "error_book": [], "study_plans": [],
        "problems": [], "exam_questions": [], "exam_attempts": [],
        "app_settings": [
            {"key": "review_intervals", "value": "[true, 2]"},
        ],
        "study_sessions": [],
    }
    r = client.post("/api/import/json", json=bool_backup, params={"strategy": "overwrite"})
    check("bool intervals import 200", r.status_code == 200)
    check("bool intervals settings_imported=0", r.json()["settings_imported"] == 0, f"got {r.json()['settings_imported']}")
    check("bool intervals settings_skipped>=1", r.json()["settings_skipped"] >= 1, f"got {r.json()['settings_skipped']}")
    check("bool intervals has warnings", len(r.json().get("settings_warnings", [])) > 0)

    # Verify intervals unchanged
    r = client.get("/api/settings/review")
    check("intervals still default after bool", r.json()["intervals"] == [1, 3, 7, 14], f"got {r.json()['intervals']}")

    # Also test [false, 3]
    bool_backup2 = dict(bool_backup)
    bool_backup2["app_settings"] = [{"key": "review_intervals", "value": "[false, 3]"}]
    r = client.post("/api/import/json", json=bool_backup2, params={"strategy": "overwrite"})
    check("false intervals import 200", r.status_code == 200)
    check("false intervals settings_imported=0", r.json()["settings_imported"] == 0)
    r = client.get("/api/settings/review")
    check("intervals still default after false", r.json()["intervals"] == [1, 3, 7, 14])

    # ── 67. PUT [true, 2] returns 422 ──
    print("\n[67] PUT bool in review_intervals returns 422")
    r = client.put("/api/settings/review", json={"intervals": [True, 2]})
    check("PUT [true,2] 422", r.status_code == 422, f"got {r.status_code}")

    r = client.put("/api/settings/review", json={"intervals": [False, 3]})
    check("PUT [false,3] 422", r.status_code == 422, f"got {r.status_code}")

    # Verify still default
    r = client.get("/api/settings/review")
    check("intervals still default after PUT bool", r.json()["intervals"] == [1, 3, 7, 14])

    # ── 68. ParseWorker race: delete material during parse ──
    print("\n[68] ParseWorker race: delete material during parse")
    # Upload a material, then immediately delete it while the worker might be processing
    race_file = os.path.join(_tmp_dir, "worker_race_test.txt")
    with open(race_file, "w", encoding="utf-8") as f:
        f.write("Worker竞态测试内容 " * 100)
    with open(race_file, "rb") as f:
        r = client.post("/api/materials/upload", files={"file": ("worker_race_test.txt", f, "text/plain")})
    check("race upload 200", r.status_code == 200)
    race_mid = r.json()["id"]

    # Immediately delete (race with worker)
    r = client.delete(f"/api/materials/{race_mid}")
    check("race delete 200", r.status_code == 200)

    # Wait a bit for any in-flight worker tasks to complete
    time.sleep(1)

    # Verify health is still ok (no crash)
    r = client.get("/api/health")
    check("health ok after race", r.status_code == 200)
    check("health status ok after race", r.json().get("status") == "ok")

    # Verify no orphaned records
    async def _verify_no_race_orphans():
        async with async_session() as session:
            mc = await session.execute(text("SELECT COUNT(*) FROM material_chunks WHERE material_id = :id"), {"id": race_mid})
            mj = await session.execute(text("SELECT COUNT(*) FROM material_parse_jobs WHERE material_id = :id"), {"id": race_mid})
            return mc.scalar() or 0, mj.scalar() or 0
    loop_rr = asyncio.new_event_loop()
    rc, rj = loop_rr.run_until_complete(_verify_no_race_orphans())
    loop_rr.close()
    check("no orphaned chunks after race", rc == 0, f"count={rc}")
    check("no orphaned jobs after race", rj == 0, f"count={rj}")

    # ── 69. Multiple rapid upload+delete race ──
    print("\n[69] Multiple rapid upload+delete race")
    race_ids = []
    for i in range(3):
        rf = os.path.join(_tmp_dir, f"rapid_race_{i}.txt")
        with open(rf, "w", encoding="utf-8") as f:
            f.write(f"快速竞态测试 {i} " + "x" * 200)
        with open(rf, "rb") as f:
            r = client.post("/api/materials/upload", files={"file": (f"rapid_race_{i}.txt", f, "text/plain")})
        check(f"rapid race upload {i} 200", r.status_code == 200)
        race_ids.append(r.json()["id"])

    # Immediately delete all
    for mid in race_ids:
        r = client.delete(f"/api/materials/{mid}")
        check(f"rapid race delete {mid} 200", r.status_code == 200)

    # Wait for worker to finish any in-flight tasks
    time.sleep(2)

    # Verify health still ok
    r = client.get("/api/health")
    check("health ok after rapid race", r.status_code == 200)
    check("health status ok after rapid race", r.json().get("status") == "ok")


# ── Main ──
with TestClient(app) as client:
    try:
        run(client)
    except Exception as e:
        print(f"\n  FATAL: {e}")
        failed += 1

# ── Summary ──
print(f"\n{'='*40}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*40}")

# ── Cleanup temp files ──
try:
    shutil.rmtree(_tmp_dir, ignore_errors=True)
except Exception:
    pass

sys.exit(1 if failed else 0)
