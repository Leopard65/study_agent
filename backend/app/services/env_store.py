"""Atomic .env file read/write with cache-clearing side effects.

All .env mutation goes through here so routers don't touch the filesystem directly.
"""

import os
import tempfile
from pathlib import Path
from app.config import get_settings, is_ai_configured, _BACKEND_DIR

_ENV_FILE = _BACKEND_DIR / ".env"


def read_env_lines() -> list[str]:
    """Read .env file lines, or empty list if missing."""
    if not _ENV_FILE.exists():
        return []
    return _ENV_FILE.read_text(encoding="utf-8").splitlines()


def parse_env_dict(lines: list[str]) -> dict[str, str]:
    """Parse env lines into {KEY: value} dict. Skips comments and blanks."""
    result: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            result[key.strip()] = value.strip()
    return result


def apply_updates(lines: list[str], updates: dict[str, str | None]) -> list[str]:
    """Apply updates to env lines. Returns new lines.
    Keys with value=None are removed. Preserves comments and ordering."""
    new_lines: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                seen.add(key)
                val = updates[key]
                if val is not None:
                    new_lines.append(f"{key}={val}")
                continue  # skip if val is None (delete)
        new_lines.append(line)
    # Append new keys not already in file
    for key, val in updates.items():
        if key not in seen and val is not None:
            new_lines.append(f"{key}={val}")
    return new_lines


def atomic_write_env(lines: list[str]) -> None:
    """Write lines to .env atomically: write to temp file, then os.replace().
    Preserves the original file if the write fails."""
    content = "\n".join(lines) + "\n"
    # Write to a temp file in the same directory (same filesystem for atomic replace)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_BACKEND_DIR), prefix=".env.tmp.", suffix=".tmp"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(_ENV_FILE))
    except Exception:
        # Clean up temp file on failure; original .env is untouched
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_env_updates(updates: dict[str, str | None]) -> None:
    """Read → merge → atomic write → clear settings cache.
    This is the single entry point for .env mutation."""
    lines = read_env_lines()
    new_lines = apply_updates(lines, updates)
    atomic_write_env(new_lines)
    get_settings.cache_clear()


def read_app_settings_dict() -> dict:
    """Return persisted config dict from .env. No runtime state."""
    settings = get_settings()
    return {
        "ai_configured": is_ai_configured(),
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "ocr_enabled": settings.ocr_enabled,
    }
