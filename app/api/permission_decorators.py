"""权限装饰器 - 用于API权限控制"""
from functools import wraps
from typing import List, Optional, Callable, Any
from fastapi import HTTPException, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.permission_service import PermissionService
from app.db.database import get_db


def require_permission(permission_code: str):
    """
    要求特定权限的装饰器

    Args:
        permission_code: 权限代码，如 "memory.create"

    Example:
        @require_permission("memory.create")
        async def create_memory(request: Request, db: AsyncSession = Depends(get_db)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, db: AsyncSession = Depends(get_db), *args, **kwargs):
            # 从请求中获取用户ID（假设已经通过认证）
            agent_id = getattr(request.state, "agent_id", None)
            if not agent_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证"
                )

            # 检查权限
            perm_service = PermissionService(db)
            has_perm = await perm_service.has_permission(agent_id, permission_code)

            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限: {permission_code}"
                )

            # 执行原函数
            return await func(request, db, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permission_codes: List[str]):
    """
    要求任意一个权限的装饰器

    Args:
        permission_codes: 权限代码列表

    Example:
        @require_any_permission(["memory.create", "memory.update"])
        async def modify_memory(request: Request, db: AsyncSession = Depends(get_db)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, db: AsyncSession = Depends(get_db), *args, **kwargs):
            agent_id = getattr(request.state, "agent_id", None)
            if not agent_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证"
                )

            perm_service = PermissionService(db)
            has_any = False
            for perm_code in permission_codes:
                if await perm_service.has_permission(agent_id, perm_code):
                    has_any = True
                    break

            if not has_any:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限，需要以下任意一个: {', '.join(permission_codes)}"
                )

            return await func(request, db, *args, **kwargs)
        return wrapper
    return decorator


def require_all_permissions(permission_codes: List[str]):
    """
    要求所有权限的装饰器

    Args:
        permission_codes: 权限代码列表

    Example:
        @require_all_permissions(["memory.create", "team.member"])
        async def create_team_memory(request: Request, db: AsyncSession = Depends(get_db)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, db: AsyncSession = Depends(get_db), *args, **kwargs):
            agent_id = getattr(request.state, "agent_id", None)
            if not agent_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证"
                )

            perm_service = PermissionService(db)
            has_all = True
            for perm_code in permission_codes:
                if not await perm_service.has_permission(agent_id, perm_code):
                    has_all = False
                    break

            if not has_all:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限，需要所有权限: {', '.join(permission_codes)}"
                )

            return await func(request, db, *args, **kwargs)
        return wrapper
    return decorator


def require_resource_permission(
    permission_code: str,
    resource_type_param: str = "resource_type",
    resource_id_param: str = "resource_id"
):
    """
    要求资源级权限的装饰器

    Args:
        permission_code: 权限代码
        resource_type_param: 资源类型参数名（从请求中获取）
        resource_id_param: 资源ID参数名（从请求中获取）

    Example:
        @require_resource_permission("memory.view", "memory_type", "memory_id")
        async def view_memory(memory_id: str, memory_type: str = "memory", request: Request, db: AsyncSession = Depends(get_db)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取db和request
            db = None
            request = None
            for arg in args:
                if isinstance(arg, AsyncSession):
                    db = arg
                elif isinstance(arg, Request):
                    request = arg

            # 检查kwargs
            if not db:
                db = kwargs.get("db")
            if not request:
                request = kwargs.get("request")

            if not db or not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="装饰器参数错误"
                )

            agent_id = getattr(request.state, "agent_id", None)
            if not agent_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证"
                )

            # 从请求中获取资源类型和ID
            resource_type = kwargs.get(resource_type_param) or getattr(request.state, resource_type_param, None)
            resource_id = kwargs.get(resource_id_param) or getattr(request.state, resource_id_param, None)

            if not resource_type or not resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"缺少资源参数: {resource_type_param} 或 {resource_id_param}"
                )

            # 检查资源权限
            perm_service = PermissionService(db)
            has_perm = await perm_service.has_permission(
                agent_id=agent_id,
                permission_code=permission_code,
                resource_type=resource_type,
                resource_id=resource_id
            )

            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少资源权限: {permission_code} (资源: {resource_type}/{resource_id})"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def optional_permission(
    permission_code: str,
    raise_on_missing: bool = False
):
    """
    可选权限装饰器 - 不强制要求，但可以在函数内检查

    Args:
        permission_code: 权限代码
        raise_on_missing: 是否在缺少权限时抛出异常

    Example:
        @optional_permission("memory.delete")
        async def delete_memory(memory_id: str, request: Request, db: AsyncSession = Depends(get_db)):
            agent_id = request.state.agent_id
            perm_service = PermissionService(db)
            if await perm_service.has_permission(agent_id, "memory.delete"):
                # 可以删除
                ...
            else:
                # 只能删除自己的
                ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, db: AsyncSession = Depends(get_db), *args, **kwargs):
            agent_id = getattr(request.state, "agent_id", None)
            if agent_id:
                perm_service = PermissionService(db)
                has_perm = await perm_service.has_permission(agent_id, permission_code)
                request.state.has_permission = has_perm
            else:
                request.state.has_permission = False

            if raise_on_missing and not request.state.has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限: {permission_code}"
                )

            return await func(request, db, *args, **kwargs)
        return wrapper
    return decorator


# ========== 依赖注入函数 ==========

async def get_current_user_permissions(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    获取当前用户的所有权限（依赖注入）

    Example:
        @router.get("/permissions")
        async def list_my_permissions(
            permissions: List[dict] = Depends(get_current_user_permissions)
        ):
            return {"permissions": permissions}
    """
    agent_id = getattr(request.state, "agent_id", None)
    if not agent_id:
        return []

    perm_service = PermissionService(db)
    return await perm_service.get_user_permissions(agent_id)


async def check_permission(
    permission_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> bool:
    """
    检查权限（依赖注入）

    Example:
        @router.get("/check")
        async def check_perm(
            has_perm: bool = Depends(lambda r, db: check_permission("memory.view", r, db))
        ):
            return {"has_permission": has_perm}
    """
    agent_id = getattr(request.state, "agent_id", None)
    if not agent_id:
        return False

    perm_service = PermissionService(db)
    return await perm_service.has_permission(agent_id, permission_code)
