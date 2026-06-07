"""GET/PUT /api/settings/app — persisted .env-backed config.

Contract:
  GET  → persisted config only (no runtime state like ocr_available)
  PUT  → atomic .env write, cache clear, return confirmed values

Runtime state (ocr_available, database health, etc.) lives in /api/health only.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.env_store import write_env_updates, read_app_settings_dict

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AppSettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    clear_api_key: bool = False


@router.get("/app")
async def read_app_settings():
    return read_app_settings_dict()


@router.put("/app")
async def update_app_settings(body: AppSettingsUpdate):
    # ── Mutual exclusion: clear_api_key + openai_api_key ──
    if body.clear_api_key and body.openai_api_key is not None:
        raise HTTPException(
            422,
            "clear_api_key 和 openai_api_key 不能同时使用。"
            "请只选一个：要么传 openai_api_key 设置新值，要么传 clear_api_key=true 清空。",
        )

    updates: dict[str, str | None] = {}

    if body.clear_api_key:
        updates["OPENAI_API_KEY"] = ""
    elif body.openai_api_key is not None:
        updates["OPENAI_API_KEY"] = body.openai_api_key.strip()

    if body.openai_base_url is not None:
        url = body.openai_base_url.strip().rstrip("/")
        if not url:
            raise HTTPException(422, "API 地址不能为空")
        updates["OPENAI_BASE_URL"] = url

    if body.openai_model is not None:
        model = body.openai_model.strip()
        if not model:
            raise HTTPException(422, "模型名称不能为空")
        updates["OPENAI_MODEL"] = model

    if not updates:
        raise HTTPException(422, "没有要更新的字段")

    # Atomic write + cache clear
    write_env_updates(updates)

    # Read back confirmed values
    confirmed = read_app_settings_dict()
    return {
        "ok": True,
        **confirmed,
        "note": "设置已保存。当前进程已生效，其他进程需重启。",
        "updated_keys": list(updates.keys()),
    }
