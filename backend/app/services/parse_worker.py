"""资料解析任务队列 worker：SQLite 持久化 + asyncio 并发控制。

设计要点：
- MaterialParseJob 表持久化任务状态，进程重启可恢复
- ParseWorker 单例：asyncio.Queue + Semaphore 控制并发
- 启动时恢复：processing → pending，然后拉取 pending 任务
- upload/retry 创建 job 后调用 worker.enqueue(material_id)
- 删除资料时 job 会被级联删除，worker 对已删除的记录安全退出
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import StaleDataError

from app.database import async_session
from app.models import Material, MaterialParseJob
from app.services.doc_parser import extract_text
from app.services.search import index_chunks, delete_chunks_for_material

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParseWorker:
    """单例解析 worker，管理并发和任务调度。"""

    def __init__(self, concurrency: int = 1):
        self._concurrency = max(1, concurrency)
        self._semaphore: asyncio.Semaphore | None = None
        self._queue: asyncio.Queue[int] | None = None  # material_id queue
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动 worker：恢复卡住的任务，开始消费队列。"""
        if self._running:
            return
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._queue = asyncio.Queue()
        self._running = True

        # 恢复：processing 状态的 job 视为中断，重置为 pending
        async with async_session() as session:
            await session.execute(
                update(MaterialParseJob)
                .where(MaterialParseJob.status == "processing")
                .values(status="pending", started_at=None, progress_current=0, progress_total=0, progress_message="")
            )
            # 同步 materials 表：processing → pending
            await session.execute(
                update(Material)
                .where(Material.status == "processing")
                .values(status="pending", error_message="")
            )
            await session.commit()

        # 拉取所有 pending jobs 入队
        async with async_session() as session:
            rows = await session.execute(
                select(MaterialParseJob.material_id)
                .where(MaterialParseJob.status == "pending")
                .order_by(MaterialParseJob.created_at)
            )
            for (mid,) in rows.fetchall():
                await self._queue.put(mid)

        self._task = asyncio.create_task(self._consume_loop())
        logger.info(
            "ParseWorker started (concurrency=%d, recovered %d pending jobs)",
            self._concurrency,
            self._queue.qsize(),
        )

    async def stop(self) -> None:
        """停止 worker（优雅关闭）。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, material_id: int) -> None:
        """将 material_id 加入解析队列。"""
        if self._queue is not None:
            await self._queue.put(material_id)
        else:
            # worker 未启动时直接创建任务（兼容测试场景）
            async def _safe_process():
                try:
                    await self._process_one(material_id)
                except Exception:
                    logger.exception("Unexpected error in enqueue for material %d", material_id)
            asyncio.create_task(_safe_process())

    async def _consume_loop(self) -> None:
        """持续从队列取任务并处理（受并发限制）。"""
        while self._running:
            try:
                material_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            # 在 semaphore 控制下并发处理
            asyncio.create_task(self._semaphore_wrap(material_id))

    async def _semaphore_wrap(self, material_id: int) -> None:
        try:
            async with self._semaphore:
                await self._process_one(material_id)
        except Exception:
            # Never let exceptions leak from fire-and-forget tasks
            logger.exception("Unexpected error in _semaphore_wrap for material %d", material_id)

    async def _update_progress(self, job_id: int, current: int, total: int, message: str) -> None:
        """更新 job 的进度字段（轻量，不改 status）。"""
        try:
            async with async_session() as session:
                job = await session.get(MaterialParseJob, job_id)
                if job and job.status == "processing":
                    job.progress_current = current
                    job.progress_total = total
                    job.progress_message = message
                    await session.commit()
        except (IntegrityError, InvalidRequestError):
            # Job was deleted (e.g. user deleted material) — safe to ignore
            pass

    async def _process_one(self, material_id: int) -> None:
        """处理单个 material 的解析任务。"""
        # 查找 pending job
        try:
            async with async_session() as session:
                job = (
                    await session.execute(
                        select(MaterialParseJob)
                        .where(
                            MaterialParseJob.material_id == material_id,
                            MaterialParseJob.status == "pending",
                        )
                        .order_by(MaterialParseJob.created_at.desc())
                        .limit(1)
                    )
                ).scalars().first()
                if not job:
                    return
                job_id_local = job.id
                job.status = "processing"
                job.started_at = _utcnow()
                job.attempts += 1
                job.progress_current = 0
                job.progress_total = 4  # 4 阶段：读取→提取→索引→完成
                job.progress_message = "等待中"
                material = await session.get(Material, material_id)
                if not material:
                    job.status = "failed"
                    job.error_message = "资料记录不存在"
                    job.progress_message = "失败：资料记录不存在"
                    job.finished_at = _utcnow()
                    await session.commit()
                    return
                material.status = "processing"
                file_path = material.stored_filename or ""
                await session.commit()
        except (StaleDataError, IntegrityError, InvalidRequestError):
            # Job or material was deleted between query and commit (race with user delete/cleanup)
            logger.info("Material %d or job disappeared before commit, skipping", material_id)
            return

        job_id = job_id_local

        # 构建完整文件路径
        from app.config import get_settings
        settings = get_settings()
        import os
        full_path = os.path.join(settings.upload_dir, file_path) if file_path else ""

        try:
            # 阶段 1：读取文件
            await self._update_progress(job_id, 1, 4, "正在读取文件")
            if not full_path or not os.path.isfile(full_path):
                raise FileNotFoundError(f"存储文件不存在: {file_path}")

            # 阶段 2：提取文本（可能含 OCR）
            await self._update_progress(job_id, 2, 4, "正在提取文本")
            loop = asyncio.get_running_loop()
            text_content = await loop.run_in_executor(None, extract_text, full_path)

            # 阶段 3：写入索引
            await self._update_progress(job_id, 3, 4, "正在写入索引")
            async with async_session() as session:
                material = await session.get(Material, material_id)
                if not material:
                    # Material was deleted while parsing — quiet exit
                    logger.info("Material %d deleted during parse, discarding result", material_id)
                    return
                material.content = text_content
                await delete_chunks_for_material(session, material_id)
                if text_content.strip():
                    await index_chunks(session, material_id, text_content)
                material.status = "ready"
                material.error_message = ""

                # 阶段 4：完成
                job = await session.get(MaterialParseJob, job_id)
                if job:
                    job.status = "done"
                    job.error_message = ""
                    job.progress_current = 4
                    job.progress_total = 4
                    job.progress_message = "已完成"
                    job.finished_at = _utcnow()

                await session.commit()
                logger.info("Material %d parsed (%d chars, attempt %d)", material_id, len(text_content), job.attempts if job else -1)

        except (IntegrityError, InvalidRequestError, StaleDataError):
            # Material/job was deleted during parse (user action) — quiet exit
            logger.info("Material %d or its parse job deleted during parse, skipping", material_id)
        except Exception as e:
            # Check if the material/job was deleted — if so, this is expected, not an error
            try:
                async with async_session() as session:
                    material = await session.get(Material, material_id)
                    job = await session.get(MaterialParseJob, job_id)
                    if not material and not job:
                        logger.info("Material %d deleted during parse (error path), skipping", material_id)
                        return
                    # Real error — mark as failed
                    if material:
                        material.status = "failed"
                        material.error_message = str(e)[:500]
                    if job:
                        job.status = "failed"
                        job.error_message = str(e)[:500]
                        job.progress_message = f"失败：{str(e)[:100]}"
                        job.finished_at = _utcnow()
                    await session.commit()
            except (IntegrityError, InvalidRequestError, StaleDataError):
                logger.info("Material %d deleted during parse error handling, skipping", material_id)
                return
            logger.exception("Failed to parse material %d", material_id)


# 模块级单例
_worker: ParseWorker | None = None


def get_worker() -> ParseWorker:
    global _worker
    if _worker is None:
        from app.config import get_settings
        _worker = ParseWorker(concurrency=get_settings().material_parse_concurrency)
    return _worker


async def start_worker() -> None:
    """启动 worker（在 app lifespan 中调用）。"""
    await get_worker().start()


async def stop_worker() -> None:
    """停止 worker。"""
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None


def reset_worker_for_testing() -> None:
    """测试用：重置单例，确保测试隔离。"""
    global _worker
    _worker = None
