"""异常检测服务"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models.tables import AnomalyEvent, AnomalyRule
from app.services.anomaly_rules import AnomalyRuleFactory, DEFAULT_RULES
import json


class AnomalyDetectionService:
    """异常检测服务"""

    def __init__(self, db: Session):
        self.db = db

    def check_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检查单个事件是否异常

        Args:
            event_data: 事件数据

        Returns:
            异常列表
        """
        anomalies = []

        # 获取所有启用的规则
        rules = self.db.query(AnomalyRule).filter(
            AnomalyRule.is_enabled == True
        ).all()

        for rule in rules:
            try:
                # 创建规则实例
                rule_instance = AnomalyRuleFactory.create_rule({
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "anomaly_type": rule.anomaly_type,
                    "anomaly_subtype": rule.anomaly_subtype,
                    "detection_logic": rule.detection_logic,
                    "threshold_config": rule.threshold_config,
                    "alert_severity": rule.alert_severity
                })

                # 检查事件
                result = rule_instance.check(event_data, self.db)

                if result:
                    anomalies.append({
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "anomaly_type": rule.anomaly_type,
                        "anomaly_subtype": rule.anomaly_subtype,
                        **result
                    })

            except Exception as e:
                print(f"Error checking rule {rule.rule_id}: {e}")
                continue

        return anomalies

    def detect_and_create_events(self, event_data: Dict[str, Any]) -> List[AnomalyEvent]:
        """
        检测事件并创建异常记录

        Args:
            event_data: 事件数据

        Returns:
            创建的异常事件列表
        """
        anomalies = self.check_event(event_data)

        created_events = []

        for anomaly in anomalies:
            # 检查告警冷却时间
            if self._is_in_cooldown(anomaly):
                continue

            # 创建异常事件
            event = AnomalyEvent(
                anomaly_type=anomaly["anomaly_type"],
                anomaly_subtype=anomaly["anomaly_subtype"],
                severity="critical" if anomaly["confidence"] >= 0.9 else ("warning" if anomaly["confidence"] >= 0.7 else "info"),
                target_type=event_data.get("target_type"),
                target_id=event_data.get("target_id"),
                title=anomaly["title"],
                description=anomaly["description"],
                evidence=anomaly["evidence"],
                detection_rule_id=anomaly["rule_id"],
                confidence=anomaly["confidence"]
            )

            self.db.add(event)

            # 更新规则统计
            self._update_rule_stats(anomaly["rule_id"])

            created_events.append(event)

        self.db.commit()

        return created_events

    def _is_in_cooldown(self, anomaly: Dict[str, Any]) -> bool:
        """检查是否在冷却时间内"""
        rule_id = anomaly["rule_id"]
        rule = self.db.query(AnomalyRule).filter(
            AnomalyRule.rule_id == rule_id
        ).first()

        if not rule:
            return False

        cooldown_minutes = rule.alert_cooldown_minutes
        cooldown_end = datetime.now() - timedelta(minutes=cooldown_minutes)

        # 查询冷却时间内是否已有相同类型的异常
        recent_anomaly = self.db.query(AnomalyEvent).filter(
            AnomalyEvent.detection_rule_id == rule_id,
            AnomalyEvent.detected_at >= cooldown_end
        ).first()

        return recent_anomaly is not None

    def _update_rule_stats(self, rule_id: str):
        """更新规则统计信息"""
        rule = self.db.query(AnomalyRule).filter(
            AnomalyRule.rule_id == rule_id
        ).first()

        if rule:
            rule.total_detections += 1

    def batch_detect(self, events: List[Dict[str, Any]]) -> List[AnomalyEvent]:
        """
        批量检测事件

        Args:
            events: 事件列表

        Returns:
            创建的异常事件列表
        """
        all_events = []

        for event_data in events:
            anomalies = self.detect_and_create_events(event_data)
            all_events.extend(anomalies)

        return all_events

    def get_recent_anomalies(
        self,
        limit: int = 100,
        anomaly_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[AnomalyEvent]:
        """
        获取最近的异常事件

        Args:
            limit: 返回数量
            anomaly_type: 异常类型过滤
            severity: 严重程度过滤
            status: 状态过滤

        Returns:
            异常事件列表
        """
        query = self.db.query(AnomalyEvent)

        if anomaly_type:
            query = query.filter(AnomalyEvent.anomaly_type == anomaly_type)

        if severity:
            query = query.filter(AnomalyEvent.severity == severity)

        if status:
            query = query.filter(AnomalyEvent.status == status)

        return query.order_by(AnomalyEvent.detected_at.desc()).limit(limit).all()

    def get_anomaly_by_id(self, event_id: str) -> Optional[AnomalyEvent]:
        """
        根据ID获取异常事件

        Args:
            event_id: 异常事件ID

        Returns:
            异常事件
        """
        return self.db.query(AnomalyEvent).filter(
            AnomalyEvent.event_id == event_id
        ).first()

    def confirm_anomaly(
        self,
        event_id: str,
        is_true_positive: bool,
        confirmed_by_agent_id: str,
        resolution_note: Optional[str] = None
    ) -> Optional[AnomalyEvent]:
        """
        确认异常（真阳性或假阳性）

        Args:
            event_id: 异常事件ID
            is_true_positive: 是否为真阳性
            confirmed_by_agent_id: 确认者ID
            resolution_note: 解决说明

        Returns:
            更新后的异常事件
        """
        event = self.get_anomaly_by_id(event_id)

        if not event:
            return None

        event.status = "resolved" if is_true_positive else "false_positive"
        event.confirmed_by_agent_id = confirmed_by_agent_id
        event.confirmed_at = datetime.now()
        event.resolution_note = resolution_note

        # 更新规则统计
        if event.detection_rule_id:
            rule = self.db.query(AnomalyRule).filter(
                AnomalyRule.rule_id == event.detection_rule_id
            ).first()

            if rule:
                if is_true_positive:
                    rule.true_positive_count += 1
                else:
                    rule.false_positive_count += 1

        self.db.commit()

        return event

    def get_anomaly_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取异常统计信息

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            统计信息
        """
        query = self.db.query(AnomalyEvent)

        if start_time:
            query = query.filter(AnomalyEvent.detected_at >= start_time)

        if end_time:
            query = query.filter(AnomalyEvent.detected_at <= end_time)

        anomalies = query.all()

        total_count = len(anomalies)

        # 按类型统计
        by_type = {}
        for anomaly in anomalies:
            anomaly_type = anomaly.anomaly_type
            by_type[anomaly_type] = by_type.get(anomaly_type, 0) + 1

        # 按严重程度统计
        by_severity = {}
        for anomaly in anomalies:
            severity = anomaly.severity
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # 按状态统计
        by_status = {}
        for anomaly in anomalies:
            status = anomaly.status
            by_status[status] = by_status.get(status, 0) + 1

        # 计算准确率
        resolved_anomalies = [a for a in anomalies if a.status in ["resolved", "false_positive"]]
        accuracy = None
        if resolved_anomalies:
            true_positives = len([a for a in resolved_anomalies if a.status == "resolved"])
            accuracy = true_positives / len(resolved_anomalies)

        return {
            "total_count": total_count,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
            "accuracy": accuracy
        }

    def initialize_default_rules(self):
        """初始化默认规则"""
        existing_rules = self.db.query(AnomalyRule).count()

        if existing_rules == 0:
            for rule_config in DEFAULT_RULES:
                rule = AnomalyRule(
                    name=rule_config["name"],
                    anomaly_type=rule_config["anomaly_type"],
                    anomaly_subtype=rule_config["anomaly_subtype"],
                    detection_logic=rule_config["detection_logic"],
                    threshold_config=rule_config["threshold_config"],
                    alert_severity=rule_config["alert_severity"],
                    alert_channels=rule_config["alert_channels"],
                    alert_cooldown_minutes=rule_config["alert_cooldown_minutes"]
                )

                self.db.add(rule)

            self.db.commit()

            print(f"Initialized {len(DEFAULT_RULES)} default anomaly detection rules")


def create_detection_service(db: Session) -> AnomalyDetectionService:
    """创建异常检测服务"""
    service = AnomalyDetectionService(db)
    service.initialize_default_rules()
    return service
