"""异常告警服务"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.models.tables import AnomalyEvent, AnomalyAlert, AnomalyRule, Agent
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json
import hashlib


class AnomalyAlertingService:
    """异常告警服务"""

    def __init__(self, db: Session):
        self.db = db

    def create_alerts_for_event(self, event: AnomalyEvent) -> List[AnomalyAlert]:
        """
        为异常事件创建告警

        Args:
            event: 异常事件

        Returns:
            创建的告警列表
        """
        alerts = []

        # 获取检测规则
        rule = self.db.query(AnomalyRule).filter(
            AnomalyRule.rule_id == event.detection_rule_id
        ).first()

        if not rule:
            return alerts

        # 检查告警冷却
        if self._is_in_alert_cooldown(event, rule):
            return alerts

        # 为每个配置的告警渠道创建告警
        for channel_type in rule.alert_channels:
            # 创建告警
            alert = AnomalyAlert(
                event_id=event.event_id,
                title=f"[{rule.alert_severity.upper()}] {event.title}",
                message=self._format_alert_message(event, rule),
                severity=rule.alert_severity,
                channel_type=channel_type,
                channel_config=self._get_channel_config(channel_type),
                aggregation_key=self._generate_aggregation_key(event, rule)
            )

            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()

        return alerts

    def _is_in_alert_cooldown(self, event: AnomalyEvent, rule: AnomalyRule) -> bool:
        """检查是否在告警冷却时间内"""
        cooldown_end = datetime.now() - timedelta(minutes=rule.alert_cooldown_minutes)

        # 查询冷却时间内是否已有相同聚合键的已发送告警
        aggregation_key = self._generate_aggregation_key(event, rule)

        recent_alert = self.db.query(AnomalyAlert).filter(
            AnomalyAlert.aggregation_key == aggregation_key,
            AnomalyAlert.status == "sent",
            AnomalyAlert.sent_at >= cooldown_end
        ).first()

        return recent_alert is not None

    def _generate_aggregation_key(self, event: AnomalyEvent, rule: AnomalyRule) -> str:
        """生成聚合键"""
        key_parts = [
            rule.rule_id,
            event.anomaly_type,
            event.anomaly_subtype
        ]

        # 如果有目标，也包含在聚合键中
        if event.target_id:
            key_parts.append(event.target_id)

        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _format_alert_message(self, event: AnomalyEvent, rule: AnomalyRule) -> str:
        """格式化告警消息"""
        message_parts = [
            f"异常类型: {event.anomaly_type}/{event.anomaly_subtype}",
            f"检测时间: {event.detected_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"置信度: {event.confidence:.2%}",
            ""
        ]

        if event.target_id:
            message_parts.append(f"目标对象: {event.target_type} - {event.target_id}")
            message_parts.append("")

        message_parts.append(f"描述: {event.description}")
        message_parts.append("")

        # 添加证据信息
        if event.evidence:
            message_parts.append("证据:")
            for key, value in event.evidence.items():
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)
                message_parts.append(f"  {key}: {value}")

        message_parts.append("")
        message_parts.append(f"检测规则: {rule.name}")
        message_parts.append(f"事件ID: {event.event_id}")

        return "\n".join(message_parts)

    def _get_channel_config(self, channel_type: str) -> Dict[str, Any]:
        """获取告警渠道配置"""
        # 从配置中读取（这里简化处理）
        configs = {
            "email": {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_username": "",
                "smtp_password": "",
                "from_email": "noreply@memorymarket.com",
                "to_emails": ["admin@memorymarket.com"]
            },
            "webhook": {
                "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
            },
            "slack": {
                "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
                "channel": "#alerts"
            }
        }

        return configs.get(channel_type, {})

    def send_pending_alerts(self, limit: int = 50) -> List[AnomalyAlert]:
        """
        发送待发送的告警

        Args:
            limit: 批量发送数量

        Returns:
            已发送的告警列表
        """
        # 获取待发送的告警
        pending_alerts = self.db.query(AnomalyAlert).filter(
            AnomalyAlert.status == "pending",
            AnomalyAlert.retry_count < AnomalyAlert.max_retries
        ).order_by(AnomalyAlert.created_at.asc()).limit(limit).all()

        sent_alerts = []

        for alert in pending_alerts:
            try:
                # 发送告警
                success = self._send_alert(alert)

                if success:
                    alert.status = "sent"
                    alert.sent_at = datetime.now()
                else:
                    alert.status = "failed"
                    alert.error_message = "Failed to send alert"
                    alert.retry_count += 1

                self.db.add(alert)
                sent_alerts.append(alert)

            except Exception as e:
                alert.status = "failed"
                alert.error_message = str(e)
                alert.retry_count += 1
                self.db.add(alert)
                sent_alerts.append(alert)

        self.db.commit()

        return sent_alerts

    def _send_alert(self, alert: AnomalyAlert) -> bool:
        """发送单个告警"""
        try:
            if alert.channel_type == "email":
                return self._send_email_alert(alert)
            elif alert.channel_type == "webhook":
                return self._send_webhook_alert(alert)
            elif alert.channel_type == "slack":
                return self._send_slack_alert(alert)
            else:
                print(f"Unknown alert channel type: {alert.channel_type}")
                return False

        except Exception as e:
            print(f"Error sending alert {alert.alert_id}: {e}")
            return False

    def _send_email_alert(self, alert: AnomalyAlert) -> bool:
        """发送邮件告警"""
        config = alert.channel_config

        if not config or not config.get("smtp_username") or not config.get("to_emails"):
            print("Email alert not configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = alert.title
            msg["From"] = config["from_email"]
            msg["To"] = ", ".join(config["to_emails"])

            # 纯文本内容
            text_part = MIMEText(alert.message, "plain", "utf-8")
            msg.attach(text_part)

            # 发送邮件
            with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
                server.starttls()
                server.login(config["smtp_username"], config["smtp_password"])
                server.send_message(msg)

            return True

        except Exception as e:
            print(f"Error sending email alert: {e}")
            return False

    def _send_webhook_alert(self, alert: AnomalyAlert) -> bool:
        """发送Webhook告警"""
        config = alert.channel_config

        if not config or not config.get("url"):
            print("Webhook alert not configured")
            return False

        try:
            payload = {
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity,
                "alert_id": alert.alert_id,
                "event_id": alert.event_id,
                "timestamp": alert.created_at.isoformat()
            }

            response = requests.post(
                config["url"],
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Error sending webhook alert: {e}")
            return False

    def _send_slack_alert(self, alert: AnomalyAlert) -> bool:
        """发送Slack告警"""
        config = alert.channel_config

        if not config or not config.get("webhook_url"):
            print("Slack alert not configured")
            return False

        try:
            # 根据严重程度设置颜色
            color_map = {
                "critical": "#FF0000",
                "warning": "#FFA500",
                "info": "#00BFFF"
            }
            color = color_map.get(alert.severity, "#808080")

            payload = {
                "channel": config.get("channel", "#alerts"),
                "username": "Anomaly Alert Bot",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.message,
                        "footer": f"Alert ID: {alert.alert_id}",
                        "ts": int(alert.created_at.timestamp())
                    }
                ]
            }

            response = requests.post(
                config["webhook_url"],
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Error sending slack alert: {e}")
            return False

    def acknowledge_alert(
        self,
        alert_id: str,
        ack_by_agent_id: str
    ) -> Optional[AnomalyAlert]:
        """
        确认告警

        Args:
            alert_id: 告警ID
            ack_by_agent_id: 确认者ID

        Returns:
            更新后的告警
        """
        alert = self.db.query(AnomalyAlert).filter(
            AnomalyAlert.alert_id == alert_id
        ).first()

        if not alert:
            return None

        alert.status = "acknowledged"
        alert.ack_at = datetime.now()
        alert.ack_by_agent_id = ack_by_agent_id

        self.db.commit()

        return alert

    def get_alerts(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        channel_type: Optional[str] = None
    ) -> List[AnomalyAlert]:
        """
        获取告警列表

        Args:
            limit: 返回数量
            status: 状态过滤
            severity: 严重程度过滤
            channel_type: 渠道类型过滤

        Returns:
            告警列表
        """
        query = self.db.query(AnomalyAlert)

        if status:
            query = query.filter(AnomalyAlert.status == status)

        if severity:
            query = query.filter(AnomalyAlert.severity == severity)

        if channel_type:
            query = query.filter(AnomalyAlert.channel_type == channel_type)

        return query.order_by(AnomalyAlert.created_at.desc()).limit(limit).all()

    def get_alert_by_id(self, alert_id: str) -> Optional[AnomalyAlert]:
        """
        根据ID获取告警

        Args:
            alert_id: 告警ID

        Returns:
            告警
        """
        return self.db.query(AnomalyAlert).filter(
            AnomalyAlert.alert_id == alert_id
        ).first()

    def get_alert_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取告警统计信息

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            统计信息
        """
        query = self.db.query(AnomalyAlert)

        if start_time:
            query = query.filter(AnomalyAlert.created_at >= start_time)

        if end_time:
            query = query.filter(AnomalyAlert.created_at <= end_time)

        alerts = query.all()

        total_count = len(alerts)

        # 按状态统计
        by_status = {}
        for alert in alerts:
            status = alert.status
            by_status[status] = by_status.get(status, 0) + 1

        # 按严重程度统计
        by_severity = {}
        for alert in alerts:
            severity = alert.severity
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # 按渠道统计
        by_channel = {}
        for alert in alerts:
            channel = alert.channel_type
            by_channel[channel] = by_channel.get(channel, 0) + 1

        # 计算发送成功率
        sent_alerts = [a for a in alerts if a.status in ["sent", "acknowledged"]]
        send_success_rate = None
        if total_count > 0:
            send_success_rate = len(sent_alerts) / total_count

        return {
            "total_count": total_count,
            "by_status": by_status,
            "by_severity": by_severity,
            "by_channel": by_channel,
            "send_success_rate": send_success_rate
        }

    def aggregate_alerts(self) -> List[AnomalyAlert]:
        """
        聚合相似的告警

        Returns:
            更新的告警列表
        """
        # 查找相同聚合键的待发送告警
        pending_alerts = self.db.query(AnomalyAlert).filter(
            AnomalyAlert.status == "pending"
        ).all()

        aggregated_alerts = []

        # 按聚合键分组
        aggregation_groups = {}
        for alert in pending_alerts:
            key = alert.aggregation_key
            if key not in aggregation_groups:
                aggregation_groups[key] = []
            aggregation_groups[key].append(alert)

        # 聚合每个组
        for key, group in aggregation_groups.items():
            if len(group) > 1:
                # 保留第一个告警，更新其聚合数量
                primary_alert = group[0]
                primary_alert.aggregated_count = len(group)
                primary_alert.message = f"[已聚合 {len(group)} 个相似告警]\n\n{primary_alert.message}"

                # 将其他告警标记为已聚合
                for alert in group[1:]:
                    alert.status = "aggregated"
                    self.db.add(alert)

                self.db.add(primary_alert)
                aggregated_alerts.append(primary_alert)
            else:
                aggregated_alerts.append(group[0])

        self.db.commit()

        return aggregated_alerts


def create_alerting_service(db: Session) -> AnomalyAlertingService:
    """创建异常告警服务"""
    return AnomalyAlertingService(db)
