"""资源权限API - 资源级权限管理"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.models.tables import ResourcePermission, Memory, Team, Agent
from app.services.permission_service import PermissionService
from app.api.permission_decorators import require_permission, require_resource_permission


# ========== 路由器 ==========
router = APIRouter(prefix="/resource-permissions", tags=["资源权限管理"])


# ========== 请求模型 ==========

class GrantResourcePermission(BaseModel):
    """授予资源权限"""
    permission_code: str = Field(..., description="权限代码")
    agent_id: Optional[str] = Field(None, description="授权给哪个用户")
    role_id: Optional[str] = Field(None, description="授权给哪个角色")
    conditions: Optional[Dict[str, Any]] = Field(None, description="权限条件")
    expires_days: Optional[int] = Field(None, description="有效期天数")


# ========== 记忆权限端点 ==========

@router.get("/memories/{memory_id}")
async def get_memory_permissions(
    memory_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取记忆的权限列表"""
    # 检查记忆是否存在
    memory = await db.execute(
        select(Memory).where(Memory.memory_id == memory_id)
    )
    memory_obj = memory.scalar_one_or_none()
    if not memory_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"记忆不存在: {memory_id}"
        )

    # 查询资源权限
    query = select(ResourcePermission).where(
        and_(
            ResourcePermission.resource_type == "memory",
            ResourcePermission.resource_id == memory_id
        )
    ).order_by(ResourcePermission.created_at)

    result = await db.execute(query)
    perms = result.scalars().all()

    return {
        "memory_id": memory_id,
        "title": memory_obj.title,
        "permissions": [
            {
                "id": perm.id,
                "permission_code": perm.permission_code,
                "agent_id": perm.agent_id,
                "role_id": perm.role_id,
                "grant_type": perm.grant_type,
                "conditions": perm.conditions,
                "expires_at": perm.expires_at,
                "created_at": perm.created_at
            }
            for perm in perms
        ]
    }


@router.post("/memories/{memory_id}")
@require_permission("memory.permission.grant")
async def grant_memory_permission(
    memory_id: str,
    grant_data: GrantResourcePermission,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """授予记忆权限"""
    # 检查记忆是否存在
    memory = await db.execute(
        select(Memory).where(Memory.memory_id == memory_id)
    )
    if not memory.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"记忆不存在: {memory_id}"
        )

    # 验证至少指定了用户或角色
    if not grant_data.agent_id and not grant_data.role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    # 验证用户是否存在（如果指定了）
    if grant_data.agent_id:
        user = await db.execute(
            select(Agent).where(Agent.agent_id == grant_data.agent_id)
        )
        if not user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户不存在: {grant_data.agent_id}"
            )

    # 计算过期时间
    expires_at = None
    if grant_data.expires_days:
        expires_at = datetime.now() + timedelta(days=grant_data.expires_days)

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 授予权限
    perm_service = PermissionService(db)
    success = await perm_service.grant_resource_permission(
        resource_type="memory",
        resource_id=memory_id,
        permission_code=grant_data.permission_code,
        agent_id=grant_data.agent_id,
        role_id=grant_data.role_id,
        conditions=grant_data.conditions,
        expires_at=expires_at,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限授予失败"
        )

    return {"message": "权限授予成功"}


@router.delete("/memories/{memory_id}/{permission_code}")
@require_permission("memory.permission.revoke")
async def revoke_memory_permission(
    memory_id: str,
    permission_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent_id: Optional[str] = None,
    role_id: Optional[str] = None
):
    """撤销记忆权限"""
    # 检查记忆是否存在
    memory = await db.execute(
        select(Memory).where(Memory.memory_id == memory_id)
    )
    if not memory.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"记忆不存在: {memory_id}"
        )

    # 验证至少指定了用户或角色
    if not agent_id and not role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 撤销权限
    perm_service = PermissionService(db)
    success = await perm_service.revoke_resource_permission(
        resource_type="memory",
        resource_id=memory_id,
        permission_code=permission_code,
        agent_id=agent_id,
        role_id=role_id,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限撤销失败"
        )

    return {"message": "权限撤销成功"}


