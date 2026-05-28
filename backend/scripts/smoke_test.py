"""本地冒烟测试：覆盖非 AI 主链路，不依赖 API Key。
用法：cd backend && .venv\\Scripts\\python.exe scripts\\smoke_test.py

环境变量 CORS_ORIGINS 可配置 CORS 允许来源，默认 localhost:5173。"""
import json
import os
import sys

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

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import async_session

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

    r = client.get(f"/api/materials/{ocr_material_id}")
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
    check("has version", data.get("version") == "0.2")
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

    # Verify preview did NOT write to DB
    r_before = client.get("/api/exam/questions")
    count_before = len(r_before.json())

    print("\n[19c] POST /api/import/json (first import)")
    r = client.post("/api/import/json", json=backup)
    check("import 200", r.status_code == 200)
    result = r.json()
    ins = result["inserted"]
    skp = result["skipped"]
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

    # Search with type filter
    r = client.get("/api/search", params={"q": "卷积定理", "types": "errors,exam", "limit": 20})
    check("filtered search 200", r.status_code == 200)
    filtered_types = {x["type"] for x in r.json()["results"]}
    check("filtered only errors+exam", filtered_types <= {"error", "exam"}, f"types={filtered_types}")

    # Verify search result IDs are correct entity IDs
    r = client.get("/api/search", params={"q": "卷积定理", "limit": 50})
    sr = r.json()
    for item in sr["results"]:
        if item["type"] == "material":
            check("material id is entity id", item["id"] == search_mat_id, f"got {item['id']}, expected {search_mat_id}")
        elif item["type"] == "error":
            check("error id is entity id", item["id"] == search_err_id, f"got {item['id']}, expected {search_err_id}")
        elif item["type"] == "plan":
            check("plan id is entity id", item["id"] == search_plan_id, f"got {item['id']}, expected {search_plan_id}")
        elif item["type"] == "exam":
            check("exam id is entity id", item["id"] == search_eq_id, f"got {item['id']}, expected {search_eq_id}")

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
