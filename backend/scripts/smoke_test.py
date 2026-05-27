"""本地冒烟测试：覆盖非 AI 主链路，不依赖 API Key。
用法：cd backend && .venv\\Scripts\\python.exe scripts\\smoke_test.py"""
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
    from datetime import date as _date, timedelta as _td
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("patch error 200", r.status_code == 200)
    err1 = r.json()
    check("error mastered=true", err1["mastered"] is True)
    check("review_count=1", err1.get("review_count") == 1)
    expected_date1 = (_date.today() + _td(days=1)).isoformat()
    check("next_review_date=tomorrow", err1.get("next_review_date") == expected_date1, f"got {err1.get('next_review_date')}")

    print("\n[10b] PATCH /api/errors/{id} (mastered=false)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": False})
    check("unmaster 200", r.status_code == 200)
    err2 = r.json()
    check("mastered=false", err2["mastered"] is False)
    check("review_count still 1", err2.get("review_count") == 1)
    expected_today = _date.today().isoformat()
    check("next_review_date=today", err2.get("next_review_date") == expected_today, f"got {err2.get('next_review_date')}")

    print("\n[10c] PATCH /api/errors/{id} (mastered=true, 2nd review)")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("re-master 200", r.status_code == 200)
    err3 = r.json()
    check("review_count=2", err3.get("review_count") == 2)
    expected_date2 = (_date.today() + _td(days=3)).isoformat()
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
    expected_date5 = (_date.today() + _td(days=14)).isoformat()
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
    for field in ("today_tasks", "today_completed", "total_materials", "total_errors", "unmastered_errors", "streak_days"):
        check(f"has {field}", field in dash)


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
