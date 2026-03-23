"""
高级权限系统测试

测试内容：
- 策略 CRUD
- 策略版本管理
- 策略附加/分离
- 条件评估引擎
- 策略评估引擎
- 权限检查
- 审计日志
- RBAC 角色继承
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.tables import (
    Agent, Permission, Role, RolePermission, UserPermission,
    ResourcePermission, PermissionPolicy, PolicyVersion,
    PolicyAttachment, PermissionAuditLog, Memory, Team, TeamMember
)
from app.services.policy_service import PolicyService, PolicyEvaluator, ConditionEvaluator
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService


# ========== Fixtures ==========

@pytest.fixture
async def test_agent(db: AsyncSession):
    """创建测试用户"""
    agent = Agent(
        name="policy_test_user",
        description="策略测试用户",
        api_key="policy_test_key_1234567890"
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@pytest.fixture
async def test_agent2(db: AsyncSession):
    """创建第二个测试用户"""
    agent = Agent(
        name="policy_test_user2",
        description="策略测试用户2",
        api_key="policy_test_key_0987654321"
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@pytest.fixture
async def test_permissions(db: AsyncSession):
    """创建测试权限"""
    permissions = [
        Permission(code="memory:create", name="创建记忆", category="memory", level="operation"),
        Permission(code="memory:get", name="查看记忆", category="memory", level="operation"),
        Permission(code="memory:list", name="列出记忆", category="memory", level="operation"),
        Permission(code="memory:delete", name="删除记忆", category="memory", level="operation"),
        Permission(code="team:manage", name="管理团队", category="team", level="operation"),
        Permission(code="system:policy:create", name="创建策略", category="system", level="system"),
        Permission(code="system:policy:list", name="列出策略", category="system", level="system"),
        Permission(code="system:policy:get", name="查看策略", category="system", level="system"),
        Permission(code="system:policy:update", name="更新策略", category="system", level="system"),
        Permission(code="system:policy:delete", name="删除策略", category="system", level="system"),
        Permission(code="system:policy:attach", name="附加策略", category="system", level="system"),
        Permission(code="system:policy:detach", name="分离策略", category="system", level="system"),
        Permission(code="system:audit:query", name="查询审计", category="system", level="system"),
        Permission(code="system:audit:report", name="审计报告", category="system", level="system"),
        Permission(code="system:role:get", name="查看角色", category="system", level="system"),
    ]
    for perm in permissions:
        db.add(perm)
    await db.commit()
    for perm in permissions:
        await db.refresh(perm)
    return permissions


@pytest.fixture
async def test_role(db: AsyncSession):
    """创建测试角色"""
    role = Role(
        code="test_policy_role",
        name="策略测试角色",
        category="platform",
        level=1
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@pytest.fixture
async def test_memory(db: AsyncSession, test_agent: Agent):
    """创建测试记忆"""
    memory = Memory(
        seller_agent_id=test_agent.agent_id,
        title="策略测试记忆",
        category="技术",
        tags=["测试"],
        summary="测试记忆摘要",
        content={"key": "value"},
        price=100
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


@pytest.fixture
async def sample_policy_document():
    """示例策略文档"""
    return {
        "Version": "2024-01-01",
        "Statement": [
            {
                "Sid": "AllowMemoryRead",
                "Effect": "Allow",
                "Action": ["memory:get", "memory:list"],
                "Resource": ["memory:*"]
            }
        ]
    }


@pytest.fixture
async def conditional_policy_document():
    """带条件的策略文档"""
    return {
        "Version": "2024-01-01",
        "Statement": [
            {
                "Sid": "AllowTechMemories",
                "Effect": "Allow",
                "Action": ["memory:get"],
                "Resource": ["memory:*"],
                "Condition": {
                    "StringEquals": {"category": "技术"}
                }
            }
        ]
    }


@pytest.fixture
async def deny_policy_document():
    """Deny 策略文档"""
    return {
        "Version": "2024-01-01",
        "Statement": [
            {
                "Sid": "DenyDelete",
                "Effect": "Deny",
                "Action": ["memory:delete"],
                "Resource": ["memory:*"]
            }
        ]
    }


# ========== 条件评估器测试 ==========

class TestConditionEvaluator:
    """条件评估器测试"""

    def test_string_equals(self):
        """测试 StringEquals"""
        condition = {"StringEquals": {"category": "技术"}}
        assert ConditionEvaluator.evaluate(condition, {"category": "技术"}) is True
        assert ConditionEvaluator.evaluate(condition, {"category": "生活"}) is False

    def test_string_not_equals(self):
        """测试 StringNotEquals"""
        condition = {"StringNotEquals": {"category": "技术"}}
        assert ConditionEvaluator.evaluate(condition, {"category": "生活"}) is True
        assert ConditionEvaluator.evaluate(condition, {"category": "技术"}) is False

    def test_string_equals_ignore_case(self):
        """测试 StringEqualsIgnoreCase"""
        condition = {"StringEqualsIgnoreCase": {"category": "技术"}}
        assert ConditionEvaluator.evaluate(condition, {"category": "技术"}) is True
        assert ConditionEvaluator.evaluate(condition, {"category": "TECH"}) is False

    def test_string_like(self):
        """测试 StringLike（通配符）"""
        condition = {"StringLike": {"title": "*测试*"}}
        assert ConditionEvaluator.evaluate(condition, {"title": "这是一个测试记忆"}) is True
        assert ConditionEvaluator.evaluate(condition, {"title": "普通记忆"}) is False

    def test_string_contains(self):
        """测试 StringContains"""
        condition = {"StringContains": {"title": "测试"}}
        assert ConditionEvaluator.evaluate(condition, {"title": "这是一个测试记忆"}) is True
        assert ConditionEvaluator.evaluate(condition, {"title": "普通记忆"}) is False

    def test_numeric_equals(self):
        """测试 NumericEquals"""
        condition = {"NumericEquals": {"price": 100}}
        assert ConditionEvaluator.evaluate(condition, {"price": 100}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 200}) is False

    def test_numeric_greater_than(self):
        """测试 NumericGreaterThan"""
        condition = {"NumericGreaterThan": {"price": 50}}
        assert ConditionEvaluator.evaluate(condition, {"price": 100}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 30}) is False

    def test_numeric_less_than(self):
        """测试 NumericLessThan"""
        condition = {"NumericLessThan": {"price": 100}}
        assert ConditionEvaluator.evaluate(condition, {"price": 50}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 150}) is False

    def test_ip_address(self):
        """测试 IpAddress"""
        condition = {"IpAddress": {"source_ip": "10.0.0.0/8"}}
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "10.0.0.1"}) is True
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "192.168.1.1"}) is False

    def test_not_ip_address(self):
        """测试 NotIpAddress"""
        condition = {"NotIpAddress": {"source_ip": "10.0.0.0/8"}}
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "192.168.1.1"}) is True
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "10.0.0.1"}) is False

    def test_bool(self):
        """测试 Bool"""
        condition = {"Bool": {"is_public": True}}
        assert ConditionEvaluator.evaluate(condition, {"is_public": True}) is True
        assert ConditionEvaluator.evaluate(condition, {"is_public": False}) is False

    def test_null(self):
        """测试 Null"""
        # Null: true 表示键不存在
        condition = {"Null": {"optional_field": True}}
        assert ConditionEvaluator.evaluate(condition, {}) is True
        assert ConditionEvaluator.evaluate(condition, {"optional_field": "value"}) is False

        # Null: false 表示键必须存在
        condition = {"Null": {"required_field": False}}
        assert ConditionEvaluator.evaluate(condition, {"required_field": "value"}) is True
        assert ConditionEvaluator.evaluate(condition, {}) is False

    def test_date_greater_than(self):
        """测试 DateGreaterThan"""
        condition = {"DateGreaterThan": {"timestamp": "2024-01-01T00:00:00"}}
        assert ConditionEvaluator.evaluate(condition, {"timestamp": "2024-06-01T00:00:00"}) is True
        assert ConditionEvaluator.evaluate(condition, {"timestamp": "2023-06-01T00:00:00"}) is False

    def test_multiple_conditions(self):
        """测试多个条件（AND 逻辑）"""
        condition = {
            "StringEquals": {"category": "技术"},
            "NumericGreaterThan": {"price": 50}
        }
        assert ConditionEvaluator.evaluate(condition, {"category": "技术", "price": 100}) is True
        assert ConditionEvaluator.evaluate(condition, {"category": "技术", "price": 30}) is False
        assert ConditionEvaluator.evaluate(condition, {"category": "生活", "price": 100}) is False

    def test_arn_like(self):
        """测试 ArnLike"""
        condition = {"ArnLike": {"resource": "memory:mem_*"}}
        assert ConditionEvaluator.evaluate(condition, {"resource": "memory:mem_abc123"}) is True
        assert ConditionEvaluator.evaluate(condition, {"resource": "team:team_abc"}) is False

    def test_empty_condition(self):
        """测试空条件"""
        assert ConditionEvaluator.evaluate({}, {"any": "value"}) is True


# ========== 策略评估引擎测试 ==========

class TestPolicyEvaluator:
    """策略评估引擎测试"""

    def test_allow_policy(self):
        """测试 Allow 策略"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get"],
                "Resource": ["memory:*"]
            }]
        }
        allowed, reason = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is True

    def test_deny_policy(self):
        """测试 Deny 策略"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Deny",
                "Action": ["memory:delete"],
                "Resource": ["memory:*"]
            }]
        }
        allowed, reason = PolicyEvaluator.evaluate_policies(
            [policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is False

    def test_deny_overrides_allow(self):
        """测试 Deny 优先于 Allow"""
        allow_policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:*"],
                "Resource": ["memory:*"]
            }]
        }
        deny_policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Deny",
                "Action": ["memory:delete"],
                "Resource": ["memory:*"]
            }]
        }
        # Deny 优先
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [allow_policy, deny_policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is False

        # 其他操作仍然 Allow
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [allow_policy, deny_policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is True

    def test_implicit_deny(self):
        """测试隐式 Deny"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get"],
                "Resource": ["memory:*"]
            }]
        }
        # 没有匹配的 Allow = 隐式 Deny
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is False

    def test_action_wildcard(self):
        """测试 Action 通配符"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:*"],
                "Resource": ["memory:*"]
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is True

        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is True

    def test_not_action(self):
        """测试 NotAction"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "NotAction": ["memory:delete"],
                "Resource": ["memory:*"]
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is True

        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is False

    def test_not_resource(self):
        """测试 NotResource"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get"],
                "NotResource": ["memory:mem_secret"]
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_public", {}
        )
        assert allowed is True

        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_secret", {}
        )
        assert allowed is False

    def test_conditional_policy(self):
        """测试带条件的策略"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get"],
                "Resource": ["memory:*"],
                "Condition": {
                    "StringEquals": {"category": "技术"}
                }
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {"category": "技术"}
        )
        assert allowed is True

        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {"category": "生活"}
        )
        assert allowed is False


