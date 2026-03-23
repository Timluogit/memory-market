"""异常检测规则模块"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models.tables import AuditLog, Transaction, Purchase, SearchLog


class AnomalyRule:
    """异常检测规则基类"""

    def __init__(self, rule_config: Dict[str, Any]):
        self.rule_id = rule_config.get("rule_id")
        self.name = rule_config.get("name")
        self.anomaly_type = rule_config.get("anomaly_type")
        self.anomaly_subtype = rule_config.get("anomaly_subtype")
        self.detection_logic = rule_config.get("detection_logic", {})
        self.threshold_config = rule_config.get("threshold_config", {})
        self.alert_severity = rule_config.get("alert_severity", "warning")

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        """
        检查事件是否异常

        Args:
            event_data: 事件数据
            db: 数据库会话

        Returns:
            如果异常，返回异常详情；否则返回 None
        """
        raise NotImplementedError("Subclass must implement check method")


class RemoteLoginRule(AnomalyRule):
    """异地登录检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")
        current_ip = event_data.get("ip_address")
        current_location = event_data.get("location", {})

        # 获取最近30天该用户的登录记录
        time_threshold = datetime.now() - timedelta(days=30)
        recent_logins = db.query(AuditLog).filter(
            AuditLog.actor_agent_id == agent_id,
            AuditLog.action_type == "login",
            AuditLog.created_at >= time_threshold
        ).all()

        # 如果是新用户（首次登录），不算异常
        if not recent_logins:
            return None

        # 提取历史IP和位置
        historical_ips = set()
        historical_locations = set()

        for login in recent_logins:
            ip = login.ip_address
            if ip:
                historical_ips.add(ip)

            # 假设位置信息存在 request_data 中
            request_data = login.request_data or {}
            location = request_data.get("location")
            if location:
                historical_locations.add(f"{location.get('country', '')}-{location.get('city', '')}")

        # 检查是否为新IP
        if current_ip and current_ip not in historical_ips:
            # 获取配置的阈值
            max_new_ip_count = self.threshold_config.get("max_new_ip_count", 3)

            # 查询最近1小时内的新IP登录次数
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_new_ip_logins = db.query(AuditLog).filter(
                AuditLog.actor_agent_id == agent_id,
                AuditLog.action_type == "login",
                AuditLog.created_at >= one_hour_ago,
                ~AuditLog.ip_address.in_(list(historical_ips))
            ).count()

            # 如果超过阈值，触发告警
            if recent_new_ip_logins >= max_new_ip_count:
                return {
                    "title": "异地登录异常",
                    "description": f"用户在短时间内从多个新IP地址登录",
                    "evidence": {
                        "current_ip": current_ip,
                        "current_location": current_location,
                        "historical_ips": list(historical_ips),
                        "historical_locations": list(historical_locations),
                        "recent_new_ip_login_count": recent_new_ip_logins
                    },
                    "confidence": 0.85
                }

        return None


class FrequentFailedLoginRule(AnomalyRule):
    """频繁失败登录检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        ip_address = event_data.get("ip_address")
        agent_id = event_data.get("agent_id")

        # 获取阈值配置
        max_failed_attempts = self.threshold_config.get("max_failed_attempts", 5)
        time_window_minutes = self.threshold_config.get("time_window_minutes", 15)

        # 查询时间窗口内的失败登录次数
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        # 按IP查询
        failed_by_ip = db.query(AuditLog).filter(
            AuditLog.action_type == "login",
            AuditLog.status == "failure",
            AuditLog.ip_address == ip_address,
            AuditLog.created_at >= time_threshold
        ).count()

        # 按用户查询
        failed_by_agent = 0
        if agent_id:
            failed_by_agent = db.query(AuditLog).filter(
                AuditLog.action_type == "login",
                AuditLog.status == "failure",
                AuditLog.actor_agent_id == agent_id,
                AuditLog.created_at >= time_threshold
            ).count()

        # 检查是否超过阈值
        if failed_by_ip >= max_failed_attempts or failed_by_agent >= max_failed_attempts:
            return {
                "title": "频繁登录失败",
                "description": f"IP或用户在短时间内频繁登录失败",
                "evidence": {
                    "ip_address": ip_address,
                    "agent_id": agent_id,
                    "failed_by_ip": failed_by_ip,
                    "failed_by_agent": failed_by_agent,
                    "max_failed_attempts": max_failed_attempts,
                    "time_window_minutes": time_window_minutes
                },
                "confidence": 0.95
            }

        return None


class LargeAmountTransactionRule(AnomalyRule):
    """大额交易检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")
        amount = event_data.get("amount", 0)
        tx_type = event_data.get("tx_type")

        # 只检查支出类型
        if tx_type not in ["purchase", "withdraw"]:
            return None

        # 获取阈值配置
        threshold = self.threshold_config.get("threshold", 100000)  # 默认1000元
        use_relative_threshold = self.threshold_config.get("use_relative_threshold", False)

        # 检查是否超过绝对阈值
        if amount >= threshold:
            confidence = 0.9

            # 如果启用相对阈值，检查相对于历史交易的情况
            if use_relative_threshold:
                # 获取该用户最近30天的平均交易金额
                time_threshold = datetime.now() - timedelta(days=30)
                recent_txs = db.query(Transaction).filter(
                    Transaction.agent_id == agent_id,
                    Transaction.tx_type == tx_type,
                    Transaction.created_at >= time_threshold
                ).all()

                if recent_txs:
                    avg_amount = sum(abs(tx.amount) for tx in recent_txs) / len(recent_txs)
                    # 如果当前交易金额是平均金额的3倍以上，提高置信度
                    if amount >= avg_amount * 3:
                        confidence = 0.98

            return {
                "title": "大额交易异常",
                "description": f"用户进行了一笔大额{tx_type}交易",
                "evidence": {
                    "agent_id": agent_id,
                    "amount": amount,
                    "tx_type": tx_type,
                    "threshold": threshold,
                    "avg_amount": avg_amount if use_relative_threshold and 'avg_amount' in locals() else None
                },
                "confidence": confidence
            }

        return None


