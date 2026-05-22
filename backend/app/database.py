from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
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
            __import__("sqlalchemy").text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(content, chunk_id UNINDEXED, material_id UNINDEXED)"
            )
        )
        # Lightweight migration: add stored_filename to materials if missing
        result = await conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(materials)")
        )
        columns = [row[1] for row in result.fetchall()]
        if "stored_filename" not in columns:
            await conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE materials ADD COLUMN stored_filename VARCHAR(500) DEFAULT ''"
                )
            )
        # Fix NULL values from old data (idempotent)
        await conn.execute(
            __import__("sqlalchemy").text(
                "UPDATE materials SET stored_filename = '' WHERE stored_filename IS NULL"
            )
        )
