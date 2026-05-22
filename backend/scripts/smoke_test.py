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

    # ── 3. Search material ──
    print("\n[3] POST /api/materials/search")
    r = client.post("/api/materials/search", json={"query": "冒烟测试", "limit": 10})
    check("search 200", r.status_code == 200)
    results = r.json()
    check("found at least 1 result", len(results) >= 1, f"got {len(results)}")
    check("result matches material_id", results[0]["material_id"] == material_id)

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

    print("\n[10] PATCH /api/errors/{id}")
    r = client.patch(f"/api/errors/{error_id}", json={"mastered": True})
    check("patch error 200", r.status_code == 200)
    check("error mastered=true", r.json()["mastered"] is True)

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