# ========== 策略服务测试 ==========

class TestPolicyService:
    """策略服务测试"""

    async def test_create_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试创建策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="测试策略",
            policy_document=sample_policy_document,
            description="测试描述",
            created_by_agent_id=test_agent.agent_id
        )

        assert policy.policy_id is not None
        assert policy.name == "测试策略"
        assert policy.policy_type == "custom"
        assert policy.version_count == 1
        assert policy.default_version_id is not None

    async def test_create_policy_invalid_document(
        self,
        db: AsyncSession,
        test_agent: Agent
    ):
        """测试创建策略 - 无效文档"""
        service = PolicyService(db)

        with pytest.raises(ValueError, match="must contain 'Statement'"):
            await service.create_policy(
                name="无效策略",
                policy_document={"Version": "2024-01-01"},
                created_by_agent_id=test_agent.agent_id
            )

    async def test_get_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试获取策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="获取测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        fetched = await service.get_policy(policy.policy_id)
        assert fetched is not None
        assert fetched.name == "获取测试"

    async def test_list_policies(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试列出策略"""
        service = PolicyService(db)

        # 创建多个策略
        for i in range(3):
            await service.create_policy(
                name=f"列表测试{i}",
                policy_document=sample_policy_document,
                created_by_agent_id=test_agent.agent_id
            )

        result = await service.list_policies(page=1, page_size=10)
        assert result["total"] >= 3

    async def test_update_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试更新策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="更新测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        # 更新基本信息
        updated = await service.update_policy(
            policy_id=policy.policy_id,
            name="更新后的名称"
        )
        assert updated.name == "更新后的名称"

        # 更新策略文档（创建新版本）
        new_doc = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get", "memory:list", "memory:create"],
                "Resource": ["memory:*"]
            }]
        }
        updated = await service.update_policy(
            policy_id=policy.policy_id,
            policy_document=new_doc,
            changelog="添加了 create 权限"
        )
        assert updated.version_count == 2

        # 验证版本
        versions = await service.get_policy_versions(policy.policy_id)
        assert len(versions) == 2

    async def test_delete_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试删除策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="删除测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        success = await service.delete_policy(policy.policy_id)
        assert success is True

        fetched = await service.get_policy(policy.policy_id)
        assert fetched is None

    async def test_delete_system_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试不能删除系统策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="系统策略",
            policy_document=sample_policy_document,
            policy_type="managed",
            created_by_agent_id=test_agent.agent_id
        )
        policy.is_system = True
        await db.commit()

        with pytest.raises(ValueError, match="Cannot delete system policy"):
            await service.delete_policy(policy.policy_id)

    async def test_attach_and_detach_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试附加和分离策略"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="附加测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        # 附加到用户
        attachment = await service.attach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )
        assert attachment.attachment_id is not None

        # 查询附加
        attachments = await service.get_attached_policies(agent_id=test_agent.agent_id)
        assert len(attachments) == 1

        # 分离
        success = await service.detach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )
        assert success is True

    async def test_version_management(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试版本管理"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="版本测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        # 创建多个版本
        for i in range(3):
            await service.update_policy(
                policy_id=policy.policy_id,
                policy_document={
                    "Version": "2024-01-01",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [f"memory:action{i}"],
                        "Resource": ["memory:*"]
                    }]
                },
                changelog=f"Version {i+2}"
            )

        versions = await service.get_policy_versions(policy.policy_id)
        assert len(versions) == 4  # 1 initial + 3 updates

        # 设置默认版本
        old_version = versions[-1]  # 最早的版本
        success = await service.set_default_version(policy.policy_id, old_version.version_id)
        assert success is True

    async def test_check_permission_with_policy(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试通过策略检查权限"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="权限检查测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        await service.attach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # 检查允许的操作
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource="memory:mem_123"
        )
        assert result["allowed"] is True

        # 检查不允许的操作
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:delete",
            resource="memory:mem_123"
        )
        assert result["allowed"] is False

    async def test_conditional_policy_check(
        self,
        db: AsyncSession,
        test_agent: Agent,
        conditional_policy_document: dict
    ):
        """测试带条件的策略检查"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="条件策略测试",
            policy_document=conditional_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        await service.attach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # 满足条件
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource="memory:mem_123",
            context={"category": "技术"}
        )
        assert result["allowed"] is True

        # 不满足条件
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource="memory:mem_123",
            context={"category": "生活"}
        )
        assert result["allowed"] is False

    async def test_deny_overrides_allow_in_service(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict,
        deny_policy_document: dict
    ):
        """测试服务层 Deny 优先于 Allow"""
        service = PolicyService(db)

        # Allow 策略
        allow_policy = await service.create_policy(
            name="Allow策略",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )
        await service.attach_policy(
            policy_id=allow_policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # Deny 策略
        deny_policy = await service.create_policy(
            name="Deny策略",
            policy_document=deny_policy_document,
            created_by_agent_id=test_agent.agent_id
        )
        await service.attach_policy(
            policy_id=deny_policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # delete 操作被 Deny
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:delete",
            resource="memory:mem_123"
        )
        assert result["allowed"] is False

        # get 操作仍然 Allow
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource="memory:mem_123"
        )
        assert result["allowed"] is True


