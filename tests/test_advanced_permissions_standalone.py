"""
高级权限系统测试 - 独立版

测试条件评估器和策略评估引擎（无需数据库/完整应用）
"""
import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.policy_service import ConditionEvaluator, PolicyEvaluator


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
        condition = {"StringEqualsIgnoreCase": {"name": "test"}}
        assert ConditionEvaluator.evaluate(condition, {"name": "TEST"}) is True
        assert ConditionEvaluator.evaluate(condition, {"name": "other"}) is False

    def test_string_like(self):
        """测试 StringLike（通配符）"""
        condition = {"StringLike": {"title": "*测试*"}}
        assert ConditionEvaluator.evaluate(condition, {"title": "这是一个测试记忆"}) is True
        assert ConditionEvaluator.evaluate(condition, {"title": "普通记忆"}) is False

    def test_string_not_like(self):
        """测试 StringNotLike"""
        condition = {"StringNotLike": {"title": "*机密*"}}
        assert ConditionEvaluator.evaluate(condition, {"title": "普通记忆"}) is True
        assert ConditionEvaluator.evaluate(condition, {"title": "机密记忆"}) is False

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

    def test_numeric_not_equals(self):
        """测试 NumericNotEquals"""
        condition = {"NumericNotEquals": {"price": 0}}
        assert ConditionEvaluator.evaluate(condition, {"price": 100}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 0}) is False

    def test_numeric_greater_than(self):
        """测试 NumericGreaterThan"""
        condition = {"NumericGreaterThan": {"price": 50}}
        assert ConditionEvaluator.evaluate(condition, {"price": 100}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 30}) is False
        assert ConditionEvaluator.evaluate(condition, {"price": 50}) is False

    def test_numeric_greater_than_or_equal(self):
        """测试 NumericGreaterThanOrEqual"""
        condition = {"NumericGreaterThanOrEqual": {"score": 4.0}}
        assert ConditionEvaluator.evaluate(condition, {"score": 4.5}) is True
        assert ConditionEvaluator.evaluate(condition, {"score": 4.0}) is True
        assert ConditionEvaluator.evaluate(condition, {"score": 3.5}) is False

    def test_numeric_less_than(self):
        """测试 NumericLessThan"""
        condition = {"NumericLessThan": {"price": 100}}
        assert ConditionEvaluator.evaluate(condition, {"price": 50}) is True
        assert ConditionEvaluator.evaluate(condition, {"price": 150}) is False

    def test_numeric_less_than_or_equal(self):
        """测试 NumericLessThanOrEqual"""
        condition = {"NumericLessThanOrEqual": {"attempts": 3}}
        assert ConditionEvaluator.evaluate(condition, {"attempts": 2}) is True
        assert ConditionEvaluator.evaluate(condition, {"attempts": 3}) is True
        assert ConditionEvaluator.evaluate(condition, {"attempts": 4}) is False

    def test_ip_address(self):
        """测试 IpAddress"""
        condition = {"IpAddress": {"source_ip": "10.0.0.0/8"}}
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "10.0.0.1"}) is True
        assert ConditionEvaluator.evaluate(condition, {"source_ip": "10.255.255.255"}) is True
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

    def test_date_less_than(self):
        """测试 DateLessThan"""
        condition = {"DateLessThan": {"expires_at": "2024-12-31T23:59:59"}}
        assert ConditionEvaluator.evaluate(condition, {"expires_at": "2024-06-01T00:00:00"}) is True
        assert ConditionEvaluator.evaluate(condition, {"expires_at": "2025-01-01T00:00:00"}) is False

    def test_multiple_conditions_and_logic(self):
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

    def test_arn_not_like(self):
        """测试 ArnNotLike"""
        condition = {"ArnNotLike": {"resource": "memory:mem_secret*"}}
        assert ConditionEvaluator.evaluate(condition, {"resource": "memory:mem_public"}) is True
        assert ConditionEvaluator.evaluate(condition, {"resource": "memory:mem_secret_123"}) is False

    def test_empty_condition(self):
        """测试空条件"""
        assert ConditionEvaluator.evaluate({}, {"any": "value"}) is True

    def test_missing_key_in_context(self):
        """测试上下文中缺少键"""
        condition = {"StringEquals": {"category": "技术"}}
        assert ConditionEvaluator.evaluate(condition, {}) is False  # 缺失键 != 预期值


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

    def test_multiple_statements(self):
        """测试多个 Statement"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [
                {
                    "Sid": "AllowRead",
                    "Effect": "Allow",
                    "Action": ["memory:get", "memory:list"],
                    "Resource": ["memory:*"]
                },
                {
                    "Sid": "DenyDelete",
                    "Effect": "Deny",
                    "Action": ["memory:delete"],
                    "Resource": ["memory:*"]
                }
            ]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is True

        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:delete", "memory:mem_123", {}
        )
        assert allowed is False

    def test_no_matching_action(self):
        """测试无匹配 Action"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["team:manage"],
                "Resource": ["team:*"]
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is False

    def test_no_matching_resource(self):
        """测试无匹配 Resource"""
        policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:get"],
                "Resource": ["memory:mem_specific"]
            }]
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_other", {}
        )
        assert allowed is False

    def test_empty_statement(self):
        """测试空 Statement"""
        policy = {
            "Version": "2024-01-01",
            "Statement": []
        }
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [policy], "memory:get", "memory:mem_123", {}
        )
        assert allowed is False

    def test_complex_scenario(self):
        """测试复杂场景：多策略、多条件"""
        allow_policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["memory:*"],
                "Resource": ["memory:*"],
                "Condition": {
                    "StringEquals": {"department": "engineering"}
                }
            }]
        }
        deny_policy = {
            "Version": "2024-01-01",
            "Statement": [{
                "Effect": "Deny",
                "Action": ["memory:delete"],
                "Resource": ["memory:mem_critical_*"]
            }]
        }

        # 满足条件，非关键资源
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [allow_policy, deny_policy],
            "memory:get",
            "memory:mem_normal",
            {"department": "engineering"}
        )
        assert allowed is True

        # 满足条件，但删除关键资源被拒绝
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [allow_policy, deny_policy],
            "memory:delete",
            "memory:mem_critical_data",
            {"department": "engineering"}
        )
        assert allowed is False

        # 不满足条件
        allowed, _ = PolicyEvaluator.evaluate_policies(
            [allow_policy, deny_policy],
            "memory:get",
            "memory:mem_normal",
            {"department": "marketing"}
        )
        assert allowed is False


# ========== 运行入口 ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
