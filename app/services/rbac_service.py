"""
RBAC 服务 - 基于角色的访问控制扩展

支持：
- 角色继承（角色树）
- 资源级权限
- 操作级权限
- 条件访问控制
- 权限委派
"""
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tables import (
    Role, RolePermission, UserPermission, ResourcePermission,
    Permission, Agent, TeamMember, Team
)


class RBACService:
    """RBAC 服务 - 角色继承和细粒度权限控制"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 角色继承 ==========

    async def get_role_hierarchy(self, role_id: str) -> Dict[str, Any]:
        """
        获取角色的完整继承链

        Returns:
            Dict: 角色层级结构
        """
        role = await self._get_role(role_id)
        if not role:
            return {}

        hierarchy = {
            "role_id": role.role_id,
            "code": role.code,
            "name": role.name,
            "level": role.level,
            "parents": [],
            "children": [],
            "all_permissions": []
        }

        # 收集父角色
        visited = set()
        parents = await self._collect_parent_roles(role, visited)
        hierarchy["parents"] = [
            {"role_id": r.role_id, "code": r.code, "name": r.name, "level": r.level}
            for r in parents
        ]

        # 收集子角色
        visited = set()
        children = await self._collect_child_roles(role_id, visited)
        hierarchy["children"] = [
            {"role_id": r.role_id, "code": r.code, "name": r.name, "level": r.level}
            for r in children
        ]

        # 收集所有权限（包括继承的）
        all_permissions = await self._get_all_role_permissions(role_id)
        hierarchy["all_permissions"] = [
            {"code": p.code, "name": p.name, "category": p.category}
            for p in all_permissions
        ]

        return hierarchy

    async def get_effective_permissions(
        self,
        agent_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取用户的有效权限（合并所有来源）

        Args:
            agent_id: 用户ID
            resource_type: 资源类型过滤
            resource_id: 资源ID过滤

        Returns:
            Dict: 有效权限详情
        """
        result = {
            "agent_id": agent_id,
            "direct_permissions": [],
            "role_permissions": [],
            "resource_permissions": [],
            "inherited_permissions": [],
            "denied_permissions": [],
            "effective_permissions": []
        }

        # 1. 直接用户权限
        user_perms = await self._get_user_direct_permissions(agent_id)
        for perm in user_perms:
            entry = {
                "code": perm.permission.code,
                "name": perm.permission.name,
                "grant_type": perm.grant_type,
                "scope": perm.scope,
                "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
            }
            if perm.grant_type == "deny":
                result["denied_permissions"].append(entry)
            else:
                result["direct_permissions"].append(entry)

        # 2. 角色权限（包括继承）
        user_roles = await self._get_user_roles(agent_id)
        for role in user_roles:
            role_perms = await self._get_all_role_permissions(role.role_id)
            for perm in role_perms:
                result["role_permissions"].append({
                    "code": perm.code,
                    "name": perm.name,
                    "category": perm.category,
                    "from_role": role.code
                })

        # 3. 资源级权限
        if resource_type and resource_id:
            resource_perms = await self._get_resource_permissions(
                agent_id, resource_type, resource_id
            )
            for perm in resource_perms:
                result["resource_permissions"].append({
                    "code": perm.permission_code,
                    "grant_type": perm.grant_type,
                    "conditions": perm.conditions,
                    "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
                })

        # 4. 计算有效权限（Deny 优先）
        denied_codes = {p["code"] for p in result["denied_permissions"]}
        all_allowed = set()
        for p in result["direct_permissions"] + result["role_permissions"] + result["resource_permissions"]:
            code = p["code"]
            if code not in denied_codes:
                all_allowed.add(code)

        result["effective_permissions"] = sorted(list(all_allowed))
        return result

    async def check_operation_permission(
        self,
        agent_id: str,
        operation: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        检查操作级权限

        Args:
            agent_id: 用户ID
            operation: 操作（如 create/read/update/delete）
            resource_type: 资源类型
            resource_id: 资源ID（可选）
            context: 上下文条件

        Returns:
            Dict: 检查结果
        """
        # 构造权限代码
        permission_code = f"{resource_type}.{operation}"

        # 构造资源标识
        resource = f"{resource_type}:{resource_id or '*'}"

        # 检查显式 Deny
        is_denied = await self._check_explicit_deny(agent_id, permission_code, context)
        if is_denied:
            return {
                "allowed": False,
                "reason": "explicit_deny",
                "permission_code": permission_code,
                "resource": resource
            }

        # 检查 Allow
        is_allowed = await self._check_explicit_allow(
            agent_id, permission_code, resource_type, resource_id, context
        )

        if is_allowed:
            return {
                "allowed": True,
                "reason": "explicit_allow",
                "permission_code": permission_code,
                "resource": resource
            }

        # 隐式 Deny
        return {
            "allowed": False,
            "reason": "implicit_deny",
            "permission_code": permission_code,
            "resource": resource
        }

    # ========== 权限委派 ==========

    async def delegate_permission(
        self,
        from_agent_id: str,
        to_agent_id: str,
        permission_code: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        conditions: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        权限委派 - 用户将自己的权限委派给另一个用户

        要求委出者拥有该权限，且委出者的权限允许委派
        """
        # 1. 检查委出者是否有该权限
        has_perm = await self._check_explicit_allow(
            from_agent_id, permission_code, resource_type, resource_id
        )
        if not has_perm:
            return False

        # 2. 检查委出者是否有委派权限
        can_delegate = await self._check_explicit_allow(
            from_agent_id, f"{permission_code}.delegate", resource_type, resource_id
        )
        if not can_delegate:
            # 检查是否有通用委派权限
            can_delegate = await self._check_explicit_allow(
                from_agent_id, "permission.delegate", resource_type, resource_id
            )

        if not can_delegate:
            return False

        # 3. 授予被委派者权限
        if resource_type and resource_id:
            # 资源级委派
            perm = ResourcePermission(
                resource_type=resource_type,
                resource_id=resource_id,
                permission_code=permission_code,
                agent_id=to_agent_id,
                grant_type="allow",
                conditions=conditions,
                expires_at=expires_at,
                created_by_agent_id=from_agent_id
            )
        else:
            # 用户级委派
            perm_record = await self._get_permission_by_code(permission_code)
            if not perm_record:
                return False

            perm = UserPermission(
                agent_id=to_agent_id,
                permission_id=perm_record.permission_id,
                grant_type="allow",
                scope=conditions,
                expires_at=expires_at,
                created_by_agent_id=from_agent_id
            )

        self.db.add(perm)
        await self.db.commit()
        return True

    # ========== 条件访问 ==========

    async def evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        评估条件表达式

        支持的条件格式：
        1. 简单键值：{"category": "技术"}
        2. 操作符条件：{"StringEquals": {"category": "技术"}}
        3. 复合条件：{"AND": [...], "OR": [...], "NOT": ...}
        """
        if not conditions:
            return True

        # 复合条件
        if "AND" in conditions:
            return all(
                await self.evaluate_conditions(c, context)
                for c in conditions["AND"]
            )

        if "OR" in conditions:
            return any(
                await self.evaluate_conditions(c, context)
                for c in conditions["OR"]
            )

        if "NOT" in conditions:
            return not await self.evaluate_conditions(conditions["NOT"], context)

        # 简单条件 - 从 PolicyService 导入条件评估器
        from app.services.policy_service import ConditionEvaluator
        return ConditionEvaluator.evaluate(conditions, context)

    # ========== 内部方法 ==========

    async def _get_role(self, role_id: str) -> Optional[Role]:
        query = select(Role).where(Role.role_id == role_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_user_roles(self, agent_id: str) -> List[Role]:
        """获取用户的所有角色"""
        # 从 TeamMember 获取
        query = select(TeamMember).where(
            and_(
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True
            )
        )
        result = await self.db.execute(query)
        memberships = result.scalars().all()

        role_codes = []
        for m in memberships:
            if m.role == "owner":
                role_codes.append("team_owner")
            elif m.role == "admin":
                role_codes.append("team_admin")
            elif m.role == "member":
                role_codes.append("team_member")

        if not role_codes:
            return []

        query = select(Role).where(
            and_(Role.code.in_(role_codes), Role.is_active == True)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _collect_parent_roles(self, role: Role, visited: Set[str]) -> List[Role]:
        """收集所有父角色"""
        if role.role_id in visited:
            return []
        visited.add(role.role_id)

        parents = []
        if role.inherit_from_id:
            query = select(Role).where(Role.role_id == role.inherit_from_id)
            result = await self.db.execute(query)
            parent = result.scalar_one_or_none()
            if parent and parent.is_active:
                parents.append(parent)
                parents.extend(await self._collect_parent_roles(parent, visited))

        return parents

    async def _collect_child_roles(self, role_id: str, visited: Set[str]) -> List[Role]:
        """收集所有子角色"""
        if role_id in visited:
            return []
        visited.add(role_id)

        query = select(Role).where(
            and_(Role.inherit_from_id == role_id, Role.is_active == True)
        )
        result = await self.db.execute(query)
        children = result.scalars().all()

        all_children = list(children)
        for child in children:
            all_children.extend(await self._collect_child_roles(child.role_id, visited))

        return all_children

    async def _get_all_role_permissions(self, role_id: str) -> List[Permission]:
        """获取角色的所有权限（包括继承）"""
        visited_roles = set()
        all_perm_ids = set()

        await self._collect_role_permission_ids(role_id, visited_roles, all_perm_ids)

        if not all_perm_ids:
            return []

        query = select(Permission).where(
            and_(
                Permission.permission_id.in_(list(all_perm_ids)),
                Permission.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _collect_role_permission_ids(
        self,
        role_id: str,
        visited: Set[str],
        perm_ids: Set[str]
    ) -> None:
        """递归收集角色权限ID"""
        if role_id in visited:
            return
        visited.add(role_id)

        # 获取直接权限
        query = select(RolePermission).where(RolePermission.role_id == role_id)
        result = await self.db.execute(query)
        role_perms = result.scalars().all()
        for rp in role_perms:
            perm_ids.add(rp.permission_id)

        # 递归继承
        role = await self._get_role(role_id)
        if role and role.inherit_from_id:
            await self._collect_role_permission_ids(role.inherit_from_id, visited, perm_ids)

    async def _get_user_direct_permissions(self, agent_id: str) -> List[UserPermission]:
        query = select(UserPermission).options(
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
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _get_resource_permissions(
        self,
        agent_id: str,
        resource_type: str,
        resource_id: str
    ) -> List[ResourcePermission]:
        query = select(ResourcePermission).where(
            and_(
                ResourcePermission.resource_type == resource_type,
                ResourcePermission.resource_id == resource_id,
                ResourcePermission.agent_id == agent_id,
                or_(
                    ResourcePermission.expires_at.is_(None),
                    ResourcePermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _check_explicit_deny(
        self,
        agent_id: str,
        permission_code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """检查显式 Deny"""
        # 用户级 Deny
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
        if result.scalar_one_or_none():
            return True

        # 资源级 Deny
        if context and "resource_type" in context and "resource_id" in context:
            query = select(ResourcePermission).where(
                and_(
                    ResourcePermission.resource_type == context["resource_type"],
                    ResourcePermission.resource_id == context["resource_id"],
                    ResourcePermission.agent_id == agent_id,
                    ResourcePermission.permission_code == permission_code,
                    ResourcePermission.grant_type == "deny",
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

    async def _check_explicit_allow(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """检查显式 Allow"""
        # 用户级 Allow
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
        if result.scalar_one_or_none():
            return True

        # 角色级 Allow
        user_roles = await self._get_user_roles(agent_id)
        if user_roles:
            role_ids = [r.role_id for r in user_roles]
            query = select(RolePermission).where(
                and_(
                    RolePermission.role_id.in_(role_ids),
                    RolePermission.permission_id.in_(
                        select(Permission.permission_id).where(Permission.code == permission_code)
                    )
                )
            )
            result = await self.db.execute(query)
            if result.scalar_one_or_none():
                return True

        # 资源级 Allow
        if resource_type and resource_id:
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

        return False

    async def _get_permission_by_code(self, code: str) -> Optional[Permission]:
        query = select(Permission).where(Permission.code == code)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
