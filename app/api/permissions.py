"""权限管理API - 用户和角色权限管理"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.models.tables import Permission, Role, RolePermission, UserPermission, Agent
from app.services.permission_service import PermissionService
from app.api.permission_decorators import (
    require_permission,
    get_current_user_permissions
)


# ========== 路由器 ==========
router = APIRouter(prefix="/permissions", tags=["权限管理"])


# ========== 请求模型 ==========

class PermissionCreate(BaseModel):
    """创建权限"""
    code: str = Field(..., description="权限代码，如：memory.create")
    name: str = Field(..., description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    category: str = Field(..., description="权限分类：memory/team/user/system")
    level: str = Field(default="operation", description="权限层级：operation/resource/system")
    resource_type: Optional[str] = Field(None, description="资源类型：memory/team/agent")


class RoleCreate(BaseModel):
    """创建角色"""
    code: str = Field(..., description="角色代码，如：admin")
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    category: str = Field(..., description="角色分类：system/platform/team")
    level: int = Field(default=0, description="角色级别")
    inherit_from_id: Optional[str] = Field(None, description="继承自哪个角色")


class GrantUserPermission(BaseModel):
    """授予用户权限"""
    permission_code: str = Field(..., description="权限代码")
    grant_type: str = Field(default="allow", description="授权类型：allow/deny")
    scope: Optional[Dict[str, Any]] = Field(None, description="权限范围")
    expires_days: Optional[int] = Field(None, description="有效期天数")


class GrantRolePermission(BaseModel):
    """授予角色权限"""
    permission_id: str = Field(..., description="权限ID")
    conditions: Optional[Dict[str, Any]] = Field(None, description="条件限制")


# ========== 响应模型 ==========

class PermissionResponse(BaseModel):
    """权限信息"""
    permission_id: str
    code: str
    name: str
    description: Optional[str]
    category: str
    level: str
    resource_type: Optional[str]
    is_system: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """角色信息"""
    role_id: str
    code: str
    name: str
    description: Optional[str]
    category: str
    level: int
    inherit_from_id: Optional[str]
    inherit_from_name: Optional[str]
    is_system: bool
    is_active: bool
    member_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserPermissionResponse(BaseModel):
    """用户权限信息"""
    permission_id: str
    code: str
    name: str
    grant_type: str
    scope: Optional[Dict[str, Any]]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 权限管理端点 ==========

@router.get("", response_model=List[PermissionResponse])
async def list_permissions(
    category: Optional[str] = Query(None, description="过滤分类"),
    is_active: Optional[bool] = Query(None, description="是否仅显示激活权限"),
    db: AsyncSession = Depends(get_db)
):
    """获取权限列表"""
    query = select(Permission)

    if category:
        query = query.where(Permission.category == category)
    if is_active is not None:
        query = query.where(Permission.is_active == is_active)

    query = query.order_by(Permission.category, Permission.code)

    result = await db.execute(query)
    permissions = result.scalars().all()
    return permissions


@router.post("", response_model=PermissionResponse)
@require_permission("system.permission.create")
async def create_permission(
    perm_data: PermissionCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新权限"""
    # 检查代码是否已存在
    existing = await db.execute(
        select(Permission).where(Permission.code == perm_data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"权限代码已存在: {perm_data.code}"
        )

    # 创建权限
    permission = Permission(
        code=perm_data.code,
        name=perm_data.name,
        description=perm_data.description,
        category=perm_data.category,
        level=perm_data.level,
        resource_type=perm_data.resource_type
    )
    db.add(permission)
    await db.commit()
    await db.refresh(permission)

    return permission


# ========== 角色管理端点 ==========

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    category: Optional[str] = Query(None, description="过滤分类"),
    is_active: Optional[bool] = Query(None, description="是否仅显示激活角色"),
    db: AsyncSession = Depends(get_db)
):
    """获取角色列表"""
    query = select(Role)

    if category:
        query = query.where(Role.category == category)
    if is_active is not None:
        query = query.where(Role.is_active == is_active)

    query = query.order_by(Role.level, Role.code)

    result = await db.execute(query)
    roles = result.scalars().all()
    return roles


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取角色详情"""
    result = await db.execute(
        select(Role).where(Role.role_id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色不存在: {role_id}"
        )
    return role


@router.post("/roles", response_model=RoleResponse)
@require_permission("system.role.create")
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新角色"""
    # 检查代码是否已存在
    existing = await db.execute(
        select(Role).where(Role.code == role_data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"角色代码已存在: {role_data.code}"
        )

    # 检查继承的角色是否存在
    if role_data.inherit_from_id:
        parent = await db.execute(
            select(Role).where(Role.role_id == role_data.inherit_from_id)
        )
        if not parent.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"继承的角色不存在: {role_data.inherit_from_id}"
            )

    # 创建角色
    role = Role(
        code=role_data.code,
        name=role_data.name,
        description=role_data.description,
        category=role_data.category,
        level=role_data.level,
        inherit_from_id=role_data.inherit_from_id
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    return role


@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取角色的所有权限"""
    # 检查角色是否存在
    role = await db.execute(
        select(Role).where(Role.role_id == role_id)
    )
    if not role.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色不存在: {role_id}"
        )

    # 查询角色权限
    query = select(RolePermission).options(
        # selectinload(RolePermission.permission)
    ).where(RolePermission.role_id == role_id)

    result = await db.execute(query)
    role_perms = result.scalars().all()

    # 查询权限详情
    perm_ids = [perm.permission_id for perm in role_perms]
    if perm_ids:
        perms_result = await db.execute(
            select(Permission).where(Permission.permission_id.in_(perm_ids))
        )
        perms = perms_result.scalars().all()
        perm_dict = {perm.permission_id: perm for perm in perms}
    else:
        perm_dict = {}

    return {
        "role_id": role_id,
        "permissions": [
            {
                "permission_id": perm.permission_id,
                "code": perm_dict.get(perm.permission_id).code if perm.permission_id in perm_dict else None,
                "name": perm_dict.get(perm.permission_id).name if perm.permission_id in perm_dict else None,
                "conditions": perm.conditions
            }
            for perm in role_perms
        ]
    }


@router.post("/roles/{role_id}/permissions")
@require_permission("system.role.grant")
async def grant_role_permission(
    role_id: str,
    grant_data: GrantRolePermission,
    db: AsyncSession = Depends(get_db)
):
    """授予角色权限"""
    # 检查角色是否存在
    role = await db.execute(
        select(Role).where(Role.role_id == role_id)
    )
    if not role.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色不存在: {role_id}"
        )

    # 检查权限是否存在
    perm = await db.execute(
        select(Permission).where(Permission.permission_id == grant_data.permission_id)
    )
    if not perm.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"权限不存在: {grant_data.permission_id}"
        )

    # 检查是否已存在
    existing = await db.execute(
        select(RolePermission).where(
            and_(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == grant_data.permission_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="角色已拥有该权限"
        )

    # 授予权限
    role_perm = RolePermission(
        role_id=role_id,
        permission_id=grant_data.permission_id,
        conditions=grant_data.conditions
    )
    db.add(role_perm)
    await db.commit()

    return {"message": "权限授予成功"}


@router.delete("/roles/{role_id}/permissions/{permission_id}")
@require_permission("system.role.revoke")
async def revoke_role_permission(
    role_id: str,
    permission_id: str,
    db: AsyncSession = Depends(get_db)
):
    """撤销角色权限"""
    # 查询角色权限
    result = await db.execute(
        select(RolePermission).where(
            and_(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
        )
    )
    role_perm = result.scalar_one_or_none()
    if not role_perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色权限不存在"
        )

    # 删除权限
    await db.delete(role_perm)
    await db.commit()

    return {"message": "权限撤销成功"}


# ========== 用户权限管理端点 ==========

@router.get("/users/{user_id}")
async def get_user_permissions(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用户的所有权限（包括角色权限）"""
    # 检查用户是否存在
    user = await db.execute(
        select(Agent).where(Agent.agent_id == user_id)
    )
    if not user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}"
        )

    perm_service = PermissionService(db)
    permissions = await perm_service.get_user_permissions(user_id)

    return {"agent_id": user_id, "permissions": permissions}


