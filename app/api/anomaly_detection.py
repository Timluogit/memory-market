"""异常检测API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.tables import AnomalyEvent, AnomalyAlert, AnomalyRule
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.anomaly_alerting_service import AnomalyAlertingService
from app.core.auth import get_current_agent

router = APIRouter(prefix="/anomalies", tags=["异常检测"])


# ============== 异常事件API ==============

@router.get("", summary="获取异常事件列表")
def get_anomalies(
    limit: int = Query(100, description="返回数量", ge=1, le=1000),
    anomaly_type: Optional[str] = Query(None, description="异常类型过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db)
):
    """
    获取异常事件列表

    支持的异常类型: login, transaction, query, behavior, system
    支持的严重程度: critical, warning, info
    支持的状态: new, investigating, resolved, false_positive
    """
    service = AnomalyDetectionService(db)
    anomalies = service.get_recent_anomalies(
        limit=limit,
        anomaly_type=anomaly_type,
        severity=severity,
        status=status
    )

    return {
        "total": len(anomalies),
        "items": [
            {
                "event_id": a.event_id,
                "anomaly_type": a.anomaly_type,
                "anomaly_subtype": a.anomaly_subtype,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "confidence": a.confidence,
                "status": a.status,
                "detected_at": a.detected_at.isoformat(),
                "confirmed_at": a.confirmed_at.isoformat() if a.confirmed_at else None,
                "resolution_note": a.resolution_note
            }
            for a in anomalies
        ]
    }


@router.get("/{event_id}", summary="获取异常事件详情")
def get_anomaly_detail(
    event_id: str,
    db: Session = Depends(get_db)
):
    """获取异常事件详情"""
    service = AnomalyDetectionService(db)
    anomaly = service.get_anomaly_by_id(event_id)

    if not anomaly:
        raise HTTPException(status_code=404, detail="异常事件不存在")

    # 获取相关告警
    alerts = db.query(AnomalyAlert).filter(
        AnomalyAlert.event_id == event_id
    ).all()

    return {
        "event_id": anomaly.event_id,
        "anomaly_type": anomaly.anomaly_type,
        "anomaly_subtype": anomaly.anomaly_subtype,
        "severity": anomaly.severity,
        "title": anomaly.title,
        "description": anomaly.description,
        "target_type": anomaly.target_type,
        "target_id": anomaly.target_id,
        "evidence": anomaly.evidence,
        "confidence": anomaly.confidence,
        "status": anomaly.status,
        "detected_at": anomaly.detected_at.isoformat(),
        "confirmed_at": anomaly.confirmed_at.isoformat() if anomaly.confirmed_at else None,
        "resolution_note": anomaly.resolution_note,
        "detection_rule_id": anomaly.detection_rule_id,
        "alerts": [
            {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "severity": alert.severity,
                "channel_type": alert.channel_type,
                "status": alert.status,
                "created_at": alert.created_at.isoformat(),
                "sent_at": alert.sent_at.isoformat() if alert.sent_at else None
            }
            for alert in alerts
        ]
    }


@router.post("/{event_id}/confirm", summary="确认异常")
def confirm_anomaly(
    event_id: str,
    is_true_positive: bool = Query(..., description="是否为真阳性"),
    resolution_note: Optional[str] = Query(None, description="解决说明"),
    current_agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    确认异常事件

    - is_true_positive: True 表示真阳性（确实是异常），False 表示假阳性（误报）
    - resolution_note: 可选的解决说明
    """
    service = AnomalyDetectionService(db)
    anomaly = service.confirm_anomaly(
        event_id=event_id,
        is_true_positive=is_true_positive,
        confirmed_by_agent_id=current_agent.agent_id,
        resolution_note=resolution_note
    )

    if not anomaly:
        raise HTTPException(status_code=404, detail="异常事件不存在")

    return {
        "event_id": anomaly.event_id,
        "status": anomaly.status,
        "confirmed_at": anomaly.confirmed_at.isoformat() if anomaly.confirmed_at else None
    }