# ========== RBAC 服务测试 ==========

class TestRBACService:
    """RBAC 服务测试"""

    async def test_get_effective_permissions(
        self,
        db: AsyncSession,
        test_agent: Agent,
        test_permissions: list
    ):
        """测试获取有效权限"""
        # 授予用户直接权限
        user_perm = UserPermission(
            agent_id=test_agent.agent_id,
            permission_id=test_permissions[0].permission_id,
            grant_type="allow"
        )
        db.add(user_perm)
        await db.commit()

        rbac_service = RBACService(db)
        result = await rbac_service.get_effective_permissions(test_agent.agent_id)

        assert test_permissions[0].code in result["effective_permissions"]
        assert len(result["direct_permissions"]) == 1

    async def test_deny_priority(
        self,
        db: AsyncSession,
        test_agent: Agent,
        test_permissions: list
    ):
        """测试 Deny 优先级"""
        # Allow
        allow_perm = UserPermission(
            agent_id=test_agent.agent_id,
            permission_id=test_permissions[0].permission_id,
            grant_type="allow"
        )
        db.add(allow_perm)

        # Deny（同权限）
        deny_perm = UserPermission(
            agent_id=test_agent.agent_id,
            permission_id=test_permissions[0].permission_id,
            grant_type="deny"
        )
        db.add(deny_perm)
        await db.commit()

        rbac_service = RBACService(db)
        result = await rbac_service.get_effective_permissions(test_agent.agent_id)

        # Deny 优先，不应在有效权限中
        assert test_permissions[0].code not in result["effective_permissions"]
        assert len(result["denied_permissions"]) == 1

    async def test_role_hierarchy(
        self,
        db: AsyncSession,
        test_role: Role
    ):
        """测试角色继承"""
        # 创建父角色
        parent_role = Role(
            code="parent_role",
            name="父角色",
            category="platform",
            level=2
        )
        db.add(parent_role)
        await db.commit()

        # 设置继承
        test_role.inherit_from_id = parent_role.role_id
        await db.commit()

        rbac_service = RBACService(db)
        hierarchy = await rbac_service.get_role_hierarchy(test_role.role_id)

        assert len(hierarchy["parents"]) == 1
        assert hierarchy["parents"][0]["code"] == "parent_role"

    async def test_condition_evaluation(
        self,
        db: AsyncSession
    ):
        """测试条件评估"""
        rbac_service = RBACService(db)

        # 简单条件
        result = await rbac_service.evaluate_conditions(
            {"StringEquals": {"category": "技术"}},
            {"category": "技术"}
        )
        assert result is True

        # AND 条件
        result = await rbac_service.evaluate_conditions(
            {
                "AND": [
                    {"StringEquals": {"category": "技术"}},
                    {"NumericGreaterThan": {"price": 50}}
                ]
            },
            {"category": "技术", "price": 100}
        )
        assert result is True

        # OR 条件
        result = await rbac_service.evaluate_conditions(
            {
                "OR": [
                    {"StringEquals": {"category": "技术"}},
                    {"StringEquals": {"category": "生活"}}
                ]
            },
            {"category": "生活"}
        )
        assert result is True

        # NOT 条件
        result = await rbac_service.evaluate_conditions(
            {"NOT": {"StringEquals": {"category": "技术"}}},
            {"category": "生活"}
        )
        assert result is True


