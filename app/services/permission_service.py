"""权限服务 - 细粒度权限控制"""
import json
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tables import (
    Agent, Permission, Role, RolePermission, UserPermission,
    ResourcePermission, PermissionCache, PermissionAuditLog
)
from app.cache.redis_client import get_redis_client


class PermissionService:
    """权限服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = get_redis_client()

    async def has_permission(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        check_cache: bool = True
    ) -> bool:
        """
        检查用户是否拥有指定权限

        Args:
            agent_id: 用户ID
            permission_code: 权限代码
            resource_type: 资源类型（用于资源级权限检查）
            resource_id: 资源ID（用于资源级权限检查）
            check_cache: 是否检查缓存

        Returns:
            bool: 是否拥有权限
        """
        import time
        start_time = time.time()

        # 1. 先检查用户级拒绝权限（拒绝优先级最高）
        user_denied = await self._check_user_deny(agent_id, permission_code)
        if user_denied:
            await self._log_permission_check(
                agent_id=agent_id,
                permission_code=permission_code,
                resource_type=resource_type,
                resource_id=resource_id,
                status="forbidden",
                reason="user_deny",
                duration_ms=int((time.time() - start_time) * 1000)
            )
            return False

        # 2. 检查用户级允许权限
        user_allowed = await self._check_user_allow(agent_id, permission_code)
        if user_allowed:
            # 如果有资源限制，需要进一步检查
            if resource_type or resource_id:
                return await self._check_resource_scope(agent_id, permission_code, resource_type, resource_id)
            return True

        # 3. 检查角色权限
        role_allowed = await self._check_role_permissions(agent_id, permission_code)
        if role_allowed:
            # 如果有资源限制，需要进一步检查
            if resource_type or resource_id:
                return await self._check_resource_scope(agent_id, permission_code, resource_type, resource_id)
            return True

        # 4. 检查资源级权限
        if resource_type and resource_id:
            resource_allowed = await self._check_resource_permission(
                agent_id=agent_id,
                permission_code=permission_code,
                resource_type=resource_type,
                resource_id=resource_id
            )
            if resource_allowed:
                await self._log_permission_check(
                    agent_id=agent_id,
                    permission_code=permission_code,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status="success",
                    reason="resource_permission",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                return True

        # 没有权限
        await self._log_permission_check(
            agent_id=agent_id,
            permission_code=permission_code,
            resource_type=resource_type,
            resource_id=resource_id,
            status="forbidden",
            reason="no_permission",
            duration_ms=int((time.time() - start_time) * 1000)
        )
        return False

    async def _check_user_deny(self, agent_id: str, permission_code: str) -> bool:
        """检查用户级拒绝权限"""
        query = select(UserPermission).where(
            and_(
                UserPermission.agent_id == agent_id,
                UserPermission.permission_id.in_(
                    select(Permission.permission_id).where(Permission.code == permission_code)
                ),
                UserPermission.grant_type == "deny",
                or_(
                    UserPermission.expires_at.is_(None),
                    UserPermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _check_user_allow(self, agent_id: str, permission_code: str) -> bool:
        """检查用户级允许权限"""
        query = select(UserPermission).where(
            and_(
                UserPermission.agent_id == agent_id,
                UserPermission.permission_id.in_(
                    select(Permission.permission_id).where(Permission.code == permission_code)
                ),
                UserPermission.grant_type == "allow",
                or_(
                    UserPermission.expires_at.is_(None),
                    UserPermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _check_role_permissions(self, agent_id: str, permission_code: str) -> bool:
        """检查角色权限（包括角色继承）"""
        # 1. 获取用户的所有角色（直接+间接）
        user_roles = await self._get_user_roles(agent_id)
        if not user_roles:
            return False

        role_ids = [role.role_id for role in user_roles]

        # 2. 检查这些角色是否有该权限
        query = select(RolePermission).where(
            and_(
                RolePermission.role_id.in_(role_ids),
                RolePermission.permission_id.in_(
                    select(Permission.permission_id).where(Permission.code == permission_code)
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _get_user_roles(self, agent_id: str) -> List[Role]:
        """获取用户的所有角色（包括继承的角色）"""
        # 查询用户的直接角色
        query = select(Role).options(selectinload(Role.inherit_from)).where(
            and_(
                Role.role_id.in_(
                    select(RolePermission.role_id).where(
                        RolePermission.permission_id.in_(
                            select(Permission.permission_id).where(
                                Permission.code == "user.role"  # 假设有一个标记用户角色的权限
                            )
                        )
                    )
                ),
                Role.is_active == True
            )
        )
        # 这里需要简化，实际应该有一个 user_roles 表
        # 暂时返回空列表
        return []

    async def _check_resource_scope(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> bool:
        """检查资源范围限制"""
        # 查询用户权限的范围限制
        query = select(UserPermission).where(
            and_(
                UserPermission.agent_id == agent_id,
                UserPermission.permission_id.in_(
                    select(Permission.permission_id).where(Permission.code == permission_code)
                ),
                UserPermission.scope.isnot(None),
                or_(
                    UserPermission.expires_at.is_(None),
                    UserPermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        user_perms = result.scalars().all()

        for perm in user_perms:
            scope = perm.scope or {}

            # 如果没有指定资源，检查是否有任何范围限制
            if not resource_type or not resource_id:
                if not scope:  # 空范围 = 全部资源
                    return True
                continue

            # 检查资源ID是否在允许范围内
            if resource_type == "memory":
                allowed_ids = scope.get("memory_ids", [])
                if not allowed_ids or resource_id in allowed_ids:
                    return True
            elif resource_type == "team":
                allowed_ids = scope.get("team_ids", [])
                if not allowed_ids or resource_id in allowed_ids:
                    return True

        return False

    async def _check_resource_permission(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """检查资源级权限"""
        # 1. 检查直接授予用户的资源权限
        query = select(ResourcePermission).where(
            and_(
                ResourcePermission.resource_type == resource_type,
                ResourcePermission.resource_id == resource_id,
                ResourcePermission.agent_id == agent_id,
                ResourcePermission.permission_code == permission_code,
                ResourcePermission.grant_type == "allow",
                or_(
                    ResourcePermission.expires_at.is_(None),
                    ResourcePermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            return True

        # 2. 检查授予角色的资源权限
        user_roles = await self._get_user_roles(agent_id)
        if user_roles:
            role_ids = [role.role_id for role in user_roles]
            query = select(ResourcePermission).where(
                and_(
                    ResourcePermission.resource_type == resource_type,
                    ResourcePermission.resource_id == resource_id,
                    ResourcePermission.role_id.in_(role_ids),
                    ResourcePermission.permission_code == permission_code,
                    ResourcePermission.grant_type == "allow",
                    or_(
                        ResourcePermission.expires_at.is_(None),
                        ResourcePermission.expires_at > datetime.now()
                    )
                )
            )
            result = await self.db.execute(query)
            if result.scalar_one_or_none():
                return True

        return False

    async def grant_permission(
        self,
        agent_id: str,
        permission_code: str,
        grant_type: str = "allow",
        scope: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        actor_agent_id: Optional[str] = None
    ) -> bool:
        """
        授予用户权限

        Args:
            agent_id: 目标用户ID
            permission_code: 权限代码
            grant_type: 授权类型（allow/deny）
            scope: 权限范围
            expires_at: 过期时间
            actor_agent_id: 操作者ID

        Returns:
            bool: 是否成功
        """
        # 1. 查询权限是否存在
        query = select(Permission).where(Permission.code == permission_code)
        result = await self.db.execute(query)
        permission = result.scalar_one_or_none()
        if not permission:
            return False

        # 2. 检查是否已存在相同的授权
        existing_query = select(UserPermission).where(
            and_(
                UserPermission.agent_id == agent_id,
                UserPermission.permission_id == permission.permission_id,
                UserPermission.grant_type == grant_type
            )
        )
        result = await self.db.execute(existing_query)
        existing = result.scalar_one_or_none()
        if existing:
            # 更新现有授权
            existing.scope = scope
            existing.expires_at = expires_at
        else:
            # 创建新授权
            new_perm = UserPermission(
                agent_id=agent_id,
                permission_id=permission.permission_id,
                grant_type=grant_type,
                scope=scope,
                expires_at=expires_at,
                created_by_agent_id=actor_agent_id
            )
            self.db.add(new_perm)

        # 3. 清除权限缓存
        await self._clear_permission_cache(agent_id)

        # 4. 记录审计日志
        await self._log_permission_grant(
            actor_agent_id=actor_agent_id,
            target_agent_id=agent_id,
            permission_code=permission_code,
            grant_type=grant_type,
            scope=scope
        )

        await self.db.commit()
        return True

    async def revoke_permission(
        self,
        agent_id: str,
        permission_code: str,
        actor_agent_id: Optional[str] = None
    ) -> bool:
        """
        撤销用户权限

        Args:
            agent_id: 目标用户ID
            permission_code: 权限代码
            actor_agent_id: 操作者ID

        Returns:
            bool: 是否成功
        """
        # 1. 查询权限ID
        query = select(Permission).where(Permission.code == permission_code)
        result = await self.db.execute(query)
        permission = result.scalar_one_or_none()
        if not permission:
            return False

        # 2. 删除用户权限
        delete_query = select(UserPermission).where(
            and_(
                UserPermission.agent_id == agent_id,
                UserPermission.permission_id == permission.permission_id
            )
        )
        result = await self.db.execute(delete_query)
        user_perm = result.scalar_one_or_none()
        if user_perm:
            await self.db.delete(user_perm)

        # 3. 清除权限缓存
        await self._clear_permission_cache(agent_id)

        # 4. 记录审计日志
        await self._log_permission_revoke(
            actor_agent_id=actor_agent_id,
            target_agent_id=agent_id,
            permission_code=permission_code
        )

        await self.db.commit()
        return True

    async def grant_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        permission_code: str,
        agent_id: Optional[str] = None,
        role_id: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        actor_agent_id: Optional[str] = None
    ) -> bool:
        """
        授予资源权限

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            permission_code: 权限代码
            agent_id: 授权给哪个用户（可选）
            role_id: 授权给哪个角色（可选）
            conditions: 权限条件
            expires_at: 过期时间
            actor_agent_id: 操作者ID

        Returns:
            bool: 是否成功
        """
        if not agent_id and not role_id:
            return False

        # 1. 检查是否已存在相同的授权
        query = select(ResourcePermission).where(
            and_(
                ResourcePermission.resource_type == resource_type,
                ResourcePermission.resource_id == resource_id,
                ResourcePermission.permission_code == permission_code,
                ResourcePermission.agent_id == agent_id,
                ResourcePermission.role_id == role_id
            )
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            # 更新现有授权
            existing.conditions = conditions
            existing.expires_at = expires_at
        else:
            # 创建新授权
            new_perm = ResourcePermission(
                resource_type=resource_type,
                resource_id=resource_id,
                permission_code=permission_code,
                agent_id=agent_id,
                role_id=role_id,
                grant_type="allow",
                conditions=conditions,
                expires_at=expires_at,
                created_by_agent_id=actor_agent_id
            )
            self.db.add(new_perm)

        # 2. 清除相关缓存
        if agent_id:
            await self._clear_permission_cache(agent_id)
        if role_id:
            # 清除拥有该角色的所有用户的缓存
            await self._clear_role_cache(role_id)

        # 3. 记录审计日志
        await self._log_resource_permission_grant(
            actor_agent_id=actor_agent_id,
            resource_type=resource_type,
            resource_id=resource_id,
            permission_code=permission_code,
            agent_id=agent_id,
            role_id=role_id,
            conditions=conditions
        )

        await self.db.commit()
        return True

    async def revoke_resource_permission(
        self,
        resource_type: str,
        resource_id: str,
        permission_code: str,
        agent_id: Optional[str] = None,
        role_id: Optional[str] = None,
        actor_agent_id: Optional[str] = None
    ) -> bool:
        """
        撤销资源权限

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            permission_code: 权限代码
            agent_id: 用户ID（可选）
            role_id: 角色ID（可选）
            actor_agent_id: 操作者ID

        Returns:
            bool: 是否成功
        """
        # 1. 删除资源权限
        query = select(ResourcePermission).where(
            and_(
                ResourcePermission.resource_type == resource_type,
                ResourcePermission.resource_id == resource_id,
                ResourcePermission.permission_code == permission_code,
                ResourcePermission.agent_id == agent_id,
                ResourcePermission.role_id == role_id
            )
        )
        result = await self.db.execute(query)
        resource_perm = result.scalar_one_or_none()
        if resource_perm:
            await self.db.delete(resource_perm)

            # 2. 清除相关缓存
            if resource_perm.agent_id:
                await self._clear_permission_cache(resource_perm.agent_id)
            if resource_perm.role_id:
                await self._clear_role_cache(resource_perm.role_id)

            # 3. 记录审计日志
            await self._log_resource_permission_revoke(
                actor_agent_id=actor_agent_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_code=permission_code,
                agent_id=agent_id,
                role_id=role_id
            )

        await self.db.commit()
        return True

    async def get_user_permissions(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有权限

        Args:
            agent_id: 用户ID

        Returns:
            List[Dict]: 权限列表
        """
        # 1. 获取用户直接授予的权限
        user_perm_query = select(UserPermission).options(
            selectinload(UserPermission.permission)
        ).where(
            and_(
                UserPermission.agent_id == agent_id,
                or_(
                    UserPermission.expires_at.is_(None),
                    UserPermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(user_perm_query)
        user_perms = result.scalars().all()

        # 2. 获取角色权限
        role_perms = await self._get_role_permissions(agent_id)

        # 3. 合并权限
        permissions = []
        for perm in user_perms:
            permissions.append({
                "type": "user",
                "grant_type": perm.grant_type,
                "code": perm.permission.code,
                "name": perm.permission.name,
                "category": perm.permission.category,
                "scope": perm.scope,
                "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
            })

        for perm in role_perms:
            permissions.append({
                "type": "role",
                "code": perm.permission.code,
                "name": perm.permission.name,
                "category": perm.permission.category,
                "role_name": perm.role.name
            })

        return permissions

    async def _get_role_permissions(self, agent_id: str) -> List[RolePermission]:
        """获取用户的角色权限"""
        # 这里简化处理，实际应该有一个 user_roles 表
        return []

    async def _clear_permission_cache(self, agent_id: str):
        """清除用户权限缓存"""
        cache_key = f"permissions:{agent_id}"
        if self.redis:
            await self.redis.delete(cache_key)

    async def _clear_role_cache(self, role_id: str):
        """清除角色权限缓存"""
        cache_key = f"role_permissions:{role_id}"
        if self.redis:
            await self.redis.delete(cache_key)

    # ========== 审计日志 ==========

    async def _log_permission_check(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        status: str,
        reason: str,
        duration_ms: int
    ):
        """记录权限检查日志"""
        log = PermissionAuditLog(
            actor_agent_id=agent_id,
            actor_name="",  # 需要查询用户名
            action_type="check",
            action_category="permission",
            target_type="agent",
            target_id=agent_id,
            permission_code=permission_code,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            extra_data={"reason": reason, "duration_ms": duration_ms}
        )
        self.db.add(log)

    async def _log_permission_grant(
        self,
        actor_agent_id: Optional[str],
        target_agent_id: str,
        permission_code: str,
        grant_type: str,
        scope: Optional[Dict[str, Any]]
    ):
        """记录权限授予日志"""
        log = PermissionAuditLog(
            actor_agent_id=actor_agent_id,
            actor_name="",
            action_type="grant",
            action_category="permission",
            target_type="agent",
            target_id=target_agent_id,
            permission_code=permission_code,
            status="success",
            extra_data={"grant_type": grant_type, "scope": scope}
        )
        self.db.add(log)

    async def _log_permission_revoke(
        self,
        actor_agent_id: Optional[str],
        target_agent_id: str,
        permission_code: str
    ):
        """记录权限撤销日志"""
        log = PermissionAuditLog(
            actor_agent_id=actor_agent_id,
            actor_name="",
            action_type="revoke",
            action_category="permission",
            target_type="agent",
            target_id=target_agent_id,
            permission_code=permission_code,
            status="success"
        )
        self.db.add(log)

    async def _log_resource_permission_grant(
        self,
        actor_agent_id: Optional[str],
        resource_type: str,
        resource_id: str,
        permission_code: str,
        agent_id: Optional[str],
        role_id: Optional[str],
        conditions: Optional[Dict[str, Any]]
    ):
        """记录资源权限授予日志"""
        log = PermissionAuditLog(
            actor_agent_id=actor_agent_id,
            actor_name="",
            action_type="grant",
            action_category="resource",
            target_type=resource_type,
            target_id=resource_id,
            permission_code=permission_code,
            extra_data={
                "agent_id": agent_id,
                "role_id": role_id,
                "conditions": conditions
            },
            status="success"
        )
        self.db.add(log)

    async def _log_resource_permission_revoke(
        self,
        actor_agent_id: Optional[str],
        resource_type: str,
        resource_id: str,
        permission_code: str,
        agent_id: Optional[str],
        role_id: Optional[str]
    ):
        """记录资源权限撤销日志"""
        log = PermissionAuditLog(
            actor_agent_id=actor_agent_id,
            actor_name="",
            action_type="revoke",
            action_category="resource",
            target_type=resource_type,
            target_id=resource_id,
            permission_code=permission_code,
            extra_data={"agent_id": agent_id, "role_id": role_id},
            status="success"
        )
        self.db.add(log)
