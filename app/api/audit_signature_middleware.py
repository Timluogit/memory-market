"""审计日志签名中间件"""
import logging
from typing import Callable
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.digital_signature_service import signature_service
from app.services.key_management_service import key_management_service
from app.models.tables import AuditLog

logger = logging.getLogger(__name__)


class AuditSignatureMiddleware:
    """审计日志签名中间件 - 自动签名和验证审计日志"""

    def __init__(self):
        self.enabled = True
        self.alarm_on_failure = True

    def sign_audit_log(self, audit_log: AuditLog) -> bool:
        """
        为审计日志创建签名

        Args:
            audit_log: 审计日志对象

        Returns:
            签名是否成功
        """
        if not self.enabled:
            return True

        try:
            # 获取当前密钥对
            key_pair = key_management_service.get_current_key_pair()
            if key_pair is None:
                logger.warning("No signing key available, skipping signature")
                return True

            key_id, private_key_pem, public_key_pem = key_pair

            # 准备要签名的数据（排除签名和签名时间戳字段）
            data_to_sign = {
                "log_id": audit_log.log_id,
                "actor_agent_id": audit_log.actor_agent_id,
                "actor_name": audit_log.actor_name,
                "action_type": audit_log.action_type,
                "action_category": audit_log.action_category,
                "target_type": audit_log.target_type,
                "target_id": audit_log.target_id,
                "target_name": audit_log.target_name,
                "http_method": audit_log.http_method,
                "endpoint": audit_log.endpoint,
                "ip_address": audit_log.ip_address,
                "status": audit_log.status,
                "status_code": audit_log.status_code,
                "error_message": audit_log.error_message,
                "request_data": audit_log.request_data,
                "response_data": audit_log.response_data,
                "changes": audit_log.changes,
                "session_id": audit_log.session_id,
                "request_id": audit_log.request_id,
                "created_at": audit_log.created_at.isoformat() if audit_log.created_at else None
            }

            # 签名
            signature_hex, signature_timestamp = signature_service.sign(
                data_to_sign,
                private_key_pem
            )

            # 更新审计日志
            audit_log.signature = signature_hex
            audit_log.signature_algorithm = signature_service.algorithm_name
            audit_log.signature_timestamp = signature_timestamp

            logger.debug(f"Successfully signed audit log: {audit_log.log_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to sign audit log {audit_log.log_id}: {str(e)}")
            if self.alarm_on_failure:
                # TODO: 发送告警通知
                pass
            return False

    def verify_audit_log(self, audit_log: AuditLog) -> bool:
        """
        验证审计日志的签名

        Args:
            audit_log: 审计日志对象

        Returns:
            验证是否成功
        """
        if not self.enabled:
            return True

        # 如果没有签名，跳过验证
        if not audit_log.signature:
            logger.debug(f"No signature for audit log: {audit_log.log_id}")
            return True

        try:
            # 准备要验证的数据
            data_to_verify = {
                "log_id": audit_log.log_id,
                "actor_agent_id": audit_log.actor_agent_id,
                "actor_name": audit_log.actor_name,
                "action_type": audit_log.action_type,
                "action_category": audit_log.action_category,
                "target_type": audit_log.target_type,
                "target_id": audit_log.target_id,
                "target_name": audit_log.target_name,
                "http_method": audit_log.http_method,
                "endpoint": audit_log.endpoint,
                "ip_address": audit_log.ip_address,
                "status": audit_log.status,
                "status_code": audit_log.status_code,
                "error_message": audit_log.error_message,
                "request_data": audit_log.request_data,
                "response_data": audit_log.response_data,
                "changes": audit_log.changes,
                "session_id": audit_log.session_id,
                "request_id": audit_log.request_id,
                "created_at": audit_log.created_at.isoformat() if audit_log.created_at else None
            }

            # 从签名时间戳中提取密钥ID（假设签名字符串包含密钥信息）
            # 实际实现中，可以在签名字符串中嵌入密钥ID或使用其他方式关联
            # 这里简化处理：使用当前密钥验证
            key_pair = key_management_service.get_current_key_pair()
            if key_pair is None:
                logger.warning("No verification key available")
                return False

            _, _, public_key_pem = key_pair

            # 验证签名
            is_valid = signature_service.verify(
                data_to_verify,
                audit_log.signature,
                public_key_pem
            )

            if not is_valid:
                logger.error(f"Signature verification failed for audit log: {audit_log.log_id}")
                if self.alarm_on_failure:
                    # TODO: 发送篡改告警
                    pass

            return is_valid

        except Exception as e:
            logger.error(f"Failed to verify audit log {audit_log.log_id}: {str(e)}")
            if self.alarm_on_failure:
                # TODO: 发送验证失败告警
                pass
            return False

    def audit_log_before_commit(self, db: Session, audit_log: AuditLog):
        """
        在审计日志提交前自动签名（作为数据库事件监听器）

        Args:
            db: 数据库会话
            audit_log: 审计日志对象
        """
        # 只为新创建的日志签名（更新时不重新签名，以保持原始签名）
        if not audit_log.signature:
            self.sign_audit_log(audit_log)

    def audit_log_after_load(self, db: Session, audit_log: AuditLog):
        """
        在审计日志加载后自动验证签名（作为数据库事件监听器）

        Args:
            db: 数据库会话
            audit_log: 审计日志对象
        """
        if audit_log.signature:
            is_valid = self.verify_audit_log(audit_log)
            if not is_valid:
                logger.warning(f"Loaded audit log with invalid signature: {audit_log.log_id}")


# 全局实例
audit_signature_middleware = AuditSignatureMiddleware()


def setup_audit_signature_events():
    """
    设置审计日志签名相关的数据库事件监听器

    在应用启动时调用此函数来设置事件监听器
    """
    from sqlalchemy import event

    @event.listens_for(AuditLog, "before_insert")
    def handle_before_insert(mapper, connection, target):
        """在插入前签名"""
        # 注意：这里无法直接调用中间件，因为还没有 session
        # 实际应该在应用层面处理
        pass

    @event.listens_for(AuditLog, "before_update")
    def handle_before_update(mapper, connection, target):
        """在更新前处理"""
        # 不重新签名，保持原始签名
        pass

    @event.listens_for(AuditLog, "load")
    def handle_load(target, context):
        """在加载后验证签名"""
        # 注意：这里无法直接调用中间件
        # 实际应该在应用层面处理
        pass


# 工具函数：在应用代码中使用
def sign_audit_log_before_commit(db: Session, audit_log: AuditLog):
    """
    在提交前签名审计日志（在应用代码中调用）

    Args:
        db: 数据库会话
        audit_log: 审计日志对象
    """
    audit_signature_middleware.audit_log_before_commit(db, audit_log)


def verify_audit_log_after_load(db: Session, audit_log: AuditLog) -> bool:
    """
    在加载后验证审计日志（在应用代码中调用）

    Args:
        db: 数据库会话
        audit_log: 审计日志对象

    Returns:
        验证是否成功
    """
    return audit_signature_middleware.verify_audit_log(audit_log)