# ========== 审计服务测试 ==========

class TestAuditService:
    """审计服务测试"""

    async def test_log_and_query(
        self,
        db: AsyncSession,
        test_agent: Agent
    ):
        """测试记录和查询审计日志"""
        audit_service = AuditService(db)

        # 记录审计日志
        await audit_service.log_permission_check(
            agent_id=test_agent.agent_id,
            permission_code="memory:get",
            resource_type="memory",
            resource_id="mem_123",
            status="success",
            reason="explicit_allow"
        )
        await db.commit()

        # 查询
        result = await audit_service.query_permission_audit_logs(
            actor_agent_id=test_agent.agent_id
        )

        assert result["total"] >= 1
        assert len(result["logs"]) >= 1

    async def test_generate_report(
        self,
        db: AsyncSession,
        test_agent: Agent
    ):
        """测试生成审计报告"""
        audit_service = AuditService(db)

        # 记录一些审计日志
        for status in ["success", "success", "forbidden"]:
            await audit_service.log_permission_check(
                agent_id=test_agent.agent_id,
                permission_code="memory:get",
                status=status
            )
        await db.commit()

        report = await audit_service.generate_permission_report()

        assert "summary" in report
        assert "permission_checks" in report
        assert "policy_statistics" in report

    async def test_log_permission_change(
        self,
        db: AsyncSession,
        test_agent: Agent,
        test_agent2: Agent
    ):
        """测试记录权限变更审计日志"""
        audit_service = AuditService(db)

        await audit_service.log_permission_change(
            actor_agent_id=test_agent.agent_id,
            action_type="grant",
            target_agent_id=test_agent2.agent_id,
            permission_code="memory:get"
        )
        await db.commit()

        result = await audit_service.query_permission_audit_logs(
            action_type="grant"
        )

        assert result["total"] >= 1


