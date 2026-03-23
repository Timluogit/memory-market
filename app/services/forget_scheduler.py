"""遗忘调度器

负责定时执行自动遗忘任务
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auto_forget_service import get_auto_forget_service
from app.db.database import async_session
from app.core.config import settings

logger = logging.getLogger(__name__)


class ForgetScheduler:
    """遗忘调度器

    定期检查和清理过期的记忆和事实
    """

    def __init__(self):
        """初始化遗忘调度器"""
        self.auto_forget_service = get_auto_forget_service()
        self.schedule_minutes = settings.AUTO_FORGET_SCHEDULE_MINUTES
        self.enabled = settings.AUTO_FORGET_ENABLED

        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动调度器"""
        if not self.enabled:
            logger.info("Forget scheduler is disabled, skipping start")
            return

        if self._running:
            logger.warning("Forget scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_schedule())
        logger.info(
            f"Forget scheduler started (interval: {self.schedule_minutes} minutes)"
        )

    async def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Forget scheduler stopped")

    async def _run_schedule(self):
        """运行调度循环"""
        while self._running:
            try:
                await self._execute_forget_task()

                # 等待下一次执行
                await asyncio.sleep(self.schedule_minutes * 60)

            except asyncio.CancelledError:
                logger.info("Forget scheduler task cancelled")
                break

            except Exception as e:
                logger.error(f"Error in forget scheduler: {e}")
                # 出错后等待一段时间再重试
                await asyncio.sleep(60)

    async def _execute_forget_task(self):
        """执行遗忘任务"""
        try:
            async with async_session() as db:
                stats = await self.auto_forget_service.auto_expire_memories(db)

                logger.info(
                    f"Forget task completed: checked={stats['checked']}, "
                    f"expired_memories={stats['expired_memories']}, "
                    f"expired_facts={stats['expired_facts']}"
                )

        except Exception as e:
            logger.error(f"Error executing forget task: {e}")

    async def manual_trigger(self) -> dict:
        """手动触发清理任务

        Returns:
            统计信息
        """
        try:
            async with async_session() as db:
                stats = await self.auto_forget_service.auto_expire_memories(db)
                return stats

        except Exception as e:
            logger.error(f"Error in manual trigger: {e}")
            return {
                "checked": 0,
                "expired_memories": 0,
                "expired_facts": 0,
                "errors": 1
            }

    def is_running(self) -> bool:
        """检查调度器是否正在运行

        Returns:
            是否正在运行
        """
        return self._running


# 全局单例
_forget_scheduler: Optional[ForgetScheduler] = None


def get_forget_scheduler() -> ForgetScheduler:
    """获取遗忘调度器单例

    Returns:
        遗忘调度器实例
    """
    global _forget_scheduler
    if _forget_scheduler is None:
        _forget_scheduler = ForgetScheduler()
    return _forget_scheduler
