"""搜索日志中间件 - 记录搜索操作和用户点击"""
import asyncio
import json
import logging
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.tables import SearchLog, SearchClick, SearchABTest, Agent, Memory
from app.models.schemas import SearchLogCreate, SearchClickCreate

logger = logging.getLogger(__name__)


class SearchLogMiddleware:
    """搜索日志中间件

    异步记录搜索日志，避免影响搜索性能
    """

    def __init__(self, max_queue_size: int = 1000):
        """初始化日志中间件

        Args:
            max_queue_size: 最大队列大小
        """
        self.max_queue_size = max_queue_size
        self.log_queue = asyncio.Queue(maxsize=max_queue_size)
        self.is_running = False
        self.worker_task = None

    async def start(self):
        """启动日志写入worker"""
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._log_writer())
            logger.info("Search log middleware started")

    async def stop(self):
        """停止日志写入worker"""
        if self.is_running:
            self.is_running = False
            # 等待队列清空
            await self.log_queue.join()
            # 取消worker
            if self.worker_task:
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
            logger.info("Search log middleware stopped")

    async def _log_writer(self):
        """日志写入worker（后台任务）"""
        while self.is_running or not self.log_queue.empty():
            try:
                # 从队列获取日志任务
                task = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
                if task is None:
                    break

                db, log_type, data = task

                try:
                    # 根据类型写入不同的日志
                    if log_type == "search":
                        await self._write_search_log(db, data)
                    elif log_type == "click":
                        await self._write_click_log(db, data)

                except Exception as e:
                    logger.error(f"Failed to write {log_type} log: {e}", exc_info=True)
                finally:
                    self.log_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Log writer error: {e}", exc_info=True)

    async def log_search(
        self,
        db: AsyncSession,
        agent_id: str,
        query: str,
        search_type: str,
        filters: dict,
        results: list,
        response_time_ms: int,
        scores: Optional[dict] = None,
        session_id: Optional[str] = None
    ):
        """记录搜索日志（异步）"""
        try:
            # 获取A/B测试分组（如果有活跃的测试）
            ab_test_id, ab_test_group = await self._get_ab_test_group(db, agent_id, query)

            # 准备日志数据
            log_data = SearchLogCreate(
                query=query,
                search_type=search_type,
                category=filters.get("category"),
                platform=filters.get("platform"),
                format_type=filters.get("format_type"),
                min_score=filters.get("min_score"),
                max_price=filters.get("max_price"),
                sort_by=filters.get("sort_by"),
                result_count=len(results),
                top_result_id=results[0].memory_id if results else None,
                response_time_ms=response_time_ms,
                semantic_score=scores.get("semantic") if scores else None,
                keyword_score=scores.get("keyword") if scores else None,
                ab_test_id=ab_test_id,
                ab_test_group=ab_test_group,
                session_id=session_id
            )

            # 放入队列（非阻塞）
            try:
                self.log_queue.put_nowait((db, "search", log_data))
            except asyncio.QueueFull:
                logger.warning("Search log queue full, dropping log")

            # 返回搜索日志ID（用于后续点击追踪）
            return log_data

        except Exception as e:
            logger.error(f"Failed to queue search log: {e}", exc_info=True)
            return None

    async def log_click(
        self,
        db: AsyncSession,
        agent_id: str,
        search_log_id: Optional[str],
        memory_id: str,
        position: int,
        click_type: str = "detail"
    ):
        """记录点击日志（异步）"""
        try:
            # 如果没有提供search_log_id，尝试查找最近的搜索
            if not search_log_id:
                search_log_id = await self._get_recent_search_log(db, agent_id, memory_id)

            if not search_log_id:
                logger.warning(f"No recent search log found for agent {agent_id} and memory {memory_id}")
                return None

            # 获取A/B测试信息
            ab_test_id, ab_test_group = await self._get_ab_test_from_search_log(db, search_log_id)

            # 准备点击数据
            click_data = SearchClickCreate(
                search_log_id=search_log_id,
                memory_id=memory_id,
                position=position,
                click_type=click_type,
                ab_test_id=ab_test_id,
                ab_test_group=ab_test_group
            )

            # 放入队列
            try:
                self.log_queue.put_nowait((db, "click", click_data))
            except asyncio.QueueFull:
                logger.warning("Search click queue full, dropping log")

            return click_data

        except Exception as e:
            logger.error(f"Failed to queue click log: {e}", exc_info=True)
            return None

    async def _write_search_log(self, db: AsyncSession, log_data: SearchLogCreate):
        """写入搜索日志到数据库"""
        log_entry = SearchLog(
            agent_id=log_data.agent_id,
            query=log_data.query,
            search_type=log_data.search_type,
            category=log_data.category,
            platform=log_data.platform,
            format_type=log_data.format_type,
            min_score=log_data.min_score,
            max_price=log_data.max_price,
            sort_by=log_data.sort_by,
            result_count=log_data.result_count,
            top_result_id=log_data.top_result_id,
            response_time_ms=log_data.response_time_ms,
            semantic_score=log_data.semantic_score,
            keyword_score=log_data.keyword_score,
            ab_test_id=log_data.ab_test_id,
            ab_test_group=log_data.ab_test_group,
            session_id=log_data.session_id
        )

        db.add(log_entry)
        await db.commit()
        logger.debug(f"Search log written: {log_entry.log_id}")

    async def _write_click_log(self, db: AsyncSession, click_data: SearchClickCreate):
        """写入点击日志到数据库"""
        click_entry = SearchClick(
            search_log_id=click_data.search_log_id,
            memory_id=click_data.memory_id,
            position=click_data.position,
            agent_id=click_data.agent_id,
            click_type=click_data.click_type,
            ab_test_id=click_data.ab_test_id,
            ab_test_group=click_data.ab_test_group
        )

        db.add(click_entry)
        await db.commit()
        logger.debug(f"Search click written: {click_entry.click_id}")

    async def _get_ab_test_group(self, db: AsyncSession, agent_id: str, query: str) -> tuple[Optional[str], Optional[str]]:
        """获取A/B测试分组

        Args:
            db: 数据库会话
            agent_id: 用户ID
            query: 搜索查询

        Returns:
            (test_id, group)
        """
        now = datetime.utcnow()

        # 查找活跃的A/B测试
        result = await db.execute(
            select(SearchABTest).where(
                SearchABTest.status == "running",
                SearchABTest.start_at <= now,
                SearchABTest.end_at >= now
            ).order_by(SearchABTest.created_at.desc()).limit(1)
        )

        test = result.scalar_one_or_none()

        if not test:
            return None, None

        # 根据agent_id哈希值分配组（确保同一用户始终在同一组）
        import hashlib
        hash_val = int(hashlib.md5(f"{test.test_id}:{agent_id}".encode()).hexdigest(), 16)
        group_index = hash_val % 100  # 0-99

        # 根据split_ratio分配组
        cumulative = 0
        for group, ratio in test.split_ratio.items():
            cumulative += ratio * 100
            if group_index < cumulative:
                return test.test_id, group

        return None, None

    async def _get_recent_search_log(self, db: AsyncSession, agent_id: str, memory_id: str) -> Optional[str]:
        """获取最近的搜索日志ID"""
        # 查找该用户最近5分钟内包含此memory_id的搜索
        five_minutes_ago = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=5)

        result = await db.execute(
            select(SearchLog.log_id)
            .where(
                SearchLog.agent_id == agent_id,
                SearchLog.created_at >= five_minutes_ago
            )
            .order_by(SearchLog.created_at.desc())
            .limit(10)
        )

        logs = result.scalars().all()

        # 查找包含该memory_id的搜索
        for log_id in logs:
            # 检查搜索结果中是否包含该memory_id
            # 这里需要重新执行搜索来验证，为了简化，我们返回最近的log_id
            return log_id

        return None

    async def _get_ab_test_from_search_log(self, db: AsyncSession, search_log_id: str) -> tuple[Optional[str], Optional[str]]:
        """从搜索日志中获取A/B测试信息"""
        result = await db.execute(
            select(SearchLog.ab_test_id, SearchLog.ab_test_group)
            .where(SearchLog.log_id == search_log_id)
        )

        row = result.first()
        if row:
            return row.ab_test_id, row.ab_test_group

        return None, None


# 全局实例
search_log_middleware = SearchLogMiddleware()


async def get_search_log_middleware():
    """获取搜索日志中间件实例"""
    return search_log_middleware
