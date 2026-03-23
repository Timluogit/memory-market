"""签名验证 API"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.models.tables import AuditLog
from app.services.digital_signature_service import signature_service
from app.services.key_management_service import key_management_service
from app.api.audit_signature_middleware import audit_signature_middleware
from app.core.logging import get_logger

router = APIRouter(prefix="/audit-logs", tags=["Signature Verification"])
logger = get_logger(__name__)


# ============ Request/Response Schemas ============

class SignatureVerificationResponse(BaseModel):
    """签名验证响应"""
    log_id: str
    is_valid: bool
    signature_algorithm: Optional[str]
    signature_timestamp: Optional[datetime]
    verification_time: datetime
    details: Optional[str]


class BatchVerificationRequest(BaseModel):
    """批量验证请求"""
    log_ids: List[str]


class BatchVerificationResponse(BaseModel):
    """批量验证响应"""
    total: int
    valid: int
    invalid: int
    no_signature: int
    results: List[SignatureVerificationResponse]


class CurrentPublicKeyResponse(BaseModel):
    """当前公钥响应"""
    key_id: Optional[str]
    public_key: Optional[str]
    algorithm: Optional[str]
    created_at: Optional[str]


class KeyRotationResponse(BaseModel):
    """密钥轮换响应"""
    old_key_id: Optional[str]
    new_key_id: str
    new_public_key: str
    rotated_at: datetime


class SignatureStatisticsResponse(BaseModel):
    """签名统计响应"""
    total_logs: int
    signed_logs: int
    unsigned_logs: int
    valid_signatures: int
    invalid_signatures: int
    signature_coverage: float  # 百分比
    verification_rate: float  # 百分比


# ============ API Endpoints ============

@router.get("/{log_id}/verify", response_model=SignatureVerificationResponse)
async def verify_single_audit_log(
    log_id: str,
    db: Session = Depends(get_db)
):
    """
    验证单条审计日志的签名

    Args:
        log_id: 审计日志ID

    Returns:
        签名验证结果
    """
    # 查询审计日志
    audit_log = db.query(AuditLog).filter(AuditLog.log_id == log_id).first()
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log not found: {log_id}"
        )

    # 检查是否有签名
    if not audit_log.signature:
        return SignatureVerificationResponse(
            log_id=audit_log.log_id,
            is_valid=False,
            signature_algorithm=None,
            signature_timestamp=None,
            verification_time=datetime.utcnow(),
            details="No signature found"
        )

    # 验证签名
    try:
        is_valid = audit_signature_middleware.verify_audit_log(audit_log)

        return SignatureVerificationResponse(
            log_id=audit_log.log_id,
            is_valid=is_valid,
            signature_algorithm=audit_log.signature_algorithm,
            signature_timestamp=audit_log.signature_timestamp,
            verification_time=datetime.utcnow(),
            details="Signature verified successfully" if is_valid else "Signature verification failed"
        )
    except Exception as e:
        logger.error(f"Error verifying signature for log {log_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify signature: {str(e)}"
        )


@router.post("/batch-verify", response_model=BatchVerificationResponse)
async def batch_verify_audit_logs(
    request: BatchVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    批量验证审计日志的签名

    Args:
        request: 批量验证请求（包含日志ID列表）

    Returns:
        批量验证结果
    """
    results = []
    valid = 0
    invalid = 0
    no_signature = 0

    # 批量查询
    audit_logs = db.query(AuditLog).filter(
        AuditLog.log_id.in_(request.log_ids)
    ).all()

    # 创建日志字典以便快速查找
    logs_dict = {log.log_id: log for log in audit_logs}

    # 验证每个日志
    for log_id in request.log_ids:
        audit_log = logs_dict.get(log_id)

        if not audit_log:
            results.append(SignatureVerificationResponse(
                log_id=log_id,
                is_valid=False,
                signature_algorithm=None,
                signature_timestamp=None,
                verification_time=datetime.utcnow(),
                details="Audit log not found"
            ))
            invalid += 1
            continue

        if not audit_log.signature:
            results.append(SignatureVerificationResponse(
                log_id=audit_log.log_id,
                is_valid=False,
                signature_algorithm=None,
                signature_timestamp=None,
                verification_time=datetime.utcnow(),
                details="No signature found"
            ))
            no_signature += 1
            continue

        try:
            is_valid = audit_signature_middleware.verify_audit_log(audit_log)

            if is_valid:
                valid += 1
            else:
                invalid += 1

            results.append(SignatureVerificationResponse(
                log_id=audit_log.log_id,
                is_valid=is_valid,
                signature_algorithm=audit_log.signature_algorithm,
                signature_timestamp=audit_log.signature_timestamp,
                verification_time=datetime.utcnow(),
                details="Signature verified successfully" if is_valid else "Signature verification failed"
            ))
        except Exception as e:
            logger.error(f"Error verifying signature for log {log_id}: {str(e)}")
            results.append(SignatureVerificationResponse(
                log_id=audit_log.log_id,
                is_valid=False,
                signature_algorithm=audit_log.signature_algorithm,
                signature_timestamp=audit_log.signature_timestamp,
                verification_time=datetime.utcnow(),
                details=f"Verification error: {str(e)}"
            ))
            invalid += 1

    return BatchVerificationResponse(
        total=len(request.log_ids),
        valid=valid,
        invalid=invalid,
        no_signature=no_signature,
        results=results
    )