class FrequentTransactionRule(AnomalyRule):
    """频繁交易检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")
        tx_type = event_data.get("tx_type")

        # 获取阈值配置
        max_transactions = self.threshold_config.get("max_transactions", 20)
        time_window_minutes = self.threshold_config.get("time_window_minutes", 60)

        # 查询时间窗口内的交易次数
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        transaction_count = db.query(Transaction).filter(
            Transaction.agent_id == agent_id,
            Transaction.tx_type == tx_type,
            Transaction.created_at >= time_threshold
        ).count()

        # 检查是否超过阈值
        if transaction_count >= max_transactions:
            return {
                "title": "频繁交易异常",
                "description": f"用户在短时间内进行了大量{tx_type}交易",
                "evidence": {
                    "agent_id": agent_id,
                    "tx_type": tx_type,
                    "transaction_count": transaction_count,
                    "max_transactions": max_transactions,
                    "time_window_minutes": time_window_minutes
                },
                "confidence": 0.85
            }

        return None


class SensitiveWordQueryRule(AnomalyRule):
    """敏感词查询检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        query = event_data.get("query", "")

        # 获取敏感词配置
        sensitive_words = self.detection_logic.get("sensitive_words", [])

        # 检查查询中是否包含敏感词
        found_words = []
        for word in sensitive_words:
            if word.lower() in query.lower():
                found_words.append(word)

        if found_words:
            return {
                "title": "敏感词查询异常",
                "description": f"用户查询包含敏感词",
                "evidence": {
                    "query": query,
                    "found_words": found_words
                },
                "confidence": 0.95
            }

        return None


class AbnormalQueryFrequencyRule(AnomalyRule):
    """异常查询频率检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")

        # 获取阈值配置
        max_queries = self.threshold_config.get("max_queries", 100)
        time_window_minutes = self.threshold_config.get("time_window_minutes", 60)

        # 查询时间窗口内的搜索次数
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        query_count = db.query(SearchLog).filter(
            SearchLog.agent_id == agent_id,
            SearchLog.created_at >= time_threshold
        ).count()

        # 检查是否超过阈值
        if query_count >= max_queries:
            return {
                "title": "异常查询频率",
                "description": f"用户在短时间内进行了大量查询",
                "evidence": {
                    "agent_id": agent_id,
                    "query_count": query_count,
                    "max_queries": max_queries,
                    "time_window_minutes": time_window_minutes
                },
                "confidence": 0.8
            }

        return None


class AbnormalActivityRule(AnomalyRule):
    """异常活跃度检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")

        # 获取阈值配置
        max_actions = self.threshold_config.get("max_actions", 500)
        time_window_minutes = self.threshold_config.get("time_window_minutes", 60)

        # 查询时间窗口内的审计日志数量（所有操作）
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        action_count = db.query(AuditLog).filter(
            AuditLog.actor_agent_id == agent_id,
            AuditLog.created_at >= time_threshold
        ).count()

        # 检查是否超过阈值
        if action_count >= max_actions:
            return {
                "title": "异常活跃度",
                "description": f"用户在短时间内进行了大量操作",
                "evidence": {
                    "agent_id": agent_id,
                    "action_count": action_count,
                    "max_actions": max_actions,
                    "time_window_minutes": time_window_minutes
                },
                "confidence": 0.85
            }

        return None