@router.post("/users/{user_id}")
@require_permission("system.user.grant")
async def grant_user_permission(
    user_id: str,
    grant_data: GrantUserPermission,
    request,
    db: AsyncSession = Depends(get_db)
):
    """授予用户权限"""
    # 检查用户是否存在
    user = await db.execute(
        select(Agent).where(Agent.agent_id == user_id)
    )
    if not user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}"
        )

    # 检查权限是否存在
    perm = await db.execute(
        select(Permission).where(Permission.code == grant_data.permission_code)
    )
    if not perm.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"权限不存在: {grant_data.permission_code}"
        )

    # 计算过期时间
    expires_at = None
    if grant_data.expires_days:
        expires_at = datetime.now() + timedelta(days=grant_data.expires_days)

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 授予权限
    perm_service = PermissionService(db)
    success = await perm_service.grant_permission(
        agent_id=user_id,
        permission_code=grant_data.permission_code,
        grant_type=grant_data.grant_type,
        scope=grant_data.scope,
        expires_at=expires_at,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限授予失败"
        )

    return {"message": "权限授予成功"}


@router.delete("/users/{user_id}/{permission_code}")
@require_permission("system.user.revoke")
async def revoke_user_permission(
    user_id: str,
    permission_code: str,
    request,
    db: AsyncSession = Depends(get_db)
):
    """撤销用户权限"""
    # 检查用户是否存在
    user = await db.execute(
        select(Agent).where(Agent.agent_id == user_id)
    )
    if not user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}"
        )

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 撤销权限
    perm_service = PermissionService(db)
    success = await perm_service.revoke_permission(
        agent_id=user_id,
        permission_code=permission_code,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限撤销失败"
        )

    return {"message": "权限撤销成功"}


@router.get("/me")
async def get_my_permissions(
    permissions: List[dict] = Depends(get_current_user_permissions)
):
    """获取当前用户的权限列表"""
    return {"permissions": permissions}