# ========== 团队权限端点 ==========

@router.get("/teams/{team_id}")
async def get_team_permissions(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取团队的权限列表"""
    # 检查团队是否存在
    team = await db.execute(
        select(Team).where(Team.team_id == team_id)
    )
    team_obj = team.scalar_one_or_none()
    if not team_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"团队不存在: {team_id}"
        )

    # 查询资源权限
    query = select(ResourcePermission).where(
        and_(
            ResourcePermission.resource_type == "team",
            ResourcePermission.resource_id == team_id
        )
    ).order_by(ResourcePermission.created_at)

    result = await db.execute(query)
    perms = result.scalars().all()

    return {
        "team_id": team_id,
        "name": team_obj.name,
        "permissions": [
            {
                "id": perm.id,
                "permission_code": perm.permission_code,
                "agent_id": perm.agent_id,
                "role_id": perm.role_id,
                "grant_type": perm.grant_type,
                "conditions": perm.conditions,
                "expires_at": perm.expires_at,
                "created_at": perm.created_at
            }
            for perm in perms
        ]
    }


@router.post("/teams/{team_id}")
@require_permission("team.permission.grant")
async def grant_team_permission(
    team_id: str,
    grant_data: GrantResourcePermission,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """授予团队权限"""
    # 检查团队是否存在
    team = await db.execute(
        select(Team).where(Team.team_id == team_id)
    )
    if not team.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"团队不存在: {team_id}"
        )

    # 验证至少指定了用户或角色
    if not grant_data.agent_id and not grant_data.role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    # 验证用户是否存在（如果指定了）
    if grant_data.agent_id:
        user = await db.execute(
            select(Agent).where(Agent.agent_id == grant_data.agent_id)
        )
        if not user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户不存在: {grant_data.agent_id}"
            )

    # 计算过期时间
    expires_at = None
    if grant_data.expires_days:
        expires_at = datetime.now() + timedelta(days=grant_data.expires_days)

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 授予权限
    perm_service = PermissionService(db)
    success = await perm_service.grant_resource_permission(
        resource_type="team",
        resource_id=team_id,
        permission_code=grant_data.permission_code,
        agent_id=grant_data.agent_id,
        role_id=grant_data.role_id,
        conditions=grant_data.conditions,
        expires_at=expires_at,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限授予失败"
        )

    return {"message": "权限授予成功"}


@router.delete("/teams/{team_id}/{permission_code}")
@require_permission("team.permission.revoke")
async def revoke_team_permission(
    team_id: str,
    permission_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent_id: Optional[str] = None,
    role_id: Optional[str] = None
):
    """撤销团队权限"""
    # 检查团队是否存在
    team = await db.execute(
        select(Team).where(Team.team_id == team_id)
    )
    if not team.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"团队不存在: {team_id}"
        )

    # 验证至少指定了用户或角色
    if not agent_id and not role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    # 获取当前用户ID
    actor_agent_id = getattr(request.state, "agent_id", None)

    # 撤销权限
    perm_service = PermissionService(db)
    success = await perm_service.revoke_resource_permission(
        resource_type="team",
        resource_id=team_id,
        permission_code=permission_code,
        agent_id=agent_id,
        role_id=role_id,
        actor_agent_id=actor_agent_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限撤销失败"
        )

    return {"message": "权限撤销成功"}


# ========== 通用资源权限检查端点 ==========

@router.post("/check")
async def check_resource_permission(
    resource_type: str,
    resource_id: str,
    permission_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """检查资源权限"""
    # 获取当前用户ID
    agent_id = getattr(request.state, "agent_id", None)
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证"
        )

    # 检查权限
    perm_service = PermissionService(db)
    has_perm = await perm_service.has_permission(
        agent_id=agent_id,
        permission_code=permission_code,
        resource_type=resource_type,
        resource_id=resource_id
    )

    return {
        "has_permission": has_perm,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "permission_code": permission_code
    }
