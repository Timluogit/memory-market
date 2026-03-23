"""
策略服务 - AWS IAM 风格的策略管理和评估引擎

支持：
- 策略 CRUD
- 策略版本管理
- 策略附加/分离
- 条件评估（StringEquals, StringLike, IpAddress, DateGreaterThan 等）
- 策略评估引擎（Allow/Deny 优先级）
"""
import fnmatch
import ipaddress
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tables import (
    PermissionPolicy, PolicyVersion, PolicyAttachment,
    Role, RolePermission, UserPermission, ResourcePermission,
    Agent
)


# ========== 条件操作符 ==========

class ConditionEvaluator:
    """
    AWS IAM 风格的条件评估器

    支持的操作符：
    - StringEquals / StringNotEquals
    - StringEqualsIgnoreCase / StringNotEqualsIgnoreCase
    - StringLike / StringNotLike
    - NumericEquals / NumericNotEquals
    - NumericGreaterThan / NumericGreaterThanOrEqual
    - NumericLessThan / NumericLessThanOrEqual
    - DateGreaterThan / DateGreaterThanOrEqual
    - DateLessThan / DateLessThanOrEqual
    - IpAddress / NotIpAddress
    - Bool
    - Null
    - ArnLike / ArnNotLike
    - StringContains / ForAnyValue:StringEquals / ForAllValues:StringEquals
    """

    @staticmethod
    def evaluate(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        评估条件块

        Args:
            condition: 条件块，如 {"StringEquals": {"category": "技术"}}
            context: 请求上下文，如 {"category": "技术", "source_ip": "10.0.0.1"}

        Returns:
            bool: 条件是否满足
        """
        if not condition:
            return True  # 空条件 = 无条件

        for operator, conditions in condition.items():
            if not ConditionEvaluator._evaluate_operator(operator, conditions, context):
                return False

        return True

    @staticmethod
    def _evaluate_operator(operator: str, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """评估单个操作符"""
        handler = ConditionEvaluator._OPERATORS.get(operator)
        if handler:
            return handler(conditions, context)

        # 尝试处理 ForAnyValue:xxx 和 ForAllValues:xxx 格式
        if operator.startswith("ForAnyValue:"):
            base_op = operator[len("ForAnyValue:"):]
            return ConditionEvaluator._for_any_value(base_op, conditions, context)
        elif operator.startswith("ForAllValues:"):
            base_op = operator[len("ForAllValues:"):]
            return ConditionEvaluator._for_all_values(base_op, conditions, context)

        # 未知操作符，默认通过
        return True

    @staticmethod
    def _string_equals(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if str(actual) != str(expected):
                return False
        return True

    @staticmethod
    def _string_not_equals(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if str(actual) == str(expected):
                return False
        return True

    @staticmethod
    def _string_equals_ignore_case(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if str(actual).lower() != str(expected).lower():
                return False
        return True

    @staticmethod
    def _string_not_equals_ignore_case(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if str(actual).lower() == str(expected).lower():
                return False
        return True

    @staticmethod
    def _string_like(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """支持通配符匹配 (* 和 ?)"""
        for key, pattern in conditions.items():
            actual = str(context.get(key, ""))
            if not fnmatch.fnmatch(actual, str(pattern)):
                return False
        return True

    @staticmethod
    def _string_not_like(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, pattern in conditions.items():
            actual = str(context.get(key, ""))
            if fnmatch.fnmatch(actual, str(pattern)):
                return False
        return True

    @staticmethod
    def _string_contains(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, substring in conditions.items():
            actual = str(context.get(key, ""))
            if str(substring) not in actual:
                return False
        return True

    @staticmethod
    def _numeric_equals(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if float(actual) != float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _numeric_not_equals(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if float(actual) == float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _numeric_greater_than(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if not float(actual) > float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _numeric_greater_than_or_equal(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if not float(actual) >= float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _numeric_less_than(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if not float(actual) < float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _numeric_less_than_or_equal(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                if not float(actual) <= float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _date_greater_than(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                actual_dt = actual if isinstance(actual, datetime) else datetime.fromisoformat(str(actual))
                expected_dt = expected if isinstance(expected, datetime) else datetime.fromisoformat(str(expected))
                if not actual_dt > expected_dt:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _date_greater_than_or_equal(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                actual_dt = actual if isinstance(actual, datetime) else datetime.fromisoformat(str(actual))
                expected_dt = expected if isinstance(expected, datetime) else datetime.fromisoformat(str(expected))
                if not actual_dt >= expected_dt:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _date_less_than(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                actual_dt = actual if isinstance(actual, datetime) else datetime.fromisoformat(str(actual))
                expected_dt = expected if isinstance(expected, datetime) else datetime.fromisoformat(str(expected))
                if not actual_dt < expected_dt:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _date_less_than_or_equal(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            try:
                actual_dt = actual if isinstance(actual, datetime) else datetime.fromisoformat(str(actual))
                expected_dt = expected if isinstance(expected, datetime) else datetime.fromisoformat(str(expected))
                if not actual_dt <= expected_dt:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _ip_address(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, cidr in conditions.items():
            actual = context.get(key)
            try:
                ip = ipaddress.ip_address(str(actual))
                network = ipaddress.ip_network(str(cidr), strict=False)
                if ip not in network:
                    return False
            except (ValueError, TypeError):
                return False
        return True

    @staticmethod
    def _not_ip_address(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, cidr in conditions.items():
            actual = context.get(key)
            try:
                ip = ipaddress.ip_address(str(actual))
                network = ipaddress.ip_network(str(cidr), strict=False)
                if ip in network:
                    return False
            except (ValueError, TypeError):
                return False
        return True

    @staticmethod
    def _bool(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, expected in conditions.items():
            actual = context.get(key)
            if isinstance(expected, bool):
                if actual != expected:
                    return False
            elif str(expected).lower() == "true":
                if not actual:
                    return False
            elif str(expected).lower() == "false":
                if actual:
                    return False
        return True

    @staticmethod
    def _null(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Null: true 表示键不存在，false 表示键存在"""
        for key, expected in conditions.items():
            exists = key in context and context[key] is not None
            if bool(expected) == exists:  # Null: true -> 不应该存在
                return False
        return True

    @staticmethod
    def _arn_like(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, pattern in conditions.items():
            actual = str(context.get(key, ""))
            if not fnmatch.fnmatch(actual, str(pattern)):
                return False
        return True

    @staticmethod
    def _arn_not_like(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        for key, pattern in conditions.items():
            actual = str(context.get(key, ""))
            if fnmatch.fnmatch(actual, str(pattern)):
                return False
        return True

    @staticmethod
    def _for_any_value(operator: str, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """ForAnyValue: 至少一个元素满足条件"""
        base_handler = ConditionEvaluator._OPERATORS.get(operator)
        if not base_handler:
            return True

        for key, expected in conditions.items():
            actual = context.get(key, [])
            if not isinstance(actual, (list, tuple)):
                actual = [actual]

            found = False
            for item in actual:
                if base_handler({key: expected}, {key: item}):
                    found = True
                    break

            if not found:
                return False

        return True

    @staticmethod
    def _for_all_values(operator: str, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """ForAllValues: 所有元素都满足条件"""
        base_handler = ConditionEvaluator._OPERATORS.get(operator)
        if not base_handler:
            return True

        for key, expected in conditions.items():
            actual = context.get(key, [])
            if not isinstance(actual, (list, tuple)):
                actual = [actual]

            for item in actual:
                if not base_handler({key: expected}, {key: item}):
                    return False

        return True

    # 操作符映射
    _OPERATORS = {
        "StringEquals": _string_equals,
        "StringNotEquals": _string_not_equals,
        "StringEqualsIgnoreCase": _string_equals_ignore_case,
        "StringNotEqualsIgnoreCase": _string_not_equals_ignore_case,
        "StringLike": _string_like,
        "StringNotLike": _string_not_like,
        "StringContains": _string_contains,
        "NumericEquals": _numeric_equals,
        "NumericNotEquals": _numeric_not_equals,
        "NumericGreaterThan": _numeric_greater_than,
        "NumericGreaterThanOrEqual": _numeric_greater_than_or_equal,
        "NumericLessThan": _numeric_less_than,
        "NumericLessThanOrEqual": _numeric_less_than_or_equal,
        "DateGreaterThan": _date_greater_than,
        "DateGreaterThanOrEqual": _date_greater_than_or_equal,
        "DateLessThan": _date_less_than,
        "DateLessThanOrEqual": _date_less_than_or_equal,
        "IpAddress": _ip_address,
        "NotIpAddress": _not_ip_address,
        "Bool": _bool,
        "Null": _null,
        "ArnLike": _arn_like,
        "ArnNotLike": _arn_not_like,
    }


# ========== 策略评估引擎 ==========

class PolicyEvaluator:
    """
    策略评估引擎

    AWS IAM 评估逻辑：
    1. 默认隐式 Deny
    2. 检查所有附加的策略
    3. 显式 Deny 优先于 Allow
    4. 如果没有显式 Allow，则隐式 Deny
    """

    @staticmethod
    def evaluate_policies(
        policies: List[Dict[str, Any]],
        action: str,
        resource: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        评估多个策略

        Args:
            policies: 策略文档列表
            action: 请求的操作，如 "memory:get"
            resource: 请求的资源，如 "memory:mem_xxx"
            context: 请求上下文

        Returns:
            Tuple[bool, str]: (是否允许, 原因)
        """
        has_explicit_allow = False
        deny_reason = None

        for policy_doc in policies:
            effect, reason = PolicyEvaluator._evaluate_single_policy(policy_doc, action, resource, context)

            if effect == "Deny":
                # 显式 Deny 优先
                return False, reason or "Explicit deny"
            elif effect == "Allow":
                has_explicit_allow = True
                if not deny_reason:
                    deny_reason = reason

        if has_explicit_allow:
            return True, deny_reason or "Explicit allow"

        # 隐式 Deny
        return False, "No matching allow statement"

    @staticmethod
    def _evaluate_single_policy(
        policy_doc: Dict[str, Any],
        action: str,
        resource: str,
        context: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        评估单个策略文档

        Returns:
            Tuple[Optional[str], Optional[str]]: (Effect, Reason) 或 (None, None)
        """
        statements = policy_doc.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            effect = PolicyEvaluator._evaluate_statement(stmt, action, resource, context)
            if effect:
                return effect, stmt.get("Sid", "")

        return None, None

    @staticmethod
    def _evaluate_statement(
        stmt: Dict[str, Any],
        action: str,
        resource: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        评估单个 Statement

        Returns:
            Optional[str]: "Allow" / "Deny" / None（不匹配）
        """
        # 1. 检查 Action 是否匹配
        if not PolicyEvaluator._action_matches(action, stmt.get("Action", []), stmt.get("NotAction", [])):
            return None

        # 2. 检查 Resource 是否匹配
        if not PolicyEvaluator._resource_matches(resource, stmt.get("Resource", []), stmt.get("NotResource", [])):
            return None

        # 3. 检查条件
        condition = stmt.get("Condition", {})
        if condition and not ConditionEvaluator.evaluate(condition, context):
            return None

        # 返回 Effect
        return stmt.get("Effect")

    @staticmethod
    def _action_matches(requested_action: str, actions: Any, not_actions: Any) -> bool:
        """检查 Action 是否匹配（支持通配符）"""
        # NotAction 优先
        if not_actions:
            if isinstance(not_actions, str):
                not_actions = [not_actions]
            for pattern in not_actions:
                if fnmatch.fnmatch(requested_action, pattern):
                    return False
            return True

        if not actions:
            return False

        if isinstance(actions, str):
            actions = [actions]

        for pattern in actions:
            if fnmatch.fnmatch(requested_action, pattern):
                return True

        return False

    @staticmethod
    def _resource_matches(requested_resource: str, resources: Any, not_resources: Any) -> bool:
        """检查 Resource 是否匹配（支持通配符）"""
        # NotResource 优先
        if not_resources:
            if isinstance(not_resources, str):
                not_resources = [not_resources]
            for pattern in not_resources:
                if fnmatch.fnmatch(requested_resource, pattern):
                    return False
            return True

        if not resources:
            return False

        if isinstance(resources, str):
            resources = [resources]

        for pattern in resources:
            if fnmatch.fnmatch(requested_resource, pattern):
                return True

        return False


# ========== 策略服务 ==========

class PolicyService:
    """策略服务 - AWS IAM 风格"""

    MAX_VERSIONS = 5  # 最多保留版本数

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 策略 CRUD ==========

    async def create_policy(
        self,
        name: str,
        policy_document: Dict[str, Any],
        description: Optional[str] = None,
        policy_type: str = "custom",
        created_by_agent_id: Optional[str] = None
    ) -> PermissionPolicy:
        """
        创建策略

        Args:
            name: 策略名称
            policy_document: AWS IAM 风格的策略文档
            description: 策略描述
            policy_type: 策略类型 (managed/custom/inline)
            created_by_agent_id: 创建者ID

        Returns:
            PermissionPolicy: 创建的策略
        """
        # 验证策略文档格式
        self._validate_policy_document(policy_document)

        # 创建策略
        policy = PermissionPolicy(
            name=name,
            description=description,
            policy_type=policy_type,
            policy_document=policy_document,
            created_by_agent_id=created_by_agent_id
        )
        self.db.add(policy)
        await self.db.flush()

        # 创建初始版本
        version = PolicyVersion(
            policy_id=policy.policy_id,
            version_number=1,
            is_default=True,
            policy_document=policy_document,
            changelog="Initial version"
        )
        self.db.add(version)
        await self.db.flush()

        # 更新策略的默认版本ID
        policy.default_version_id = version.version_id

        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def get_policy(self, policy_id: str) -> Optional[PermissionPolicy]:
        """获取策略"""
        query = select(PermissionPolicy).where(PermissionPolicy.policy_id == policy_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_policies(
        self,
        policy_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_system: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        列出策略

        Args:
            policy_type: 过滤策略类型
            is_active: 是否仅显示激活的
            is_system: 是否仅显示系统的
            page: 页码
            page_size: 每页数量

        Returns:
            Dict: 分页策略列表
        """
        query = select(PermissionPolicy)

        if policy_type:
            query = query.where(PermissionPolicy.policy_type == policy_type)
        if is_active is not None:
            query = query.where(PermissionPolicy.is_active == is_active)
        if is_system is not None:
            query = query.where(PermissionPolicy.is_system == is_system)

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        # 分页
        query = query.order_by(PermissionPolicy.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        policies = result.scalars().all()

        return {
            "policies": policies,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def update_policy(
        self,
        policy_id: str,
        policy_document: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        changelog: Optional[str] = None,
        actor_agent_id: Optional[str] = None
    ) -> Optional[PermissionPolicy]:
        """
        更新策略

        如果更新 policy_document，会自动创建新版本
        """
        policy = await self.get_policy(policy_id)
        if not policy:
            return None

        if policy.is_system:
            raise ValueError("Cannot update system policy")

        # 更新基本信息
        if name is not None:
            policy.name = name
        if description is not None:
            policy.description = description
        if is_active is not None:
            policy.is_active = is_active

        # 更新策略文档（创建新版本）
        if policy_document is not None:
            self._validate_policy_document(policy_document)

            # 获取当前最大版本号
            query = select(func.max(PolicyVersion.version_number)).where(
                PolicyVersion.policy_id == policy_id
            )
            result = await self.db.execute(query)
            max_version = result.scalar() or 0

            # 创建新版本
            new_version_number = max_version + 1
            new_version = PolicyVersion(
                policy_id=policy_id,
                version_number=new_version_number,
                is_default=True,
                policy_document=policy_document,
                changelog=changelog or f"Version {new_version_number}"
            )
            self.db.add(new_version)
            await self.db.flush()

            # 将旧版本设为非默认
            query = select(PolicyVersion).where(
                and_(
                    PolicyVersion.policy_id == policy_id,
                    PolicyVersion.is_default == True,
                    PolicyVersion.version_id != new_version.version_id
                )
            )
            result = await self.db.execute(query)
            old_default = result.scalar_one_or_none()
            if old_default:
                old_default.is_default = False

            # 更新策略
            policy.policy_document = policy_document
            policy.default_version_id = new_version.version_id
            policy.version_count = new_version_number

            # 清理旧版本（保留最多 MAX_VERSIONS 个）
            await self._cleanup_old_versions(policy_id)

        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def delete_policy(self, policy_id: str) -> bool:
        """删除策略"""
        policy = await self.get_policy(policy_id)
        if not policy:
            return False

        if policy.is_system:
            raise ValueError("Cannot delete system policy")

        if policy.attachment_count > 0:
            raise ValueError("Cannot delete policy with attachments")

        await self.db.delete(policy)
        await self.db.commit()
        return True

    # ========== 策略版本管理 ==========

    async def get_policy_versions(self, policy_id: str) -> List[PolicyVersion]:
        """获取策略的所有版本"""
        query = select(PolicyVersion).where(
            PolicyVersion.policy_id == policy_id
        ).order_by(PolicyVersion.version_number.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def set_default_version(self, policy_id: str, version_id: str) -> bool:
        """设置默认版本"""
        # 验证版本存在
        query = select(PolicyVersion).where(
            and_(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version_id == version_id
            )
        )
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()
        if not version:
            return False

        # 将旧默认版本取消
        query = select(PolicyVersion).where(
            and_(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.is_default == True
            )
        )
        result = await self.db.execute(query)
        old_default = result.scalar_one_or_none()
        if old_default:
            old_default.is_default = False

        # 设置新默认版本
        version.is_default = True

        # 更新策略文档
        policy = await self.get_policy(policy_id)
        if policy:
            policy.policy_document = version.policy_document
            policy.default_version_id = version_id

        await self.db.commit()
        return True

    # ========== 策略附加 ==========

    async def attach_policy(
        self,
        policy_id: str,
        agent_id: Optional[str] = None,
        role_id: Optional[str] = None,
        attachment_type: str = "managed",
        resource_scope: Optional[Dict[str, Any]] = None,
        condition_overrides: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        created_by_agent_id: Optional[str] = None
    ) -> PolicyAttachment:
        """
        附加策略到用户或角色

        Args:
            policy_id: 策略ID
            agent_id: 用户ID（与 role_id 二选一）
            role_id: 角色ID（与 agent_id 二选一）
            attachment_type: 附加类型 (managed/inline)
            resource_scope: 资源范围限制
            condition_overrides: 条件覆盖
            expires_at: 过期时间
            created_by_agent_id: 操作者ID

        Returns:
            PolicyAttachment: 附加记录
        """
        if not agent_id and not role_id:
            raise ValueError("Must specify agent_id or role_id")

        # 检查策略是否存在
        policy = await self.get_policy(policy_id)
        if not policy:
            raise ValueError(f"Policy not found: {policy_id}")

        # 检查是否已附加
        query = select(PolicyAttachment).where(
            and_(
                PolicyAttachment.policy_id == policy_id,
                or_(
                    PolicyAttachment.agent_id == agent_id,
                    PolicyAttachment.role_id == role_id
                )
            )
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError("Policy already attached")

        # 创建附加记录
        attachment = PolicyAttachment(
            policy_id=policy_id,
            agent_id=agent_id,
            role_id=role_id,
            attachment_type=attachment_type,
            resource_scope=resource_scope,
            condition_overrides=condition_overrides,
            expires_at=expires_at,
            created_by_agent_id=created_by_agent_id
        )
        self.db.add(attachment)

        # 更新策略的附加计数
        policy.attachment_count += 1

        await self.db.commit()
        await self.db.refresh(attachment)
        return attachment

    async def detach_policy(
        self,
        policy_id: str,
        agent_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> bool:
        """分离策略"""
        query = select(PolicyAttachment).where(
            and_(
                PolicyAttachment.policy_id == policy_id,
                or_(
                    PolicyAttachment.agent_id == agent_id,
                    PolicyAttachment.role_id == role_id
                )
            )
        )
        result = await self.db.execute(query)
        attachment = result.scalar_one_or_none()
        if not attachment:
            return False

        await self.db.delete(attachment)

        # 更新策略的附加计数
        policy = await self.get_policy(policy_id)
        if policy:
            policy.attachment_count = max(0, policy.attachment_count - 1)

        await self.db.commit()
        return True

    async def get_attached_policies(
        self,
        agent_id: Optional[str] = None,
        role_id: Optional[str] = None,
        include_expired: bool = False
    ) -> List[PolicyAttachment]:
        """获取附加到用户或角色的策略列表"""
        conditions = []
        if agent_id:
            conditions.append(PolicyAttachment.agent_id == agent_id)
        if role_id:
            conditions.append(PolicyAttachment.role_id == role_id)

        if not conditions:
            return []

        query = select(PolicyAttachment).where(
            or_(*conditions)
        ).options(selectinload(PolicyAttachment.policy))

        if not include_expired:
            query = query.where(
                or_(
                    PolicyAttachment.expires_at.is_(None),
                    PolicyAttachment.expires_at > datetime.now()
                )
            )

        result = await self.db.execute(query)
        return result.scalars().all()

    # ========== 权限检查 ==========

    async def check_permission(
        self,
        agent_id: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        检查用户是否有执行指定操作的权限

        完整的 AWS IAM 评估逻辑：
        1. 收集所有适用的策略（用户策略 + 角色策略 + 资源策略）
        2. 按优先级评估：显式 Deny > 显式 Allow > 隐式 Deny
        3. 返回详细的评估结果

        Args:
            agent_id: 用户ID
            action: 操作，如 "memory:get"
            resource: 资源，如 "memory:mem_xxx"
            context: 请求上下文

        Returns:
            Dict: 评估结果
        """
        if context is None:
            context = {}

        # 添加默认上下文
        context.setdefault("agent_id", agent_id)
        context.setdefault("timestamp", datetime.now().isoformat())

        # 1. 收集用户直接附加的策略
        user_policies = await self._collect_user_policies(agent_id)

        # 2. 收集角色附加的策略
        role_policies = await self._collect_role_policies(agent_id)

        # 3. 收集资源级权限（转换为策略格式）
        resource_policies = await self._collect_resource_policies(agent_id, action, resource)

        # 4. 合并所有策略
        all_policies = user_policies + role_policies + resource_policies

        # 5. 评估
        allowed, reason = PolicyEvaluator.evaluate_policies(all_policies, action, resource, context)

        return {
            "allowed": allowed,
            "reason": reason,
            "action": action,
            "resource": resource,
            "policies_evaluated": len(all_policies),
            "evaluation_details": {
                "user_policies": len(user_policies),
                "role_policies": len(role_policies),
                "resource_policies": len(resource_policies)
            }
        }

    async def _collect_user_policies(self, agent_id: str) -> List[Dict[str, Any]]:
        """收集用户直接附加的策略"""
        attachments = await self.get_attached_policies(agent_id=agent_id)
        policies = []

        for attachment in attachments:
            policy = attachment.policy
            if not policy or not policy.is_active:
                continue

            policy_doc = policy.policy_document.copy()

            # 应用资源范围限制
            if attachment.resource_scope:
                policy_doc = self._apply_resource_scope(policy_doc, attachment.resource_scope)

            # 应用条件覆盖
            if attachment.condition_overrides:
                policy_doc = self._apply_condition_overrides(policy_doc, attachment.condition_overrides)

            policies.append(policy_doc)

        return policies

    async def _collect_role_policies(self, agent_id: str) -> List[Dict[str, Any]]:
        """收集用户角色附加的策略（包括继承的角色）"""
        # 获取用户的所有角色
        user_roles = await self._get_user_roles_with_inheritance(agent_id)
        if not user_roles:
            return []

        role_ids = [role.role_id for role in user_roles]
        policies = []

        for role_id in role_ids:
            attachments = await self.get_attached_policies(role_id=role_id)
            for attachment in attachments:
                policy = attachment.policy
                if not policy or not policy.is_active:
                    continue

                policy_doc = policy.policy_document.copy()
                if attachment.resource_scope:
                    policy_doc = self._apply_resource_scope(policy_doc, attachment.resource_scope)
                if attachment.condition_overrides:
                    policy_doc = self._apply_condition_overrides(policy_doc, attachment.condition_overrides)

                policies.append(policy_doc)

        return policies

    async def _collect_resource_policies(
        self,
        agent_id: str,
        action: str,
        resource: str
    ) -> List[Dict[str, Any]]:
        """将资源级权限转换为策略格式"""
        # 解析资源
        parts = resource.split(":", 1)
        resource_type = parts[0] if len(parts) > 1 else "*"
        resource_id = parts[1] if len(parts) > 1 else resource

        # 查询资源权限
        query = select(ResourcePermission).where(
            and_(
                ResourcePermission.resource_type == resource_type,
                ResourcePermission.resource_id == resource_id,
                ResourcePermission.agent_id == agent_id,
                ResourcePermission.permission_code == action,
                ResourcePermission.grant_type == "allow",
                or_(
                    ResourcePermission.expires_at.is_(None),
                    ResourcePermission.expires_at > datetime.now()
                )
            )
        )
        result = await self.db.execute(query)
        perms = result.scalars().all()

        policies = []
        for perm in perms:
            policy_doc = {
                "Version": "2024-01-01",
                "Statement": [{
                    "Sid": f"ResourcePermission-{perm.id}",
                    "Effect": "Allow",
                    "Action": [action],
                    "Resource": [resource]
                }]
            }
            if perm.conditions:
                policy_doc["Statement"][0]["Condition"] = perm.conditions

            policies.append(policy_doc)

        return policies

    async def _get_user_roles_with_inheritance(self, agent_id: str) -> List[Role]:
        """获取用户的所有角色（包括角色继承链）"""
        # 这里简化处理，实际需要 user_roles 表
        # 暂时从 TeamMember 获取角色
        from app.models.tables import TeamMember

        query = select(TeamMember).where(
            and_(
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True
            )
        )
        result = await self.db.execute(query)
        memberships = result.scalars().all()

        # 将 team role 映射到系统角色
        role_codes = []
        for membership in memberships:
            if membership.role == "owner":
                role_codes.append("team_owner")
            elif membership.role == "admin":
                role_codes.append("team_admin")
            elif membership.role == "member":
                role_codes.append("team_member")

        if not role_codes:
            return []

        query = select(Role).where(
            and_(
                Role.code.in_(role_codes),
                Role.is_active == True
            )
        )
        result = await self.db.execute(query)
        roles = result.scalars().all()

        # 收集继承的角色
        all_roles = list(roles)
        visited = set()
        for role in roles:
            inherited = await self._collect_inherited_roles(role, visited)
            all_roles.extend(inherited)

        return all_roles

    async def _collect_inherited_roles(self, role: Role, visited: Set[str]) -> List[Role]:
        """递归收集继承的角色"""
        if role.role_id in visited:
            return []
        visited.add(role.role_id)

        inherited = []
        if role.inherit_from_id:
            query = select(Role).where(Role.role_id == role.inherit_from_id)
            result = await self.db.execute(query)
            parent = result.scalar_one_or_none()
            if parent and parent.is_active:
                inherited.append(parent)
                inherited.extend(await self._collect_inherited_roles(parent, visited))

        return inherited

    # ========== 辅助方法 ==========

    def _validate_policy_document(self, doc: Dict[str, Any]) -> None:
        """验证策略文档格式"""
        if not isinstance(doc, dict):
            raise ValueError("Policy document must be a JSON object")

        if "Statement" not in doc:
            raise ValueError("Policy document must contain 'Statement'")

        statements = doc["Statement"]
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            if not isinstance(stmt, dict):
                raise ValueError("Each statement must be a JSON object")
            if "Effect" not in stmt:
                raise ValueError("Each statement must contain 'Effect'")
            if stmt["Effect"] not in ("Allow", "Deny"):
                raise ValueError("Effect must be 'Allow' or 'Deny'")
            if "Action" not in stmt and "NotAction" not in stmt:
                raise ValueError("Each statement must contain 'Action' or 'NotAction'")

    def _apply_resource_scope(self, policy_doc: Dict[str, Any], scope: Dict[str, Any]) -> Dict[str, Any]:
        """应用资源范围限制到策略"""
        policy_doc = policy_doc.copy()
        statements = policy_doc.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            # 限制 Resource
            if "resource_ids" in scope:
                allowed_resources = scope["resource_ids"]
                current_resources = stmt.get("Resource", [])
                if isinstance(current_resources, str):
                    current_resources = [current_resources]

                # 取交集
                filtered = []
                for res in current_resources:
                    for allowed in allowed_resources:
                        if fnmatch.fnmatch(allowed, res):
                            filtered.append(allowed)
                            break

                stmt["Resource"] = filtered if filtered else current_resources

        policy_doc["Statement"] = statements
        return policy_doc

    def _apply_condition_overrides(
        self,
        policy_doc: Dict[str, Any],
        overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """应用条件覆盖"""
        policy_doc = policy_doc.copy()
        statements = policy_doc.get("Statement", [])
        if not isinstance(statements, list):
            statements = [statements]

        for stmt in statements:
            existing_condition = stmt.get("Condition", {})
            # 合并条件
            merged = {**existing_condition, **overrides}
            stmt["Condition"] = merged

        policy_doc["Statement"] = statements
        return policy_doc

    async def _cleanup_old_versions(self, policy_id: str) -> None:
        """清理旧版本，保留最多 MAX_VERSIONS 个"""
        query = select(PolicyVersion).where(
            PolicyVersion.policy_id == policy_id
        ).order_by(PolicyVersion.version_number.desc())

        result = await self.db.execute(query)
        versions = result.scalars().all()

        if len(versions) > self.MAX_VERSIONS:
            for version in versions[self.MAX_VERSIONS:]:
                if not version.is_default:
                    await self.db.delete(version)
