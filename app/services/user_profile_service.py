"""用户画像管理服务

提供用户画像的创建、查询、更新、删除等功能，支持 Redis 缓存优化
"""
from typing import Dict, List, Any, Optional
import json
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.tables import UserProfile, ProfileFact, UserDynamicContext, ProfileChange
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserProfileService:
    """用户画像管理服务

    提供 CRUD 操作和缓存优化
    """

    def __init__(self, redis_client=None):
        """初始化用户画像服务

        Args:
            redis_client: Redis 客户端（可选）
        """
        self.redis_client = redis_client
        self.cache_ttl = settings.PROFILE_CACHE_TTL
        self.enabled = settings.PROFILE_ENABLED

    async def get_profile(
        self,
        db: AsyncSession,
        agent_id: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """获取用户画像

        Args:
            db: 数据库会话
            agent_id: 用户ID
            use_cache: 是否使用缓存

        Returns:
            用户画像字典或 None
        """
        if not self.enabled:
            return None

        # 尝试从缓存获取
        cache_key = f"profile:{agent_id}"
        if use_cache and self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Profile cache hit for agent {agent_id}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Failed to get profile from cache: {e}")

        # 从数据库查询
        profile = await db.execute(
            select(UserProfile).options(
                selectinload(UserProfile.facts)
            ).where(UserProfile.agent_id == agent_id)
        )
        profile = profile.scalar_one_or_none()

        if not profile:
            return None

        # 构建画像字典
        profile_dict = await self._profile_to_dict(db, profile)

        # 写入缓存
        if use_cache and self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(profile_dict, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Failed to cache profile: {e}")

        return profile_dict

    async def create_or_update_profile(
        self,
        db: AsyncSession,
        agent_id: str,
        profile_data: Dict[str, Any],
        source: str = "manual"
    ) -> Dict[str, Any]:
        """创建或更新用户画像

        Args:
            db: 数据库会话
            agent_id: 用户ID
            profile_data: 画像数据
            source: 来源（manual/auto_extraction）

        Returns:
            更新后的画像字典
        """
        if not self.enabled:
            raise ValueError("Profile system is disabled")

        # 获取或创建画像
        profile = await db.execute(
            select(UserProfile).where(UserProfile.agent_id == agent_id)
        )
        profile = profile.scalar_one_or_none()

        is_new = False
        if not profile:
            profile = UserProfile(agent_id=agent_id)
            db.add(profile)
            await db.flush()
            is_new = True

        # 更新字段
        old_values = {}
        for field, value in profile_data.items():
            if hasattr(profile, field):
                old_value = getattr(profile, field)
                if old_value != value:
                    old_values[field] = old_value
                    setattr(profile, field, value)

                    # 记录变更
                    change = ProfileChange(
                        profile_id=profile.profile_id,
                        agent_id=agent_id,
                        change_type='created' if is_new else 'updated',
                        field_name=field,
                        old_value=old_value,
                        new_value=value,
                        source=source
                    )
                    db.add(change)

        profile.last_updated_at = datetime.now()
        await db.commit()

        # 清除缓存
        await self._invalidate_cache(agent_id)

        # 返回更新后的画像
        return await self.get_profile(db, agent_id, use_cache=False)

    async def get_facts(
        self,
        db: AsyncSession,
        agent_id: str,
        fact_type: Optional[str] = None,
        is_valid: bool = True
    ) -> List[Dict[str, Any]]:
        """获取画像事实列表

        Args:
            db: 数据库会话
            agent_id: 用户ID
            fact_type: 事实类型过滤
            is_valid: 是否只返回有效事实

        Returns:
            事实列表
        """
        query = select(ProfileFact).where(ProfileFact.agent_id == agent_id)

        if fact_type:
            query = query.where(ProfileFact.fact_type == fact_type)

        if is_valid:
            query = query.where(ProfileFact.is_valid == True)

        result = await db.execute(query)
        facts = result.scalars().all()

        return [
            {
                'fact_id': fact.fact_id,
                'fact_type': fact.fact_type,
                'fact_key': fact.fact_key,
                'fact_value': fact.fact_value,
                'confidence': fact.confidence,
                'source': fact.source,
                'source_reference': fact.source_reference,
                'expires_at': fact.expires_at.isoformat() if fact.expires_at else None,
                'created_at': fact.created_at.isoformat(),
                'is_valid': fact.is_valid
            }
            for fact in facts
        ]

    async def add_fact(
        self,
        db: AsyncSession,
        agent_id: str,
        fact_type: str,
        fact_key: str,
        fact_value: Any,
        confidence: float = 0.8,
        source: str = "manual"
    ) -> Dict[str, Any]:
        """手动添加画像事实

        Args:
            db: 数据库会话
            agent_id: 用户ID
            fact_type: 事实类型
            fact_key: 事实键
            fact_value: 事实值
            confidence: 置信度
            source: 来源

        Returns:
            添加的事实字典
        """
        if not self.enabled:
            raise ValueError("Profile system is disabled")

        # 获取或创建画像
        profile = await db.execute(
            select(UserProfile).where(UserProfile.agent_id == agent_id)
        )
        profile = profile.scalar_one_or_none()

        if not profile:
            profile = UserProfile(agent_id=agent_id)
            db.add(profile)
            await db.flush()

        # 检查是否已存在相同键的事实
        existing_fact = await db.execute(
            select(ProfileFact).where(
                and_(
                    ProfileFact.agent_id == agent_id,
                    ProfileFact.fact_key == fact_key,
                    ProfileFact.is_valid == True
                )
            )
        )
        existing_fact = existing_fact.scalar_one_or_none()

        old_value = None
        if existing_fact:
            old_value = existing_fact.fact_value
            existing_fact.is_valid = False

        # 创建新事实
        from datetime import timedelta
        new_fact = ProfileFact(
            profile_id=profile.profile_id,
            agent_id=agent_id,
            fact_type=fact_type,
            fact_key=fact_key,
            fact_value=fact_value,
            confidence=confidence,
            source=source,
            expires_at=datetime.now() + timedelta(days=settings.PROFILE_AUTO_FORGET_DAYS),
            is_valid=True
        )
        db.add(new_fact)

        # 记录变更
        change = ProfileChange(
            profile_id=profile.profile_id,
            agent_id=agent_id,
            change_type='updated' if old_value else 'created',
            field_name=fact_key,
            old_value=old_value,
            new_value=fact_value,
            source=source
        )
        db.add(change)

        # 更新画像时间
        profile.last_updated_at = datetime.now()
        await db.commit()

        # 清除缓存
        await self._invalidate_cache(agent_id)

        return {
            'fact_id': new_fact.fact_id,
            'fact_type': new_fact.fact_type,
            'fact_key': new_fact.fact_key,
            'fact_value': new_fact.fact_value,
            'confidence': new_fact.confidence,
            'created_at': new_fact.created_at.isoformat()
        }

    async def delete_fact(
        self,
        db: AsyncSession,
        agent_id: str,
        fact_id: str
    ) -> bool:
        """删除画像事实

        Args:
            db: 数据库会话
            agent_id: 用户ID
            fact_id: 事实ID

        Returns:
            是否成功删除
        """
        if not self.enabled:
            raise ValueError("Profile system is disabled")

        # 查找事实
        fact = await db.execute(
            select(ProfileFact).where(
                and_(
                    ProfileFact.fact_id == fact_id,
                    ProfileFact.agent_id == agent_id
                )
            )
        )
        fact = fact.scalar_one_or_none()

        if not fact:
            return False

        # 软删除（标记为无效）
        old_value = fact.fact_value
        fact.is_valid = False

        # 记录变更
        change = ProfileChange(
            profile_id=fact.profile_id,
            agent_id=agent_id,
            change_type='deleted',
            field_name=fact.fact_key,
            old_value=old_value,
            new_value=None,
            source='manual'
        )
        db.add(change)

        await db.commit()

        # 清除缓存
        await self._invalidate_cache(agent_id)

        return True

    async def get_changes(
        self,
        db: AsyncSession,
        agent_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取画像变更历史

        Args:
            db: 数据库会话
            agent_id: 用户ID
            limit: 返回数量限制

        Returns:
            变更历史列表
        """
        profile = await db.execute(
            select(UserProfile).where(UserProfile.agent_id == agent_id)
        )
        profile = profile.scalar_one_or_none()

        if not profile:
            return []

        # 查询变更历史
        result = await db.execute(
            select(ProfileChange)
            .where(ProfileChange.profile_id == profile.profile_id)
            .order_by(ProfileChange.created_at.desc())
            .limit(limit)
        )
        changes = result.scalars().all()

        return [
            {
                'change_id': change.change_id,
                'change_type': change.change_type,
                'field_name': change.field_name,
                'old_value': change.old_value,
                'new_value': change.new_value,
                'source': change.source,
                'source_reference': change.source_reference,
                'change_reason': change.change_reason,
                'created_at': change.created_at.isoformat()
            }
            for change in changes
        ]

    async def get_dynamic_context(
        self,
        db: AsyncSession,
        agent_id: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """获取用户动态上下文

        Args:
            db: 数据库会话
            agent_id: 用户ID
            use_cache: 是否使用缓存

        Returns:
            动态上下文字典或 None
        """
        if not self.enabled:
            return None

        # 尝试从缓存获取
        cache_key = f"context:{agent_id}"
        if use_cache and self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Context cache hit for agent {agent_id}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Failed to get context from cache: {e}")

        # 从数据库查询
        context = await db.execute(
            select(UserDynamicContext).where(
                UserDynamicContext.agent_id == agent_id
            )
        )
        context = context.scalar_one_or_none()

        if not context:
            return None

        # 构建上下文字典
        context_dict = {
            'agent_id': context.agent_id,
            'current_task': context.current_task,
            'current_project': context.current_project,
            'current_focus': context.current_focus,
            'work_state': context.work_state,
            'recent_activities': context.recent_activities,
            'last_session_id': context.last_session_id,
            'last_search_query': context.last_search_query,
            'last_interacted_memory': context.last_interacted_memory,
            'recommended_categories': context.recommended_categories,
            'suggested_topics': context.suggested_topics,
            'session_count_today': context.session_count_today,
            'search_count_today': context.search_count_today,
            'last_updated_at': context.last_updated_at.isoformat(),
            'created_at': context.created_at.isoformat()
        }

        # 写入缓存
        if use_cache and self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(context_dict, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Failed to cache context: {e}")

        return context_dict

    async def update_dynamic_context(
        self,
        db: AsyncSession,
        agent_id: str,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新用户动态上下文

        Args:
            db: 数据库会话
            agent_id: 用户ID
            context_data: 上下文数据

        Returns:
            更新后的上下文字典
        """
        if not self.enabled:
            raise ValueError("Profile system is disabled")

        # 获取或创建上下文
        context = await db.execute(
            select(UserDynamicContext).where(
                UserDynamicContext.agent_id == agent_id
            )
        )
        context = context.scalar_one_or_none()

        if not context:
            context = UserDynamicContext(agent_id=agent_id)
            db.add(context)

        # 更新字段
        for field, value in context_data.items():
            if hasattr(context, field):
                setattr(context, field, value)

        context.last_updated_at = datetime.now()
        await db.commit()

        # 清除缓存
        cache_key = f"context:{agent_id}"
        if self.redis_client:
            try:
                await self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Failed to invalidate context cache: {e}")

        return await self.get_dynamic_context(db, agent_id, use_cache=False)

    async def _profile_to_dict(
        self,
        db: AsyncSession,
        profile: UserProfile
    ) -> Dict[str, Any]:
        """将画像对象转换为字典

        Args:
            db: 数据库会话
            profile: 画像对象

        Returns:
            画像字典
        """
        # 获取有效事实
        facts_result = await db.execute(
            select(ProfileFact).where(
                and_(
                    ProfileFact.profile_id == profile.profile_id,
                    ProfileFact.is_valid == True
                )
            )
        )
        facts = facts_result.scalars().all()

        # 按类型分组事实
        facts_by_type = {}
        for fact in facts:
            if fact.fact_type not in facts_by_type:
                facts_by_type[fact.fact_type] = []
            facts_by_type[fact.fact_type].append({
                'fact_id': fact.fact_id,
                'fact_key': fact.fact_key,
                'fact_value': fact.fact_value,
                'confidence': fact.confidence,
                'source': fact.source,
                'expires_at': fact.expires_at.isoformat() if fact.expires_at else None,
                'created_at': fact.created_at.isoformat()
            })

        # 计算完整度
        total_fields = len(self.FIELD_TYPES)
        filled_fields = len(set(fact.fact_key for fact in facts))
        completeness_score = filled_fields / total_fields if total_fields > 0 else 0.0

        return {
            'profile_id': profile.profile_id,
            'agent_id': profile.agent_id,
            'real_name': profile.real_name,
            'job_title': profile.job_title,
            'company': profile.company,
            'location': profile.location,
            'timezone': profile.timezone,
            'language': profile.language,
            'editor': profile.editor,
            'theme': profile.theme,
            'ui_scale': profile.ui_scale,
            'work_hours': profile.work_hours,
            'work_days': profile.work_days,
            'preferred_command': profile.preferred_command,
            'skills': profile.skills,
            'tech_stack': profile.tech_stack,
            'interests': profile.interests,
            'research_areas': profile.research_areas,
            'facts': facts_by_type,
            'completeness_score': completeness_score,
            'confidence_score': profile.confidence_score,
            'last_updated_at': profile.last_updated_at.isoformat(),
            'created_at': profile.created_at.isoformat()
        }

    async def _invalidate_cache(self, agent_id: str):
        """清除用户缓存

        Args:
            agent_id: 用户ID
        """
        if not self.redis_client:
            return

        try:
            await self.redis_client.delete(f"profile:{agent_id}")
            await self.redis_client.delete(f"context:{agent_id}")
            logger.debug(f"Invalidated cache for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    @property
    def FIELD_TYPES(self):
        """支持的画像字段类型"""
        return {
            'personal': ['real_name', 'job_title', 'company', 'location', 'timezone'],
            'preference': ['language', 'editor', 'theme', 'ui_scale'],
            'habit': ['work_hours', 'work_days', 'preferred_command'],
            'skill': ['skills', 'tech_stack'],
            'interest': ['interests', 'research_areas']
        }


# 全局单例
_profile_service: Optional[UserProfileService] = None


def get_profile_service(redis_client=None) -> UserProfileService:
    """获取用户画像服务单例

    Args:
        redis_client: Redis 客户端（可选）

    Returns:
        用户画像服务实例
    """
    global _profile_service
    if _profile_service is None:
        _profile_service = UserProfileService(redis_client=redis_client)
    return _profile_service
