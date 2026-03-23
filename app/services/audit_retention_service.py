"""审计日志数据保留策略服务"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete

from app.models.tables import AuditLog
from app.core.config import settings


class AuditRetentionService:
    """审计日志数据保留策略服务"""

    # 默认保留天数
    DEFAULT_RETENTION_DAYS = 90

    # 归档保留天数（比标准保留更长）
    ARCHIVE_RETENTION_DAYS = 365

    # 归档目录
    ARCHIVE_DIR = "archives/audit_logs"

    def __init__(self, retention_days: int = None, archive_enabled: bool = False):
        """
        初始化保留策略服务

        Args:
            retention_days: 保留天数（默认90天）
            archive_enabled: 是否启用归档
        """
        self.retention_days = retention_days or self.DEFAULT_RETENTION_DAYS
        self.archive_enabled = archive_enabled

        # 创建归档目录
        if self.archive_enabled:
            os.makedirs(self.ARCHIVE_DIR, exist_ok=True)

    async def cleanup_expired_logs(self, db: AsyncSession) -> Dict[str, Any]:
        """
        清理过期的审计日志

        Args:
            db: 数据库会话

        Returns:
            清理统计信息
        """
        # 计算截止日期
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        # 统计要删除的记录数
        count_query = select(func.count()).select_from(AuditLog).where(
            AuditLog.created_at < cutoff_date
        )
        count_result = await db.execute(count_query)
        total_to_delete = count_result.scalar()

        if total_to_delete == 0:
            return {
                "retention_days": self.retention_days,
                "cutoff_date": cutoff_date,
                "deleted_count": 0,
                "archived_count": 0,
            }

        # 分批删除（避免长时间锁表）
        batch_size = 1000
        deleted_count = 0
        archived_count = 0

        while True:
            # 获取一批记录
            query = select(AuditLog).where(
                AuditLog.created_at < cutoff_date
            ).limit(batch_size)

            result = await db.execute(query)
            batch = result.scalars().all()

            if not batch:
                break

            # 删除记录
            for log in batch:
                await db.delete(log)
                deleted_count += 1

            # 提交批次
            await db.commit()

            print(f"Deleted batch: {deleted_count}/{total_to_delete}")

        return {
            "retention_days": self.retention_days,
            "cutoff_date": cutoff_date,
            "deleted_count": deleted_count,
            "archived_count": archived_count,
        }

    async def archive_old_logs(self, db: AsyncSession) -> Dict[str, Any]:
        """
        归档旧的审计日志

        Args:
            db: 数据库会话

        Returns:
            归档统计信息
        """
        if not self.archive_enabled:
            return {
                "message": "Archive is disabled",
                "archived_count": 0,
            }

        # 计算归档截止日期（保留天数的一半）
        cutoff_date = datetime.now() - timedelta(days=self.retention_days // 2)

        # TODO: 实现归档逻辑
        # 1. 查询要归档的记录
        # 2. 导出到文件
        # 3. 从数据库删除记录

        return {
            "retention_days": self.retention_days,
            "cutoff_date": cutoff_date,
            "archived_count": 0,
            "archive_path": self.ARCHIVE_DIR,
        }

    async def get_retention_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """
        获取保留统计信息

        Args:
            db: 数据库会话

        Returns:
            统计信息
        """
        now = datetime.now()

        # 总记录数
        total_result = await db.execute(select(func.count()).select_from(AuditLog))
        total = total_result.scalar()

        # 活跃记录数（未过期）
        cutoff_date = now - timedelta(days=self.retention_days)
        active_result = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.created_at >= cutoff_date
            )
        )
        active = active_result.scalar()

        # 过期记录数
        expired = total - active

        # 按年龄统计
        stats = {
            "retention_days": self.retention_days,
            "archive_enabled": self.archive_enabled,
            "total_records": total,
            "active_records": active,
            "expired_records": expired,
            "cutoff_date": cutoff_date,
            "by_age": {
                "last_7_days": 0,
                "last_30_days": 0,
                "last_90_days": 0,
                "older_than_90_days": 0,
            },
        }

        # 按年龄段统计
        for days, key in [(7, "last_7_days"), (30, "last_30_days"), (90, "last_90_days")]:
            date_threshold = now - timedelta(days=days)
            result = await db.execute(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.created_at >= date_threshold
                )
            )
            stats["by_age"][key] = result.scalar()

        stats["by_age"]["older_than_90_days"] = total - stats["by_age"]["last_90_days"]

        return stats

    async def set_retention_policy(
        self,
        db: AsyncSession,
        retention_days: int,
        archive_enabled: bool = False,
    ) -> Dict[str, Any]:
        """
        设置保留策略

        Args:
            db: 数据库会话
            retention_days: 保留天数
            archive_enabled: 是否启用归档

        Returns:
            设置结果
        """
        # 验证参数
        if retention_days < 30:
            raise ValueError("Retention days must be at least 30")

        if retention_days > 3650:  # 最多10年
            raise ValueError("Retention days cannot exceed 3650")

        # 更新策略
        self.retention_days = retention_days
        self.archive_enabled = archive_enabled

        # 保存到配置（如果需要持久化）
        # TODO: 实现策略持久化

        return {
            "retention_days": retention_days,
            "archive_enabled": archive_enabled,
            "message": "Retention policy updated",
        }


# 创建全局保留策略服务实例
default_retention_service = AuditRetentionService()


# 定时任务函数
async def run_retention_cleanup_task():
    """
    运行数据保留清理任务（定时调用）

    示例：每天凌晨2点执行
    """
    from app.db.database import async_session_maker

    async with async_session_maker() as db:
        service = AuditRetentionService()
        stats = await service.cleanup_expired_logs(db)
        print(f"Retention cleanup completed: {stats}")
        return stats