class AbnormalOperationRule(AnomalyRule):
    """异常操作检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")
        action_type = event_data.get("action_type")
        action_category = event_data.get("action_category")

        # 获取监控的异常操作列表
        monitored_operations = self.detection_logic.get("monitored_operations", [])

        # 检查是否为监控的操作
        operation_key = f"{action_category}.{action_type}"
        if operation_key in monitored_operations:
            # 获取阈值配置
            max_count = self.threshold_config.get("max_count", 5)
            time_window_minutes = self.threshold_config.get("time_window_minutes", 10)

            # 查询时间窗口内的操作次数
            time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

            operation_count = db.query(AuditLog).filter(
                AuditLog.actor_agent_id == agent_id,
                AuditLog.action_category == action_category,
                AuditLog.action_type == action_type,
                AuditLog.created_at >= time_threshold
            ).count()

            # 检查是否超过阈值
            if operation_count >= max_count:
                return {
                    "title": "异常操作",
                    "description": f"用户频繁执行特定操作: {operation_key}",
                    "evidence": {
                        "agent_id": agent_id,
                        "action_category": action_category,
                        "action_type": action_type,
                        "operation_count": operation_count,
                        "max_count": max_count,
                        "time_window_minutes": time_window_minutes
                    },
                    "confidence": 0.9
                }

        return None


class ErrorRateSpikeRule(AnomalyRule):
    """错误率飙升检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        # 获取阈值配置
        threshold_percent = self.threshold_config.get("threshold_percent", 10)  # 错误率阈值
        time_window_minutes = self.threshold_config.get("time_window_minutes", 10)
        min_total_requests = self.threshold_config.get("min_total_requests", 10)  # 最小请求数

        # 查询时间窗口内的审计日志
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        total_logs = db.query(AuditLog).filter(
            AuditLog.created_at >= time_threshold
        ).count()

        error_logs = db.query(AuditLog).filter(
            AuditLog.status == "failure",
            AuditLog.created_at >= time_threshold
        ).count()

        # 只在请求量足够时才检查
        if total_logs >= min_total_requests:
            error_rate = (error_logs / total_logs) * 100

            if error_rate >= threshold_percent:
                return {
                    "title": "错误率飙升",
                    "description": f"系统错误率异常升高",
                    "evidence": {
                        "total_logs": total_logs,
                        "error_logs": error_logs,
                        "error_rate": error_rate,
                        "threshold_percent": threshold_percent
                    },
                    "confidence": 0.95
                }

        return None


