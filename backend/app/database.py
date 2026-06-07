import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.config import get_settings, _BACKEND_DIR


def _ensure_db_dir(db_url: str) -> None:
    """Ensure the parent directory of the SQLite database file exists.

    Expects an already-normalized URL (from config's field_validator).
    Skips in-memory and non-sqlite URLs.
    """
    try:
        url = make_url(db_url)
    except Exception:
        return
    if not url.drivername.startswith("sqlite"):
        return
    db_path = url.database
    if not db_path or db_path == ":memory:":
        return
    p = Path(db_path)
    if not p.is_absolute():
        # Defensive fallback — should not happen after config normalization
        p = (_BACKEND_DIR / p).resolve()
    db_dir = p.parent
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)


settings = get_settings()
# settings.database_url is already normalized by config's field_validator
_ensure_db_dir(settings.database_url)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create FTS5 virtual table for chunk-based search
        await conn.execute(
            text("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(content, chunk_id UNINDEXED, material_id UNINDEXED)")
        )
        # Lightweight migration: add stored_filename to materials if missing
        result = await conn.execute(text("PRAGMA table_info(materials)"))
        columns = [row[1] for row in result.fetchall()]
        if "stored_filename" not in columns:
            await conn.execute(text("ALTER TABLE materials ADD COLUMN stored_filename VARCHAR(500) DEFAULT ''"))
        # Fix NULL values from old data (idempotent)
        await conn.execute(text("UPDATE materials SET stored_filename = '' WHERE stored_filename IS NULL"))
        # Lightweight migration: add review_count to error_book if missing
        result = await conn.execute(text("PRAGMA table_info(error_book)"))
        columns = [row[1] for row in result.fetchall()]
        if "review_count" not in columns:
            await conn.execute(text("ALTER TABLE error_book ADD COLUMN review_count INTEGER DEFAULT 0"))
        await conn.execute(text("UPDATE error_book SET review_count = 0 WHERE review_count IS NULL"))
        # Lightweight migration: add conversation_id to chat_history if missing
        result = await conn.execute(text("PRAGMA table_info(chat_history)"))
        columns = [row[1] for row in result.fetchall()]
        if "conversation_id" not in columns:
            await conn.execute(text("ALTER TABLE chat_history ADD COLUMN conversation_id VARCHAR(50) DEFAULT ''"))
        await conn.execute(text("UPDATE chat_history SET conversation_id = '' WHERE conversation_id IS NULL"))
        # Lightweight migration: add status/error_message to materials if missing
        result = await conn.execute(text("PRAGMA table_info(materials)"))
        columns = [row[1] for row in result.fetchall()]
        if "status" not in columns:
            await conn.execute(text("ALTER TABLE materials ADD COLUMN status VARCHAR(20) DEFAULT 'ready'"))
        await conn.execute(text("UPDATE materials SET status = 'ready' WHERE status IS NULL"))
        if "error_message" not in columns:
            await conn.execute(text("ALTER TABLE materials ADD COLUMN error_message TEXT DEFAULT ''"))
        await conn.execute(text("UPDATE materials SET error_message = '' WHERE error_message IS NULL"))
        # Lightweight migration: add progress fields to material_parse_jobs if missing
        result = await conn.execute(text("PRAGMA table_info(material_parse_jobs)"))
        columns = [row[1] for row in result.fetchall()]
        if "progress_current" not in columns:
            await conn.execute(text("ALTER TABLE material_parse_jobs ADD COLUMN progress_current INTEGER DEFAULT 0"))
        if "progress_total" not in columns:
            await conn.execute(text("ALTER TABLE material_parse_jobs ADD COLUMN progress_total INTEGER DEFAULT 0"))
        if "progress_message" not in columns:
            await conn.execute(text("ALTER TABLE material_parse_jobs ADD COLUMN progress_message VARCHAR(200) DEFAULT ''"))
        # Create operation_logs table for backup/import/cleanup audit trail
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS operation_logs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "operation_type VARCHAR(30) NOT NULL,"
            "file_type VARCHAR(10) DEFAULT '',"
            "strategy VARCHAR(20) DEFAULT '',"
            "result_summary TEXT DEFAULT '',"
            "error_message TEXT DEFAULT '',"
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