# ========== 策略版本清理测试 ==========

class TestPolicyVersionCleanup:
    """策略版本清理测试"""

    async def test_version_cleanup(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试版本清理（超过 MAX_VERSIONS）"""
        service = PolicyService(db)
        policy = await service.create_policy(
            name="版本清理测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )

        # 创建超过 MAX_VERSIONS 的版本
        for i in range(service.MAX_VERSIONS + 3):
            await service.update_policy(
                policy_id=policy.policy_id,
                policy_document={
                    "Version": "2024-01-01",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [f"memory:action{i}"],
                        "Resource": ["memory:*"]
                    }]
                }
            )

        versions = await service.get_policy_versions(policy.policy_id)
        assert len(versions) <= service.MAX_VERSIONS + 1  # +1 for initial version


# ========== 集成测试 ==========

class TestIntegration:
    """集成测试"""

    async def test_full_policy_lifecycle(
        self,
        db: AsyncSession,
        test_agent: Agent,
        sample_policy_document: dict
    ):
        """测试完整的策略生命周期"""
        service = PolicyService(db)

        # 1. 创建策略
        policy = await service.create_policy(
            name="生命周期测试",
            policy_document=sample_policy_document,
            description="完整生命周期测试",
            created_by_agent_id=test_agent.agent_id
        )
        assert policy.policy_id is not None

        # 2. 附加到用户
        await service.attach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # 3. 检查权限
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource="memory:mem_123"
        )
        assert result["allowed"] is True

        # 4. 更新策略
        await service.update_policy(
            policy_id=policy.policy_id,
            name="更新后的名称"
        )

        # 5. 分离策略
        await service.detach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # 6. 删除策略
        success = await service.delete_policy(policy.policy_id)
        assert success is True

    async def test_policy_with_resource_permissions(
        self,
        db: AsyncSession,
        test_agent: Agent,
        test_memory: Memory,
        sample_policy_document: dict
    ):
        """测试策略与资源权限的整合"""
        service = PolicyService(db)

        # 创建并附加策略
        policy = await service.create_policy(
            name="资源整合测试",
            policy_document=sample_policy_document,
            created_by_agent_id=test_agent.agent_id
        )
        await service.attach_policy(
            policy_id=policy.policy_id,
            agent_id=test_agent.agent_id
        )

        # 添加资源级权限
        resource_perm = ResourcePermission(
            resource_type="memory",
            resource_id=test_memory.memory_id,
            permission_code="memory:get",
            agent_id=test_agent.agent_id,
            grant_type="allow"
        )
        db.add(resource_perm)
        await db.commit()

        # 检查权限（策略 + 资源权限合并）
        result = await service.check_permission(
            agent_id=test_agent.agent_id,
            action="memory:get",
            resource=f"memory:{test_memory.memory_id}"
        )
        assert result["allowed"] is True