class LatencySpikeRule(AnomalyRule):
    """延迟飙升检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        # 延迟飙升需要从API响应时间数据中检测
        # 这里简化处理，从审计日志中提取

        # 获取阈值配置
        threshold_ms = self.threshold_config.get("threshold_ms", 5000)  # 延迟阈值（毫秒）
        time_window_minutes = self.threshold_config.get("time_window_minutes", 5)
        min_slow_requests = self.threshold_config.get("min_slow_requests", 5)  # 最小慢请求数

        # 查询时间窗口内的审计日志
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        # 从审计日志的响应数据中提取响应时间
        # 这里简化处理，实际应该有专门的性能监控表
        # 暂时返回None
        return None


class UnusualAccessPatternRule(AnomalyRule):
    """异常访问模式检测规则"""

    def check(self, event_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        agent_id = event_data.get("agent_id")
        action_category = event_data.get("action_category")
        target_type = event_data.get("target_type")

        # 获取阈值配置
        max_different_targets = self.threshold_config.get("max_different_targets", 50)
        time_window_minutes = self.threshold_config.get("time_window_minutes", 60)

        # 查询时间窗口内的审计日志
        time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)

        # 统计访问的不同目标数量
        if target_type:
            query = db.query(AuditLog.target_id).filter(
                AuditLog.actor_agent_id == agent_id,
                AuditLog.action_category == action_category,
                AuditLog.target_type == target_type,
                AuditLog.target_id.isnot(None),
                AuditLog.created_at >= time_threshold
            ).distinct()

            different_targets = query.count()

            # 检查是否超过阈值
            if different_targets >= max_different_targets:
                return {
                    "title": "异常访问模式",
                    "description": f"用户短时间内访问了大量{target_type}对象",
                    "evidence": {
                        "agent_id": agent_id,
                        "action_category": action_category,
                        "target_type": target_type,
                        "different_targets": different_targets,
                        "max_different_targets": max_different_targets
                    },
                    "confidence": 0.8
                }

        return None


# 规则工厂
class AnomalyRuleFactory:
    """异常检测规则工厂"""

    _rule_classes = {
        "remote_login": RemoteLoginRule,
        "frequent_failed_login": FrequentFailedLoginRule,
        "large_amount_transaction": LargeAmountTransactionRule,
        "frequent_transaction": FrequentTransactionRule,
        "sensitive_word_query": SensitiveWordQueryRule,
        "abnormal_query_frequency": AbnormalQueryFrequencyRule,
        "abnormal_activity": AbnormalActivityRule,
        "abnormal_operation": AbnormalOperationRule,
        "error_rate_spike": ErrorRateSpikeRule,
        "latency_spike": LatencySpikeRule,
        "unusual_access_pattern": UnusualAccessPatternRule,
    }

    @classmethod
    def create_rule(cls, rule_config: Dict[str, Any]) -> AnomalyRule:
        """根据配置创建规则实例"""
        rule_type = rule_config.get("rule_type") or rule_config.get("anomaly_subtype")

        if rule_type not in cls._rule_classes:
            raise ValueError(f"Unknown rule type: {rule_type}")

        return cls._rule_classes[rule_type](rule_config)

    @classmethod
    def get_supported_rules(cls) -> List[str]:
        """获取支持的规则列表"""
        return list(cls._rule_classes.keys())


# 默认规则配置
DEFAULT_RULES = [
    {
        "name": "异地登录检测",
        "anomaly_type": "login",
        "anomaly_subtype": "remote_login",
        "rule_type": "remote_login",
        "detection_logic": {},
        "threshold_config": {
            "max_new_ip_count": 3
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    },
    {
        "name": "频繁登录失败检测",
        "anomaly_type": "login",
        "anomaly_subtype": "frequent_failed_login",
        "rule_type": "frequent_failed_login",
        "detection_logic": {},
        "threshold_config": {
            "max_failed_attempts": 5,
            "time_window_minutes": 15
        },
        "alert_severity": "critical",
        "alert_channels": ["email", "webhook"],
        "alert_cooldown_minutes": 30
    },
    {
        "name": "大额交易检测",
        "anomaly_type": "transaction",
        "anomaly_subtype": "large_amount",
        "rule_type": "large_amount_transaction",
        "detection_logic": {},
        "threshold_config": {
            "threshold": 100000,
            "use_relative_threshold": True
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    },
    {
        "name": "频繁交易检测",
        "anomaly_type": "transaction",
        "anomaly_subtype": "frequent",
        "rule_type": "frequent_transaction",
        "detection_logic": {},
        "threshold_config": {
            "max_transactions": 20,
            "time_window_minutes": 60
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    },
    {
        "name": "敏感词查询检测",
        "anomaly_type": "query",
        "anomaly_subtype": "sensitive_word",
        "rule_type": "sensitive_word_query",
        "detection_logic": {
            "sensitive_words": ["password", "token", "key", "secret", "admin", "root"]
        },
        "threshold_config": {},
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 120
    },
    {
        "name": "异常查询频率检测",
        "anomaly_type": "query",
        "anomaly_subtype": "abnormal_frequency",
        "rule_type": "abnormal_query_frequency",
        "detection_logic": {},
        "threshold_config": {
            "max_queries": 100,
            "time_window_minutes": 60
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    },
    {
        "name": "异常活跃度检测",
        "anomaly_type": "behavior",
        "anomaly_subtype": "abnormal_activity",
        "rule_type": "abnormal_activity",
        "detection_logic": {},
        "threshold_config": {
            "max_actions": 500,
            "time_window_minutes": 60
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    },
    {
        "name": "异常操作检测",
        "anomaly_type": "behavior",
        "anomaly_subtype": "abnormal_operation",
        "rule_type": "abnormal_operation",
        "detection_logic": {
            "monitored_operations": [
                "memory.delete",
                "memory.update",
                "team.member_remove",
                "team.leave"
            ]
        },
        "threshold_config": {
            "max_count": 5,
            "time_window_minutes": 10
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 30
    },
    {
        "name": "错误率飙升检测",
        "anomaly_type": "system",
        "anomaly_subtype": "error_rate_spike",
        "rule_type": "error_rate_spike",
        "detection_logic": {},
        "threshold_config": {
            "threshold_percent": 10,
            "time_window_minutes": 10,
            "min_total_requests": 10
        },
        "alert_severity": "critical",
        "alert_channels": ["email", "webhook", "slack"],
        "alert_cooldown_minutes": 15
    },
    {
        "name": "延迟飙升检测",
        "anomaly_type": "system",
        "anomaly_subtype": "latency_spike",
        "rule_type": "latency_spike",
        "detection_logic": {},
        "threshold_config": {
            "threshold_ms": 5000,
            "time_window_minutes": 5,
            "min_slow_requests": 5
        },
        "alert_severity": "critical",
        "alert_channels": ["email", "webhook"],
        "alert_cooldown_minutes": 15
    },
    {
        "name": "异常访问模式检测",
        "anomaly_type": "behavior",
        "anomaly_subtype": "unusual_access_pattern",
        "rule_type": "unusual_access_pattern",
        "detection_logic": {},
        "threshold_config": {
            "max_different_targets": 50,
            "time_window_minutes": 60
        },
        "alert_severity": "warning",
        "alert_channels": ["email"],
        "alert_cooldown_minutes": 60
    }
]
