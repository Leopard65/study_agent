"""后台资料解析任务：提取文本、OCR fallback、分块索引。"""
import asyncio
import logging

from sqlalchemy import text

from app.database import async_session
from app.models import Material
from app.services.doc_parser import extract_text
from app.services.search import index_chunks, delete_chunks_for_material

logger = logging.getLogger(__name__)


async def process_material(material_id: int, stored_filename: str, file_path: str) -> None:
    """后台解析资料：更新 status、写入 content 和 chunks/FTS。"""
    async with async_session() as session:
        material = await session.get(Material, material_id)
        if not material:
            return
        material.status = "processing"
        await session.commit()

    try:
        # 在线程池中运行 CPU 密集的文本提取（含 OCR）
        loop = asyncio.get_running_loop()
        text_content = await loop.run_in_executor(None, extract_text, file_path)

        async with async_session() as session:
            material = await session.get(Material, material_id)
            if not material:
                return
            material.content = text_content
            # 先清理旧 chunks（重试场景）
            await delete_chunks_for_material(session, material_id)
            if text_content.strip():
                await index_chunks(session, material_id, text_content)
            material.status = "ready"
            material.error_message = ""
            await session.commit()
            logger.info("Material %d parsed successfully (%d chars)", material_id, len(text_content))
    except Exception as e:
        logger.exception("Failed to parse material %d", material_id)
        async with async_session() as session:
            material = await session.get(Material, material_id)
            if material:
                material.status = "failed"
                material.error_message = str(e)[:500]
                await session.commit()
