from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

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
