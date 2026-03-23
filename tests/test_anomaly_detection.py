"""异常检测和告警测试"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.tables import (
    Agent, AnomalyEvent, AnomalyAlert, AnomalyRule, AuditLog,
    Transaction, SearchLog
)
from app.services.anomaly_rules import (
    RemoteLoginRule, FrequentFailedLoginRule,
    LargeAmountTransactionRule, FrequentTransactionRule,
    SensitiveWordQueryRule, AnomalyRuleFactory
)
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.anomaly_alerting_service import AnomalyAlertingService


@pytest.fixture
def test_agent(db: Session):
    """创建测试用户"""
    agent = Agent(
        name="Test Agent",
        description="Test agent for anomaly detection",
        api_key="test_anomaly_api_key",
        credits=1000
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def detection_service(db: Session):
    """创建检测服务"""
    service = AnomalyDetectionService(db)
    service.initialize_default_rules()
    return service


@pytest.fixture
def alerting_service(db: Session):
    """创建告警服务"""
    return AnomalyAlertingService(db)


# ============== 异常检测规则测试 ==============

def test_remote_login_rule(db: Session, test_agent: Agent):
    """测试异地登录检测规则"""
    # 创建历史登录记录
    for i in range(5):
        log = AuditLog(
            actor_agent_id=test_agent.agent_id,
            action_type="login",
            action_category="auth",
            status="success",
            ip_address=f"192.168.1.{i}",
            request_data={"location": {"country": "China", "city": "Beijing"}}
        )
        db.add(log)

    db.commit()

    # 创建规则实例
    rule_config = {
        "rule_id": "test_remote_login",
        "name": "异地登录检测",
        "anomaly_type": "login",
        "anomaly_subtype": "remote_login",
        "detection_logic": {},
        "threshold_config": {"max_new_ip_count": 3},
        "alert_severity": "warning"
    }
    rule = RemoteLoginRule(rule_config)

    # 测试正常登录（历史IP）
    event_data = {
        "agent_id": test_agent.agent_id,
        "ip_address": "192.168.1.0",
        "location": {"country": "China", "city": "Beijing"}
    }
    result = rule.check(event_data, db)
    assert result is None

    # 测试异常登录（新IP，超过阈值）
    for i in range(4):
        event_data = {
            "agent_id": test_agent.agent_id,
            "ip_address": f"10.0.0.{i}",
            "location": {"country": "USA", "city": "New York"}
        }
        result = rule.check(event_data, db)

    assert result is not None
    assert result["title"] == "异地登录异常"
    assert "confidence" in result


def test_frequent_failed_login_rule(db: Session, test_agent: Agent):
    """测试频繁登录失败检测规则"""
    # 创建规则实例
    rule_config = {
        "rule_id": "test_frequent_failed",
        "name": "频繁登录失败检测",
        "anomaly_type": "login",
        "anomaly_subtype": "frequent_failed_login",
        "detection_logic": {},
        "threshold_config": {
            "max_failed_attempts": 5,
            "time_window_minutes": 15
        },
        "alert_severity": "critical"
    }
    rule = FrequentFailedLoginRule(rule_config)

    # 创建失败的登录记录
    ip_address = "10.0.0.1"
    for i in range(6):
        log = AuditLog(
            actor_agent_id=test_agent.agent_id,
            action_type="login",
            action_category="auth",
            status="failure",
            ip_address=ip_address
        )
        db.add(log)

    db.commit()

    # 测试异常检测
    event_data = {
        "agent_id": test_agent.agent_id,
        "ip_address": ip_address
    }
    result = rule.check(event_data, db)

    assert result is not None
    assert result["title"] == "频繁登录失败"
    assert result["evidence"]["failed_by_ip"] >= 5


def test_large_amount_transaction_rule(db: Session, test_agent: Agent):
    """测试大额交易检测规则"""
    # 创建历史交易
    for i in range(10):
        tx = Transaction(
            agent_id=test_agent.agent_id,
            tx_type="purchase",
            amount=-(i * 100 + 100),  # 支出100-1000分
            balance_after=1000 - (i * 100 + 100),
            description=f"Test transaction {i}"
        )
        db.add(tx)

    db.commit()

    # 创建规则实例
    rule_config = {
        "rule_id": "test_large_amount",
        "name": "大额交易检测",
        "anomaly_type": "transaction",
        "anomaly_subtype": "large_amount",
        "detection_logic": {},
        "threshold_config": {
            "threshold": 100000,
            "use_relative_threshold": True
        },
        "alert_severity": "warning"
    }
    rule = LargeAmountTransactionRule(rule_config)

    # 测试正常交易
    event_data = {
        "agent_id": test_agent.agent_id,
        "amount": 5000,
        "tx_type": "purchase"
    }
    result = rule.check(event_data, db)
    assert result is None

    # 测试大额交易
    event_data = {
        "agent_id": test_agent.agent_id,
        "amount": 120000,
        "tx_type": "purchase"
    }
    result = rule.check(event_data, db)
    assert result is not None
    assert result["title"] == "大额交易异常"


def test_sensitive_word_query_rule(db: Session):
    """测试敏感词查询检测规则"""
    # 创建规则实例
    rule_config = {
        "rule_id": "test_sensitive_word",
        "name": "敏感词查询检测",
        "anomaly_type": "query",
        "anomaly_subtype": "sensitive_word",
        "detection_logic": {
            "sensitive_words": ["password", "token", "key", "secret"]
        },
        "threshold_config": {},
        "alert_severity": "warning"
    }
    rule = SensitiveWordQueryRule(rule_config)

    # 测试正常查询
    event_data = {"query": "如何优化视频标题"}
    result = rule.check(event_data, db)
    assert result is None

    # 测试敏感词查询
    event_data = {"query": "如何获取用户的password"}
    result = rule.check(event_data, db)
    assert result is not None
    assert result["title"] == "敏感词查询异常"
    assert "password" in result["evidence"]["found_words"]


def test_rule_factory():
    """测试规则工厂"""
    # 测试支持的规则列表
    supported_rules = AnomalyRuleFactory.get_supported_rules()
    assert "remote_login" in supported_rules
    assert "frequent_failed_login" in supported_rules
    assert "large_amount_transaction" in supported_rules

    # 测试创建规则实例
    rule_config = {
        "rule_id": "test_rule",
        "name": "Test Rule",
        "anomaly_type": "login",
        "anomaly_subtype": "remote_login",
        "detection_logic": {},
        "threshold_config": {},
        "alert_severity": "warning"
    }

    rule = AnomalyRuleFactory.create_rule(rule_config)
    assert isinstance(rule, RemoteLoginRule)


# ============== 异常检测引擎测试 ==============

def test_anomaly_detection_service_check_event(
    db: Session,
    test_agent: Agent,
    detection_service: AnomalyDetectionService
):
    """测试异常检测服务"""
    # 创建登录失败记录
    for i in range(6):
        log = AuditLog(
            actor_agent_id=test_agent.agent_id,
            action_type="login",
            action_category="auth",
            status="failure",
            ip_address="10.0.0.1"
        )
        db.add(log)

    db.commit()

    # 检测事件
    event_data = {
        "agent_id": test_agent.agent_id,
        "ip_address": "10.0.0.1"
    }

    anomalies = detection_service.check_event(event_data)
    assert len(anomalies) > 0

    # 验证异常内容
    anomaly = anomalies[0]
    assert "title" in anomaly
    assert "confidence" in anomaly
    assert anomaly["agent_id"] == test_agent.agent_id


def test_anomaly_detection_service_create_events(
    db: Session,
    test_agent: Agent,
    detection_service: AnomalyDetectionService
):
    """测试创建异常事件"""
    # 创建登录失败记录
    for i in range(6):
        log = AuditLog(
            actor_agent_id=test_agent.agent_id,
            action_type="login",
            action_category="auth",
            status="failure",
            ip_address="10.0.0.1"
        )
        db.add(log)

    db.commit()

    # 检测并创建事件
    event_data = {
        "agent_id": test_agent.agent_id,
        "ip_address": "10.0.0.1"
    }

    events = detection_service.detect_and_create_events(event_data)

    # 验证创建的事件
    assert len(events) > 0
    event = events[0]
    assert event.event_id is not None
    assert event.status == "new"
    assert event.detected_at is not None


def test_anomaly_detection_service_confirm_anomaly(
    db: Session,
    detection_service: AnomalyDetectionService,
    test_agent: Agent
):
    """测试确认异常"""
    # 创建测试异常事件
    event = AnomalyEvent(
        anomaly_type="login",
        anomaly_subtype="frequent_failed_login",
        severity="critical",
        title="Test Anomaly",
        description="Test anomaly description",
        status="new",
        confidence=0.9
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # 确认为真阳性
    result = detection_service.confirm_anomaly(
        event_id=event.event_id,
        is_true_positive=True,
        confirmed_by_agent_id=test_agent.agent_id,
        resolution_note="Confirmed as true positive"
    )

    assert result is not None
    assert result.status == "resolved"
    assert result.confirmed_by_agent_id == test_agent.agent_id
    assert result.resolution_note == "Confirmed as true positive"


def test_anomaly_detection_service_get_stats(
    db: Session,
    detection_service: AnomalyDetectionService
):
    """测试获取统计信息"""
    # 创建测试异常事件
    for i in range(10):
        event = AnomalyEvent(
            anomaly_type="login" if i < 5 else "transaction",
            anomaly_subtype="test",
            severity="critical" if i < 3 else "warning",
            title=f"Test Anomaly {i}",
            description="Test",
            status="new" if i < 7 else ("resolved" if i < 9 else "false_positive"),
            confidence=0.9
        )
        db.add(event)

    db.commit()

    # 获取统计信息
    stats = detection_service.get_anomaly_stats()

    assert stats["total_count"] == 10
    assert "login" in stats["by_type"]
    assert "transaction" in stats["by_type"]
    assert "critical" in stats["by_severity"]
    assert "new" in stats["by_status"]


# ============== 异常告警服务测试 ==============

def test_alerting_service_create_alerts(
    db: Session,
    detection_service: AnomalyDetectionService,
    alerting_service: AnomalyAlertingService,
    test_agent: Agent
):
    """测试创建告警"""
    # 创建异常事件
    event = AnomalyEvent(
        anomaly_type="login",
        anomaly_subtype="frequent_failed_login",
        severity="critical",
        title="Test Anomaly",
        description="Test anomaly description",
        status="new",
        confidence=0.9
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # 创建告警
    alerts = alerting_service.create_alerts_for_event(event)

    # 验证告警
    assert len(alerts) > 0
    alert = alerts[0]
    assert alert.alert_id is not None
    assert alert.event_id == event.event_id
    assert alert.status == "pending"


def test_alerting_service_acknowledge_alert(
    db: Session,
    alerting_service: AnomalyAlertingService,
    test_agent: Agent
):
    """测试确认告警"""
    # 创建测试告警
    alert = AnomalyAlert(
        event_id="test_event_id",
        title="Test Alert",
        message="Test alert message",
        severity="warning",
        channel_type="email",
        status="pending"
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # 确认告警
    result = alerting_service.acknowledge_alert(
        alert_id=alert.alert_id,
        ack_by_agent_id=test_agent.agent_id
    )

    assert result is not None
    assert result.status == "acknowledged"
    assert result.ack_by_agent_id == test_agent.agent_id


def test_alerting_service_get_stats(
    db: Session,
    alerting_service: AnomalyAlertingService
):
    """测试获取告警统计"""
    # 创建测试告警
    for i in range(10):
        alert = AnomalyAlert(
            event_id=f"test_event_{i}",
            title=f"Test Alert {i}",
            message="Test alert message",
            severity="critical" if i < 3 else "warning",
            channel_type="email" if i < 5 else "webhook",
            status="pending" if i < 7 else ("sent" if i < 9 else "failed")
        )
        db.add(alert)

    db.commit()

    # 获取统计信息
    stats = alerting_service.get_alert_stats()

    assert stats["total_count"] == 10
    assert "pending" in stats["by_status"]
    assert "sent" in stats["by_status"]
    assert "critical" in stats["by_severity"]
    assert "warning" in stats["by_severity"]
    assert "email" in stats["by_channel"]
    assert "webhook" in stats["by_channel"]


# ============== 集成测试 ==============

def test_end_to_end_anomaly_detection(
    db: Session,
    test_agent: Agent,
    detection_service: AnomalyDetectionService,
    alerting_service: AnomalyAlertingService
):
    """端到端异常检测测试"""
    # 模拟异常行为：频繁登录失败
    for i in range(7):
        log = AuditLog(
            actor_agent_id=test_agent.agent_id,
            action_type="login",
            action_category="auth",
            status="failure",
            ip_address="10.0.0.1"
        )
        db.add(log)

    db.commit()

    # 1. 检测异常
    event_data = {
        "agent_id": test_agent.agent_id,
        "ip_address": "10.0.0.1"
    }
    events = detection_service.detect_and_create_events(event_data)

    assert len(events) > 0
    event = events[0]

    # 2. 创建告警
    alerts = alerting_service.create_alerts_for_event(event)

    assert len(alerts) > 0
    alert = alerts[0]

    # 3. 验证事件状态
    assert event.status == "new"
    assert alert.status == "pending"

    # 4. 确认异常
    confirmed_event = detection_service.confirm_anomaly(
        event_id=event.event_id,
        is_true_positive=True,
        confirmed_by_agent_id=test_agent.agent_id,
        resolution_note="User account was compromised"
    )

    assert confirmed_event.status == "resolved"

    # 5. 验证规则统计
    if event.detection_rule_id:
        rule = db.query(AnomalyRule).filter(
            AnomalyRule.rule_id == event.detection_rule_id
        ).first()

        assert rule is not None
        assert rule.true_positive_count > 0


def test_accuracy_calculation(
    db: Session,
    detection_service: AnomalyDetectionService
):
    """测试准确率计算"""
    # 创建测试异常事件
    # 5个真阳性（resolved）
    for i in range(5):
        event = AnomalyEvent(
            anomaly_type="login",
            anomaly_subtype="test",
            severity="critical",
            title=f"True Positive {i}",
            description="Test",
            status="resolved",
            confidence=0.9
        )
        db.add(event)

    # 2个假阳性（false_positive）
    for i in range(2):
        event = AnomalyEvent(
            anomaly_type="login",
            anomaly_subtype="test",
            severity="warning",
            title=f"False Positive {i}",
            description="Test",
            status="false_positive",
            confidence=0.7
        )
        db.add(event)

    # 3个未确认（new）
    for i in range(3):
        event = AnomalyEvent(
            anomaly_type="login",
            anomaly_subtype="test",
            severity="info",
            title=f"Unconfirmed {i}",
            description="Test",
            status="new",
            confidence=0.6
        )
        db.add(event)

    db.commit()

    # 获取统计信息
    stats = detection_service.get_anomaly_stats()

    # 准确率 = 真阳性 / (真阳性 + 假阳性) = 5/7 ≈ 71.4%
    assert stats["accuracy"] is not None
    expected_accuracy = 5 / 7
    assert abs(stats["accuracy"] - expected_accuracy) < 0.01


@pytest.mark.parametrize("anomaly_type", ["login", "transaction", "query", "behavior", "system"])
def test_anomaly_type_coverage(
    db: Session,
    detection_service: AnomalyDetectionService,
    anomaly_type: str
):
    """测试异常类型覆盖"""
    # 创建不同类型的异常事件
    event = AnomalyEvent(
        anomaly_type=anomaly_type,
        anomaly_subtype="test",
        severity="warning",
        title=f"Test {anomaly_type}",
        description="Test",
        status="new",
        confidence=0.8
    )
    db.add(event)
    db.commit()

    # 按类型查询
    stats = detection_service.get_anomaly_stats()

    assert anomaly_type in stats["by_type"]
    assert stats["by_type"][anomaly_type] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
