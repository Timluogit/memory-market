"""自动遗忘服务

实现记忆的自动失效机制：
- 基于时间的失效（TTL检查）
- 基于事件的失效（信息覆盖）
- 批量清理过期数据
- 智能失效策略
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tables import (
    UserProfile, ProfileFact, Memory, ProfileChange,
    UserDynamicContext
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class AutoForgetService:
    """自动遗忘服务

    负责管理和执行记忆的自动失效策略
    """

    def __init__(self):
        """初始化自动遗忘服务"""
        self.enabled = settings.AUTO_FORGET_ENABLED
        self.schedule_minutes = settings.AUTO_FORGET_SCHEDULE_MINUTES
        self.batch_size = settings.AUTO_FORGET_BATCH_SIZE
        self.default_ttl_days = settings.AUTO_FORGET_DEFAULT_TTL_DAYS

        # TTL配置（按事实类型）
        self.ttl_config = {
            "personal": settings.TTL_PERSONAL,
            "preference": settings.TTL_PREFERENCE,
            "habit": settings.TTL_HABIT,
            "skill": settings.TTL_SKILL,
            "interest": settings.TTL_INTEREST,
        }

    async def check_expired_memories(
        self,
        db: AsyncSession,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """检查过期的记忆

        Args:
            db: 数据库会话
            limit: 限制返回数量

        Returns:
            过期记忆列表
        """
        if not self.enabled:
            logger.info("Auto-forget is disabled, skipping check")
            return []

        limit = limit or self.batch_size

        # 查询过期记忆
        now = datetime.now()
        stmt = (
            select(Memory)
            .where(
                and_(
                    Memory.is_active == True,
                    Memory.expiry_time.isnot(None),
                    Memory.expiry_time <= now
                )
            )
            .limit(limit)
        )

        result = await db.execute(stmt)
        expired_memories = result.scalars().all()

        logger.info(f"Found {len(expired_memories)} expired memories")

        return [
            {
                "memory_id": m.memory_id,
                "title": m.title,
                "expiry_time": m.expiry_time,
                "seller_agent_id": m.seller_agent_id
            }
            for m in expired_memories
        ]

    async def check_expired_facts(
        self,
        db: AsyncSession,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """检查过期的事实

        Args:
            db: 数据库会话
            limit: 限制返回数量

        Returns:
            过期事实列表
        """
        if not self.enabled:
            return []

        limit = limit or self.batch_size

        # 查询过期事实
        now = datetime.now()
        stmt = (
            select(ProfileFact)
            .where(
                and_(
                    ProfileFact.is_valid == True,
                    ProfileFact.expires_at.isnot(None),
                    ProfileFact.expires_at <= now
                )
            )
            .limit(limit)
        )

        result = await db.execute(stmt)
        expired_facts = result.scalars().all()

        logger.info(f"Found {len(expired_facts)} expired facts")

        return [
            {
                "fact_id": f.fact_id,
                "agent_id": f.agent_id,
                "fact_type": f.fact_type,
                "fact_key": f.fact_key,
                "expires_at": f.expires_at
            }
            for f in expired_facts
        ]

    async def expire_memories(
        self,
        db: AsyncSession,
        memory_ids: List[str]
    ) -> int:
        """过期记忆（标记为失效）

        Args:
            db: 数据库会话
            memory_ids: 记忆ID列表

        Returns:
            过期的记忆数量
        """
        if not memory_ids:
            return 0

        now = datetime.now()

        # 批量更新记忆状态
        stmt = (
            update(Memory)
            .where(
                and_(
                    Memory.memory_id.in_(memory_ids),
                    Memory.is_active == True
                )
            )
            .values(is_active=False, updated_at=now)
        )

        result = await db.execute(stmt)
        expired_count = result.rowcount
        await db.commit()

        logger.info(f"Expired {expired_count} memories")

        return expired_count

    async def expire_facts(
        self,
        db: AsyncSession,
        fact_ids: List[str]
    ) -> int:
        """过期事实（标记为失效）

        Args:
            db: 数据库会话
            fact_ids: 事实ID列表

        Returns:
            过期的事实数量
        """
        if not fact_ids:
            return 0

        now = datetime.now()

        # 批量更新事实状态
        stmt = (
            update(ProfileFact)
            .where(
                and_(
                    ProfileFact.fact_id.in_(fact_ids),
                    ProfileFact.is_valid == True
                )
            )
            .values(
                is_valid=False,
                updated_at=now
            )
        )

        result = await db.execute(stmt)
        expired_count = result.rowcount
        await db.commit()

        # 记录变更
        await self._log_fact_changes(db, fact_ids, "expired")

        logger.info(f"Expired {expired_count} facts")

        return expired_count

    async def _log_fact_changes(
        self,
        db: AsyncSession,
        fact_ids: List[str],
        change_type: str
    ):
        """记录事实变更

        Args:
            db: 数据库会话
            fact_ids: 事实ID列表
            change_type: 变更类型
        """
        now = datetime.now()

        # 查询事实详情
        stmt = (
            select(ProfileFact)
            .where(ProfileFact.fact_id.in_(fact_ids))
        )

        result = await db.execute(stmt)
        facts = result.scalars().all()

        # 批量插入变更记录
        changes = []
        for fact in facts:
            change = ProfileChange(
                profile_id=fact.profile_id,
                agent_id=fact.agent_id,
                change_type=change_type,
                field_name=fact.fact_key,
                old_value=fact.fact_value,
                new_value=None,
                source="auto_forget",
                change_reason=f"Fact expired at {fact.expires_at}",
                created_at=now
            )
            changes.append(change)

        if changes:
            db.add_all(changes)
            await db.commit()

    async def override_fact(
        self,
        db: AsyncSession,
        agent_id: str,
        fact_type: str,
        fact_key: str,
        new_value: any,
        confidence: float = 0.8
    ) -> Tuple[Optional[ProfileFact], Optional[ProfileFact]]:
        """覆盖事实（事件失效）

        Args:
            db: 数据库会话
            agent_id: 用户ID
            fact_type: 事实类型
            fact_key: 事实键
            new_value: 新值
            confidence: 置信度

        Returns:
            (新事实, 旧事实)
        """
        # 查询现有事实
        stmt = (
            select(ProfileFact)
            .where(
                and_(
                    ProfileFact.agent_id == agent_id,
                    ProfileFact.fact_type == fact_type,
                    ProfileFact.fact_key == fact_key,
                    ProfileFact.is_valid == True
                )
            )
            .options(selectinload(ProfileFact.profile))
        )

        result = await db.execute(stmt)
        old_fact = result.scalar_one_or_none()

        if old_fact:
            # 标记旧事实为失效
            old_fact.is_valid = False
            old_fact.updated_at = datetime.now()

            # 记录变更
            change = ProfileChange(
                profile_id=old_fact.profile_id,
                agent_id=agent_id,
                change_type="expired",
                field_name=fact_key,
                old_value=old_fact.fact_value,
                new_value=new_value,
                source="auto_forget",
                change_reason=f"Overridden by new fact with confidence {confidence}",
                created_at=datetime.now()
            )
            db.add(change)

        # 获取或创建用户画像
        profile_stmt = (
            select(UserProfile)
            .where(UserProfile.agent_id == agent_id)
        )
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(agent_id=agent_id)
            db.add(profile)
            await db.flush()

        # 计算TTL
        ttl_days = self.ttl_config.get(fact_type, self.default_ttl_days)
        expires_at = datetime.now() + timedelta(days=ttl_days)

        # 创建新事实
        new_fact = ProfileFact(
            profile_id=profile.profile_id,
            agent_id=agent_id,
            fact_type=fact_type,
            fact_key=fact_key,
            fact_value=new_value,
            confidence=confidence,
            source="manual",
            expires_at=expires_at,
            is_valid=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_fact)

        await db.commit()

        logger.info(
            f"Overridden fact: {agent_id}/{fact_type}/{fact_key} "
            f"(old: {old_fact.fact_value if old_fact else None} -> new: {new_value})"
        )

        return new_fact, old_fact

    async def set_memory_ttl(
        self,
        db: AsyncSession,
        memory_id: str,
        ttl_days: int
    ) -> Optional[Memory]:
        """设置记忆TTL

        Args:
            db: 数据库会话
            memory_id: 记忆ID
            ttl_days: 生存时间（天）

        Returns:
            更新后的记忆对象
        """
        # 查询记忆
        stmt = (
            select(Memory)
            .where(Memory.memory_id == memory_id)
        )

        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()

        if not memory:
            logger.warning(f"Memory not found: {memory_id}")
            return None

        # 计算过期时间
        expiry_time = datetime.now() + timedelta(days=ttl_days)

        # 更新记忆
        memory.ttl_days = ttl_days
        memory.expiry_time = expiry_time
        memory.updated_at = datetime.now()

        await db.commit()
        await db.refresh(memory)

        logger.info(
            f"Set TTL for memory {memory_id}: {ttl_days} days "
            f"(expires at {expiry_time})"
        )

        return memory

    async def auto_expire_memories(
        self,
        db: AsyncSession
    ) -> Dict[str, int]:
        """自动过期记忆

        Args:
            db: 数据库会话

        Returns:
            统计信息
        """
        stats = {
            "checked": 0,
            "expired_memories": 0,
            "expired_facts": 0,
            "errors": 0
        }

        if not self.enabled:
            return stats

        try:
            # 检查过期记忆
            expired_memories = await self.check_expired_memories(db)
            stats["checked"] += len(expired_memories)

            if expired_memories:
                memory_ids = [m["memory_id"] for m in expired_memories]
                stats["expired_memories"] = await self.expire_memories(db, memory_ids)

            # 检查过期事实
            expired_facts = await self.check_expired_facts(db)
            stats["checked"] += len(expired_facts)

            if expired_facts:
                fact_ids = [f["fact_id"] for f in expired_facts]
                stats["expired_facts"] = await self.expire_facts(db, fact_ids)

            logger.info(
                f"Auto-expire completed: checked={stats['checked']}, "
                f"expired_memories={stats['expired_memories']}, "
                f"expired_facts={stats['expired_facts']}"
            )

        except Exception as e:
            logger.error(f"Error during auto-expire: {e}")
            stats["errors"] += 1

        return stats

    async def get_stats(
        self,
        db: AsyncSession
    ) -> Dict[str, int]:
        """获取自动遗忘统计信息

        Args:
            db: 数据库会话

        Returns:
            统计信息
        """
        now = datetime.now()

        # 统计过期记忆
        expired_memories_stmt = (
            select(func.count(Memory.memory_id))
            .where(
                and_(
                    Memory.is_active == True,
                    Memory.expiry_time.isnot(None),
                    Memory.expiry_time <= now
                )
            )
        )
        expired_memories_result = await db.execute(expired_memories_stmt)
        expired_memories_count = expired_memories_result.scalar() or 0

        # 统计过期事实
        expired_facts_stmt = (
            select(func.count(ProfileFact.fact_id))
            .where(
                and_(
                    ProfileFact.is_valid == True,
                    ProfileFact.expires_at.isnot(None),
                    ProfileFact.expires_at <= now
                )
            )
        )
        expired_facts_result = await db.execute(expired_facts_stmt)
        expired_facts_count = expired_facts_result.scalar() or 0

        # 统计即将过期的记忆（未来7天内）
        near_expiry_memories_stmt = (
            select(func.count(Memory.memory_id))
            .where(
                and_(
                    Memory.is_active == True,
                    Memory.expiry_time.isnot(None),
                    Memory.expiry_time > now,
                    Memory.expiry_time <= now + timedelta(days=7)
                )
            )
        )
        near_expiry_memories_result = await db.execute(near_expiry_memories_stmt)
        near_expiry_memories_count = near_expiry_memories_result.scalar() or 0

        # 统计即将过期的事实
        near_expiry_facts_stmt = (
            select(func.count(ProfileFact.fact_id))
            .where(
                and_(
                    ProfileFact.is_valid == True,
                    ProfileFact.expires_at.isnot(None),
                    ProfileFact.expires_at > now,
                    ProfileFact.expires_at <= now + timedelta(days=7)
                )
            )
        )
        near_expiry_facts_result = await db.execute(near_expiry_facts_stmt)
        near_expiry_facts_count = near_expiry_facts_result.scalar() or 0

        return {
            "expired_memories": expired_memories_count,
            "expired_facts": expired_facts_count,
            "near_expiry_memories": near_expiry_memories_count,
            "near_expiry_facts": near_expiry_facts_count,
            "enabled": self.enabled,
            "default_ttl_days": self.default_ttl_days,
        }


# 全局单例
_auto_forget_service: Optional[AutoForgetService] = None


def get_auto_forget_service() -> AutoForgetService:
    """获取自动遗忘服务单例

    Returns:
        自动遗忘服务实例
    """
    global _auto_forget_service
    if _auto_forget_service is None:
        _auto_forget_service = AutoForgetService()
    return _auto_forget_service
