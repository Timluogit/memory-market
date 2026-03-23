"""权限系统测试"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    Agent, Permission, Role, RolePermission, UserPermission,
    ResourcePermission, PermissionAuditLog, Memory
)
from app.services.permission_service import PermissionService


# ========== 测试数据 ==========

@pytest.fixture
async def test_permissions(db: AsyncSession):
    """创建测试权限"""
    permissions = [
        Permission(
            code="memory.create",
            name="创建记忆",
            description="创建新的记忆",
            category="memory",
            level="operation"
        ),
        Permission(
            code="memory.view",
            name="查看记忆",
            description="查看记忆内容",
            category="memory",
            level="operation"
        ),
        Permission(
            code="memory.delete",
            name="删除记忆",
            description="删除记忆",
            category="memory",
            level="operation"
        ),
        Permission(
            code="team.member",
            name="团队成员",
            description="团队基本权限",
            category="team",
            level="operation"
        ),
        Permission(
            code="team.admin",
            name="团队管理员",
            description="团队管理权限",
            category="team",
            level="operation"
        ),
    ]
    for perm in permissions:
        db.add(perm)
    await db.commit()

    return permissions


@pytest.fixture
async def test_role(db: AsyncSession):
    """创建测试角色"""
    role = Role(
        code="test_role",
        name="测试角色",
        description="测试用角色",
        category="platform",
        level=1
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@pytest.fixture
async def test_user(db: AsyncSession):
    """创建测试用户"""
    user = Agent(
        name="test_user",
        description="测试用户",
        api_key="test_api_key_123"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def test_memory(db: AsyncSession, test_user: Agent):
    """创建测试记忆"""
    memory = Memory(
        seller_agent_id=test_user.agent_id,
        title="测试记忆",
        category="测试",
        tags=[],
        summary="这是一个测试记忆",
        content={"test": "data"},
        price=100
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


# ========== 权限检查测试 ==========

async def test_has_permission_success(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限检查成功"""
    # 创建权限
    user_perm = UserPermission(
        agent_id=test_user.agent_id,
        permission_id=test_permissions[0].permission_id,
        grant_type="allow"
    )
    db.add(user_perm)
    await db.commit()

    # 检查权限
    service = PermissionService(db)
    has_perm = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create"
    )

    assert has_perm is True


async def test_has_permission_deny(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限拒绝（deny优先）"""
    # 先授予权限
    user_perm_allow = UserPermission(
        agent_id=test_user.agent_id,
        permission_id=test_permissions[0].permission_id,
        grant_type="allow"
    )
    db.add(user_perm_allow)

    # 再拒绝权限
    user_perm_deny = UserPermission(
        agent_id=test_user.agent_id,
        permission_id=test_permissions[0].permission_id,
        grant_type="deny"
    )
    db.add(user_perm_deny)
    await db.commit()

    # 检查权限
    service = PermissionService(db)
    has_perm = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create"
    )

    assert has_perm is False


async def test_has_permission_not_found(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限不存在"""
    service = PermissionService(db)
    has_perm = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="nonexistent.permission"
    )

    assert has_perm is False


# ========== 权限授予/撤销测试 ==========

async def test_grant_permission(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试授予权限"""
    service = PermissionService(db)
    success = await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )

    assert success is True

    # 验证权限已授予
    query = select(UserPermission).where(
        UserPermission.agent_id == test_user.agent_id
    )
    result = await db.execute(query)
    perms = result.scalars().all()
    assert len(perms) == 1


async def test_grant_permission_with_scope(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list,
    test_memory: Memory
):
    """测试授予带范围限制的权限"""
    service = PermissionService(db)
    success = await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        grant_type="allow",
        scope={"memory_ids": [test_memory.memory_id]},
        actor_agent_id=test_user.agent_id
    )

    assert success is True

    # 验证权限已授予
    query = select(UserPermission).where(
        UserPermission.agent_id == test_user.agent_id
    )
    result = await db.execute(query)
    perm = result.scalar_one_or_none()
    assert perm is not None
    assert perm.scope is not None
    assert test_memory.memory_id in perm.scope.get("memory_ids", [])


async def test_revoke_permission(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试撤销权限"""
    # 先授予权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )

    # 撤销权限
    success = await service.revoke_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        actor_agent_id=test_user.agent_id
    )

    assert success is True

    # 验证权限已撤销
    query = select(UserPermission).where(
        UserPermission.agent_id == test_user.agent_id
    )
    result = await db.execute(query)
    perms = result.scalars().all()
    assert len(perms) == 0


# ========== 资源权限测试 ==========

async def test_grant_resource_permission(
    db: AsyncSession,
    test_user: Agent,
    test_memory: Memory
):
    """测试授予资源权限"""
    service = PermissionService(db)
    success = await service.grant_resource_permission(
        resource_type="memory",
        resource_id=test_memory.memory_id,
        permission_code="memory.view",
        agent_id=test_user.agent_id,
        actor_agent_id=test_user.agent_id
    )

    assert success is True

    # 验证资源权限已授予
    query = select(ResourcePermission).where(
        and_(
            ResourcePermission.resource_type == "memory",
            ResourcePermission.resource_id == test_memory.memory_id,
            ResourcePermission.agent_id == test_user.agent_id
        )
    )
    result = await db.execute(query)
    perm = result.scalar_one_or_none()
    assert perm is not None