@router.get("/stats/summary", summary="获取异常统计")
def get_anomaly_stats(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db)
):
    """
    获取异常统计信息

    可以指定时间范围，默认为最近7天
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    service = AnomalyDetectionService(db)
    stats = service.get_anomaly_stats(start_time=start_time, end_time=end_time)

    return stats


# ============== 告警API ==============

@router.get("/alerts", summary="获取告警列表")
def get_alerts(
    limit: int = Query(100, description="返回数量", ge=1, le=1000),
    status: Optional[str] = Query(None, description="状态过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    channel_type: Optional[str] = Query(None, description="渠道类型过滤"),
    db: Session = Depends(get_db)
):
    """
    获取告警列表

    支持的状态: pending, sent, failed, acknowledged
    支持的严重程度: critical, warning, info
    支持的渠道类型: email, webhook, slack
    """
    service = AnomalyAlertingService(db)
    alerts = service.get_alerts(
        limit=limit,
        status=status,
        severity=severity,
        channel_type=channel_type
    )

    return {
        "total": len(alerts),
        "items": [
            {
                "alert_id": alert.alert_id,
                "event_id": alert.event_id,
                "title": alert.title,
                "severity": alert.severity,
                "channel_type": alert.channel_type,
                "status": alert.status,
                "created_at": alert.created_at.isoformat(),
                "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
                "ack_at": alert.ack_at.isoformat() if alert.ack_at else None
            }
            for alert in alerts
        ]
    }


@router.get("/alerts/{alert_id}", summary="获取告警详情")
def get_alert_detail(
    alert_id: str,
    db: Session = Depends(get_db)
):
    """获取告警详情"""
    service = AnomalyAlertingService(db)
    alert = service.get_alert_by_id(alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 获取关联的异常事件
    event = db.query(AnomalyEvent).filter(
        AnomalyEvent.event_id == alert.event_id
    ).first()

    return {
        "alert_id": alert.alert_id,
        "event_id": alert.event_id,
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity,
        "channel_type": alert.channel_type,
        "channel_config": alert.channel_config,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
        "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
        "ack_at": alert.ack_at.isoformat() if alert.ack_at else None,
        "error_message": alert.error_message,
        "retry_count": alert.retry_count,
        "aggregated_count": alert.aggregated_count,
        "event": {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "anomaly_type": event.anomaly_type,
            "anomaly_subtype": event.anomaly_subtype,
            "detected_at": event.detected_at.isoformat()
        } if event else None
    }


@router.post("/alerts/{alert_id}/ack", summary="确认告警")
def acknowledge_alert(
    alert_id: str,
    current_agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """确认告警"""
    service = AnomalyAlertingService(db)
    alert = service.acknowledge_alert(
        alert_id=alert_id,
        ack_by_agent_id=current_agent.agent_id
    )

    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    return {
        "alert_id": alert.alert_id,
        "status": alert.status,
        "ack_at": alert.ack_at.isoformat() if alert.ack_at else None
    }


@router.post("/alerts/send", summary="发送待发送的告警")
def send_pending_alerts(
    limit: int = Query(50, description="批量发送数量", ge=1, le=100),
    current_agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    手动触发发送待发送的告警

    通常由定时任务自动调用，也可以手动触发
    """
    service = AnomalyAlertingService(db)
    alerts = service.send_pending_alerts(limit=limit)

    return {
        "total": len(alerts),
        "sent": len([a for a in alerts if a.status == "sent"]),
        "failed": len([a for a in alerts if a.status == "failed"]),
        "alert_ids": [a.alert_id for a in alerts]
    }


@router.get("/alerts/stats/summary", summary="获取告警统计")
def get_alert_stats(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db)
):
    """
    获取告警统计信息

    可以指定时间范围，默认为最近7天
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    service = AnomalyAlertingService(db)
    stats = service.get_alert_stats(start_time=start_time, end_time=end_time)

    return stats


# ============== 检测规则API ==============

@router.get("/rules", summary="获取检测规则列表")
def get_anomaly_rules(
    db: Session = Depends(get_db)
):
    """获取所有异常检测规则"""
    rules = db.query(AnomalyRule).all()

    return {
        "total": len(rules),
        "items": [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "anomaly_type": rule.anomaly_type,
                "anomaly_subtype": rule.anomaly_subtype,
                "alert_severity": rule.alert_severity,
                "alert_channels": rule.alert_channels,
                "alert_cooldown_minutes": rule.alert_cooldown_minutes,
                "is_enabled": rule.is_enabled,
                "total_detections": rule.total_detections,
                "true_positive_count": rule.true_positive_count,
                "false_positive_count": rule.false_positive_count,
                "created_at": rule.created_at.isoformat(),
                "updated_at": rule.updated_at.isoformat()
            }
            for rule in rules
        ]
    }


@router.get("/rules/{rule_id}", summary="获取检测规则详情")
def get_anomaly_rule_detail(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """获取检测规则详情"""
    rule = db.query(AnomalyRule).filter(
        AnomalyRule.rule_id == rule_id
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="检测规则不存在")

    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "anomaly_type": rule.anomaly_type,
        "anomaly_subtype": rule.anomaly_subtype,
        "detection_logic": rule.detection_logic,
        "threshold_config": rule.threshold_config,
        "alert_severity": rule.alert_severity,
        "alert_channels": rule.alert_channels,
        "alert_cooldown_minutes": rule.alert_cooldown_minutes,
        "is_enabled": rule.is_enabled,
        "total_detections": rule.total_detections,
        "true_positive_count": rule.true_positive_count,
        "false_positive_count": rule.false_positive_count,
        "created_by_agent_id": rule.created_by_agent_id,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat()
    }


@router.post("/rules/{rule_id}/toggle", summary="启用/禁用检测规则")
def toggle_anomaly_rule(
    rule_id: str,
    is_enabled: bool = Query(..., description="是否启用"),
    current_agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """启用或禁用检测规则"""
    rule = db.query(AnomalyRule).filter(
        AnomalyRule.rule_id == rule_id
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="检测规则不存在")

    rule.is_enabled = is_enabled
    db.commit()

    return {
        "rule_id": rule.rule_id,
        "is_enabled": rule.is_enabled
    }


# ============== 工具API ==============

@router.post("/detect", summary="手动触发异常检测")
def detect_anomalies(
    event_data: dict,
    db: Session = Depends(get_db)
):
    """
    手动触发异常检测

    用于测试或手动检测场景
    """
    service = AnomalyDetectionService(db)
    anomalies = service.detect_and_create_events(event_data)

    return {
        "total_detected": len(anomalies),
        "event_ids": [a.event_id for a in anomalies]
    }


@router.post("/alerts/aggregate", summary="聚合告警")
def aggregate_alerts(
    current_agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    手动触发告警聚合

    通常由定时任务自动调用
    """
    service = AnomalyAlertingService(db)
    alerts = service.aggregate_alerts()

    return {
        "total_aggregated": len(alerts),
        "alert_ids": [a.alert_id for a in alerts]
    }