@router.get("/statistics/signature", response_model=SignatureStatisticsResponse)
async def get_signature_statistics(
    db: Session = Depends(get_db)
):
    """
    获取签名统计信息

    Returns:
        签名统计信息
    """
    # 统计总日志数
    total_logs = db.query(AuditLog).count()

    # 统计已签名的日志数
    signed_logs = db.query(AuditLog).filter(
        AuditLog.signature.isnot(None)
    ).count()

    unsigned_logs = total_logs - signed_logs

    # 验证签名（为了性能，只验证最近100条已签名的日志）
    recent_signed_logs = db.query(AuditLog).filter(
        AuditLog.signature.isnot(None)
    ).order_by(AuditLog.created_at.desc()).limit(100).all()

    valid_signatures = 0
    invalid_signatures = 0

    for audit_log in recent_signed_logs:
        try:
            if audit_signature_middleware.verify_audit_log(audit_log):
                valid_signatures += 1
            else:
                invalid_signatures += 1
        except Exception:
            invalid_signatures += 1

    # 计算覆盖率
    signature_coverage = (signed_logs / total_logs * 100) if total_logs > 0 else 0.0
    verification_rate = (valid_signatures / signed_logs * 100) if signed_logs > 0 else 0.0

    return SignatureStatisticsResponse(
        total_logs=total_logs,
        signed_logs=signed_logs,
        unsigned_logs=unsigned_logs,
        valid_signatures=valid_signatures,
        invalid_signatures=invalid_signatures,
        signature_coverage=round(signature_coverage, 2),
        verification_rate=round(verification_rate, 2)
    )


@router.get("/keys/current", response_model=CurrentPublicKeyResponse)
async def get_current_public_key():
    """
    获取当前公钥

    Returns:
        当前公钥信息
    """
    key_pair = key_management_service.get_current_key_pair()

    if key_pair is None:
        # 如果没有密钥，自动生成一个
        key_id, public_key_pem = key_management_service.generate_and_store_key_pair()
        return CurrentPublicKeyResponse(
            key_id=key_id,
            public_key=public_key_pem,
            algorithm=signature_service.algorithm_name,
            created_at=datetime.utcnow().isoformat()
        )

    key_id, _, public_key_pem = key_pair

    return CurrentPublicKeyResponse(
        key_id=key_id,
        public_key=public_key_pem.decode('utf-8'),
        algorithm=signature_service.algorithm_name,
        created_at=datetime.utcnow().isoformat()
    )


@router.post("/keys/rotate", response_model=KeyRotationResponse)
async def rotate_key(db: Session = Depends(get_db)):
    """
    密钥轮换：生成新密钥并归档旧密钥

    Returns:
        密钥轮换结果
    """
    # 获取旧密钥ID
    old_key_pair = key_management_service.get_current_key_pair()
    old_key_id = old_key_pair[0] if old_key_pair else None

    # 生成新密钥
    new_key_id, new_public_key_pem = key_management_service.rotate_key()

    logger.info(f"Key rotated: {old_key_id} -> {new_key_id}")

    return KeyRotationResponse(
        old_key_id=old_key_id,
        new_key_id=new_key_id,
        new_public_key=new_public_key_pem,
        rotated_at=datetime.utcnow()
    )


@router.get("/keys/info")
async def get_key_info():
    """
    获取密钥信息

    Returns:
        密钥信息字典
    """
    key_info = key_management_service.get_key_info()
    return key_info


@router.get("/algorithm/info")
async def get_algorithm_info():
    """
    获取签名算法信息

    Returns:
        算法信息字典
    """
    return signature_service.get_algorithm_info()