async def test_check_resource_permission(
    db: AsyncSession,
    test_user: Agent,
    test_memory: Memory
):
    """测试检查资源权限"""
    # 授予资源权限
    service = PermissionService(db)
    await service.grant_resource_permission(
        resource_type="memory",
        resource_id=test_memory.memory_id,
        permission_code="memory.view",
        agent_id=test_user.agent_id,
        actor_agent_id=test_user.agent_id
    )

    # 检查资源权限
    has_perm = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        resource_type="memory",
        resource_id=test_memory.memory_id
    )

    assert has_perm is True


async def test_revoke_resource_permission(
    db: AsyncSession,
    test_user: Agent,
    test_memory: Memory
):
    """测试撤销资源权限"""
    # 授予资源权限
    service = PermissionService(db)
    await service.grant_resource_permission(
        resource_type="memory",
        resource_id=test_memory.memory_id,
        permission_code="memory.view",
        agent_id=test_user.agent_id,
        actor_agent_id=test_user.agent_id
    )

    # 撤销资源权限
    success = await service.revoke_resource_permission(
        resource_type="memory",
        resource_id=test_memory.memory_id,
        permission_code="memory.view",
        agent_id=test_user.agent_id,
        actor_agent_id=test_user.agent_id
    )

    assert success is True

    # 验证资源权限已撤销
    query = select(ResourcePermission).where(
        and_(
            ResourcePermission.resource_type == "memory",
            ResourcePermission.resource_id == test_memory.memory_id,
            ResourcePermission.agent_id == test_user.agent_id
        )
    )
    result = await db.execute(query)
    perm = result.scalar_one_or_none()
    assert perm is None


# ========== 权限过期测试 ==========

async def test_permission_expiration(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限过期"""
    # 授予过期权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        expires_at=datetime.now() - timedelta(days=1),  # 已过期
        actor_agent_id=test_user.agent_id
    )

    # 检查权限
    has_perm = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create"
    )

    assert has_perm is False


# ========== 获取用户权限测试 ==========

async def test_get_user_permissions(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试获取用户权限列表"""
    # 授予权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )

    # 获取用户权限
    permissions = await service.get_user_permissions(test_user.agent_id)

    assert len(permissions) == 2
    perm_codes = [perm["code"] for perm in permissions]
    assert "memory.create" in perm_codes
    assert "memory.view" in perm_codes


# ========== 审计日志测试 ==========

async def test_permission_audit_log(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限审计日志"""
    # 授予权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )

    # 检查审计日志
    query = select(PermissionAuditLog).where(
        PermissionAuditLog.action_type == "grant"
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    assert len(logs) > 0
    assert logs[0].action_category == "permission"
    assert logs[0].permission_code == "memory.create"


# ========== 性能测试 ==========

async def test_permission_check_performance(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试权限检查性能（目标<5ms）"""
    import time

    # 授予权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.create",
        grant_type="allow",
        actor_agent_id=test_user.agent_id
    )

    # 测试权限检查性能
    iterations = 100
    total_time = 0

    for _ in range(iterations):
        start = time.time()
        await service.has_permission(
            agent_id=test_user.agent_id,
            permission_code="memory.create"
        )
        end = time.time()
        total_time += (end - start)

    avg_time = (total_time / iterations) * 1000  # 转换为毫秒

    print(f"\n平均权限检查时间: {avg_time:.2f}ms")
    assert avg_time < 5.0, f"权限检查性能不达标: {avg_time:.2f}ms > 5ms"


# ========== 权限范围测试 ==========

async def test_permission_scope_check(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list,
    test_memory: Memory
):
    """测试权限范围检查"""
    # 授予特定记忆的查看权限
    service = PermissionService(db)
    await service.grant_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        grant_type="allow",
        scope={"memory_ids": [test_memory.memory_id]},
        actor_agent_id=test_user.agent_id
    )

    # 检查对指定记忆的权限
    has_perm_authorized = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        resource_type="memory",
        resource_id=test_memory.memory_id
    )
    assert has_perm_authorized is True

    # 检查对未授权记忆的权限
    has_perm_unauthorized = await service.has_permission(
        agent_id=test_user.agent_id,
        permission_code="memory.view",
        resource_type="memory",
        resource_id="unauthorized_memory_id"
    )
    assert has_perm_unauthorized is False


# ========== 批量权限操作测试 ==========

async def test_bulk_permission_operations(
    db: AsyncSession,
    test_user: Agent,
    test_permissions: list
):
    """测试批量权限操作"""
    service = PermissionService(db)

    # 批量授予权限
    for perm in test_permissions:
        await service.grant_permission(
            agent_id=test_user.agent_id,
            permission_code=perm.code,
            grant_type="allow",
            actor_agent_id=test_user.agent_id
        )

    # 验证所有权限已授予
    permissions = await service.get_user_permissions(test_user.agent_id)
    assert len(permissions) == len(test_permissions)

    # 批量撤销权限
    for perm in test_permissions:
        await service.revoke_permission(
            agent_id=test_user.agent_id,
            permission_code=perm.code,
            actor_agent_id=test_user.agent_id
        )

    # 验证所有权限已撤销
    permissions = await service.get_user_permissions(test_user.agent_id)
    assert len(permissions) == 0
