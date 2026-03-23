"""
高级权限管理 API - AWS IAM 风格

端点：
- POST /permissions/policies - 创建策略
- GET /permissions/policies - 列出策略
- GET /permissions/policies/{id} - 获取策略详情
- PUT /permissions/policies/{id} - 更新策略
- DELETE /permissions/policies/{id} - 删除策略
- POST /permissions/policies/{id}/attach - 附加策略
- POST /permissions/policies/{id}/detach - 分离策略
- GET /permissions/policies/{id}/versions - 获取策略版本
- POST /permissions/policies/{id}/versions/{vid}/set-default - 设置默认版本
- POST /permissions/check - 权限检查
- POST /permissions/evaluate - 策略评估
- GET /permissions/effective/{agent_id} - 获取有效权限
- GET /permissions/audit - 审计日志查询
- GET /permissions/audit/report - 审计报告
- GET /permissions/roles/{id}/hierarchy - 角色层级
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.services.policy_service import PolicyService, PolicyEvaluator, ConditionEvaluator
from app.services.rbac_service import RBACService
from app.services.audit_service import AuditService
from app.api.permission_decorators import require_permission


# ========== 路由器 ==========
router = APIRouter(prefix="/permissions", tags=["高级权限管理"])


# ========== 请求/响应模型 ==========

class PolicyDocument(BaseModel):
    """策略文档 - AWS IAM 风格"""
    Version: str = Field(default="2024-01-01", description="策略版本")
    Statement: List[Dict[str, Any]] = Field(..., description="策略声明列表")

    class Config:
        json_schema_extra = {
            "example": {
                "Version": "2024-01-01",
                "Statement": [
                    {
                        "Sid": "AllowMemoryRead",
                        "Effect": "Allow",
                        "Action": ["memory:get", "memory:list"],
                        "Resource": ["memory:*"],
                        "Condition": {
                            "StringEquals": {"category": "技术"}
                        }
                    }
                ]
            }
        }


class CreatePolicyRequest(BaseModel):
    """创建策略请求"""
    name: str = Field(..., description="策略名称", max_length=200)
    description: Optional[str] = Field(None, description="策略描述")
    policy_type: str = Field(default="custom", description="策略类型: managed/custom/inline")
    policy_document: Dict[str, Any] = Field(..., description="AWS IAM 风格的策略文档")


class UpdatePolicyRequest(BaseModel):
    """更新策略请求"""
    name: Optional[str] = Field(None, description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    is_active: Optional[bool] = Field(None, description="是否激活")
    policy_document: Optional[Dict[str, Any]] = Field(None, description="策略文档（会创建新版本）")
    changelog: Optional[str] = Field(None, description="变更说明")


class AttachPolicyRequest(BaseModel):
    """附加策略请求"""
    agent_id: Optional[str] = Field(None, description="用户ID")
    role_id: Optional[str] = Field(None, description="角色ID")
    attachment_type: str = Field(default="managed", description="附加类型: managed/inline")
    resource_scope: Optional[Dict[str, Any]] = Field(None, description="资源范围限制")
    condition_overrides: Optional[Dict[str, Any]] = Field(None, description="条件覆盖")
    expires_days: Optional[int] = Field(None, description="有效期天数")


class DetachPolicyRequest(BaseModel):
    """分离策略请求"""
    agent_id: Optional[str] = Field(None, description="用户ID")
    role_id: Optional[str] = Field(None, description="角色ID")


class PermissionCheckRequest(BaseModel):
    """权限检查请求"""
    agent_id: str = Field(..., description="用户ID")
    action: str = Field(..., description="操作，如 memory:get")
    resource: str = Field(..., description="资源，如 memory:mem_xxx")
    context: Optional[Dict[str, Any]] = Field(None, description="请求上下文")


class PolicyEvaluateRequest(BaseModel):
    """策略评估请求"""
    policies: List[Dict[str, Any]] = Field(..., description="策略文档列表")
    action: str = Field(..., description="操作")
    resource: str = Field(..., description="资源")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文")


class ConditionEvaluateRequest(BaseModel):
    """条件评估请求"""
    condition: Dict[str, Any] = Field(..., description="条件表达式")
    context: Dict[str, Any] = Field(..., description="上下文")


class AuditQueryRequest(BaseModel):
    """审计日志查询请求"""
    actor_agent_id: Optional[str] = Field(None, description="操作者ID")
    action_type: Optional[str] = Field(None, description="操作类型")
    action_category: Optional[str] = Field(None, description="操作分类")
    target_type: Optional[str] = Field(None, description="目标类型")
    target_id: Optional[str] = Field(None, description="目标ID")
    permission_code: Optional[str] = Field(None, description="权限代码")
    status: Optional[str] = Field(None, description="状态")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=200, description="每页数量")


class PolicyResponse(BaseModel):
    """策略响应"""
    policy_id: str
    name: str
    description: Optional[str]
    policy_type: str
    policy_document: Dict[str, Any]
    is_active: bool
    is_system: bool
    default_version_id: Optional[str]
    version_count: int
    attachment_count: int
    created_at: str

    class Config:
        from_attributes = True


# ========== 策略 CRUD ==========

@router.post("/policies", response_model=PolicyResponse, summary="创建策略")
@require_permission("system.policy.create")
async def create_policy(
    req: CreatePolicyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的权限策略（AWS IAM 风格）

    策略文档格式：
    ```json
    {
        "Version": "2024-01-01",
        "Statement": [
            {
                "Sid": "AllowMemoryRead",
                "Effect": "Allow",
                "Action": ["memory:get", "memory:list"],
                "Resource": ["memory:*"],
                "Condition": {
                    "StringEquals": {"category": "技术"}
                }
            }
        ]
    }
    ```
    """
    actor_agent_id = getattr(request.state, "agent_id", None)

    service = PolicyService(db)
    try:
        policy = await service.create_policy(
            name=req.name,
            policy_document=req.policy_document,
            description=req.description,
            policy_type=req.policy_type,
            created_by_agent_id=actor_agent_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        policy_document=policy.policy_document,
        is_active=policy.is_active,
        is_system=policy.is_system,
        default_version_id=policy.default_version_id,
        version_count=policy.version_count,
        attachment_count=policy.attachment_count,
        created_at=policy.created_at.isoformat() if policy.created_at else ""
    )


@router.get("/policies", summary="列出策略")
@require_permission("system.policy.list")
async def list_policies(
    policy_type: Optional[str] = Query(None, description="过滤策略类型"),
    is_active: Optional[bool] = Query(None, description="是否仅激活"),
    is_system: Optional[bool] = Query(None, description="是否仅系统策略"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """列出所有策略"""
    service = PolicyService(db)
    result = await service.list_policies(
        policy_type=policy_type,
        is_active=is_active,
        is_system=is_system,
        page=page,
        page_size=page_size
    )

    # 转换为响应格式
    result["policies"] = [
        PolicyResponse(
            policy_id=p.policy_id,
            name=p.name,
            description=p.description,
            policy_type=p.policy_type,
            policy_document=p.policy_document,
            is_active=p.is_active,
            is_system=p.is_system,
            default_version_id=p.default_version_id,
            version_count=p.version_count,
            attachment_count=p.attachment_count,
            created_at=p.created_at.isoformat() if p.created_at else ""
        )
        for p in result["policies"]
    ]

    return result


@router.get("/policies/{policy_id}", response_model=PolicyResponse, summary="获取策略详情")
@require_permission("system.policy.get")
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取策略详情"""
    service = PolicyService(db)
    policy = await service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        policy_document=policy.policy_document,
        is_active=policy.is_active,
        is_system=policy.is_system,
        default_version_id=policy.default_version_id,
        version_count=policy.version_count,
        attachment_count=policy.attachment_count,
        created_at=policy.created_at.isoformat() if policy.created_at else ""
    )


@router.put("/policies/{policy_id}", response_model=PolicyResponse, summary="更新策略")
@require_permission("system.policy.update")
async def update_policy(
    policy_id: str,
    req: UpdatePolicyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    更新策略

    如果更新 policy_document，会自动创建新版本
    """
    actor_agent_id = getattr(request.state, "agent_id", None)

    service = PolicyService(db)
    try:
        policy = await service.update_policy(
            policy_id=policy_id,
            policy_document=req.policy_document,
            name=req.name,
            description=req.description,
            is_active=req.is_active,
            changelog=req.changelog,
            actor_agent_id=actor_agent_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        policy_document=policy.policy_document,
        is_active=policy.is_active,
        is_system=policy.is_system,
        default_version_id=policy.default_version_id,
        version_count=policy.version_count,
        attachment_count=policy.attachment_count,
        created_at=policy.created_at.isoformat() if policy.created_at else ""
    )


@router.delete("/policies/{policy_id}", summary="删除策略")
@require_permission("system.policy.delete")
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除策略（不能删除有附加的策略或系统策略）"""
    service = PolicyService(db)
    try:
        success = await service.delete_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")

    return {"message": "策略删除成功"}


# ========== 策略附加/分离 ==========

@router.post("/policies/{policy_id}/attach", summary="附加策略")
@require_permission("system.policy.attach")
async def attach_policy(
    policy_id: str,
    req: AttachPolicyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """将策略附加到用户或角色"""
    if not req.agent_id and not req.role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    actor_agent_id = getattr(request.state, "agent_id", None)

    # 计算过期时间
    expires_at = None
    if req.expires_days:
        expires_at = datetime.now() + __import__("datetime").timedelta(days=req.expires_days)

    service = PolicyService(db)
    try:
        attachment = await service.attach_policy(
            policy_id=policy_id,
            agent_id=req.agent_id,
            role_id=req.role_id,
            attachment_type=req.attachment_type,
            resource_scope=req.resource_scope,
            condition_overrides=req.condition_overrides,
            expires_at=expires_at,
            created_by_agent_id=actor_agent_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "策略附加成功",
        "attachment_id": attachment.attachment_id,
        "policy_id": policy_id,
        "agent_id": req.agent_id,
        "role_id": req.role_id
    }


@router.post("/policies/{policy_id}/detach", summary="分离策略")
@require_permission("system.policy.detach")
async def detach_policy(
    policy_id: str,
    req: DetachPolicyRequest,
    db: AsyncSession = Depends(get_db)
):
    """从用户或角色分离策略"""
    if not req.agent_id and not req.role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 agent_id 或 role_id"
        )

    service = PolicyService(db)
    success = await service.detach_policy(
        policy_id=policy_id,
        agent_id=req.agent_id,
        role_id=req.role_id
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略附加不存在")

    return {"message": "策略分离成功"}


@router.get("/policies/{policy_id}/attachments", summary="获取策略附加列表")
@require_permission("system.policy.get")
async def get_policy_attachments(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取策略附加到的所有用户和角色"""
    service = PolicyService(db)
    policy = await service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")

    attachments = await service.get_attached_policies()
    # 只返回该策略的附加
    policy_attachments = [a for a in attachments if a.policy_id == policy_id]

    return {
        "policy_id": policy_id,
        "attachments": [
            {
                "attachment_id": a.attachment_id,
                "agent_id": a.agent_id,
                "role_id": a.role_id,
                "attachment_type": a.attachment_type,
                "resource_scope": a.resource_scope,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in policy_attachments
        ]
    }


# ========== 策略版本 ==========

@router.get("/policies/{policy_id}/versions", summary="获取策略版本")
@require_permission("system.policy.get")
async def get_policy_versions(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取策略的所有版本"""
    service = PolicyService(db)
    policy = await service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")

    versions = await service.get_policy_versions(policy_id)

    return {
        "policy_id": policy_id,
        "versions": [
            {
                "version_id": v.version_id,
                "version_number": v.version_number,
                "is_default": v.is_default,
                "policy_document": v.policy_document,
                "changelog": v.changelog,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in versions
        ]
    }


@router.post("/policies/{policy_id}/versions/{version_id}/set-default", summary="设置默认版本")
@require_permission("system.policy.update")
async def set_default_version(
    policy_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db)
):
    """设置策略的默认版本"""
    service = PolicyService(db)
    success = await service.set_default_version(policy_id, version_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在")

    return {"message": "默认版本设置成功"}


# ========== 权限检查 ==========

@router.post("/check", summary="权限检查")
async def check_permission(
    req: PermissionCheckRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    检查用户是否有执行指定操作的权限

    完整的 AWS IAM 评估逻辑：
    1. 收集所有适用的策略
    2. 显式 Deny > 显式 Allow > 隐式 Deny
    3. 返回详细的评估结果

    示例请求：
    ```json
    {
        "agent_id": "agent_xxx",
        "action": "memory:get",
        "resource": "memory:mem_xxx",
        "context": {
            "category": "技术",
            "source_ip": "10.0.0.1"
        }
    }
    ```
    """
    service = PolicyService(db)
    result = await service.check_permission(
        agent_id=req.agent_id,
        action=req.action,
        resource=req.resource,
        context=req.context
    )

    # 记录审计日志
    audit_service = AuditService(db)
    await audit_service.log_permission_check(
        agent_id=req.agent_id,
        permission_code=req.action,
        resource_type=req.resource.split(":")[0] if ":" in req.resource else None,
        resource_id=req.resource.split(":")[1] if ":" in req.resource else None,
        status="success" if result["allowed"] else "forbidden",
        reason=result["reason"]
    )
    await db.commit()

    return result


@router.post("/evaluate", summary="策略评估")
async def evaluate_policies(
    req: PolicyEvaluateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    直接评估策略文档（不查数据库）

    用于测试和调试策略
    """
    context = req.context or {}
    allowed, reason = PolicyEvaluator.evaluate_policies(
        policies=req.policies,
        action=req.action,
        resource=req.resource,
        context=context
    )

    return {
        "allowed": allowed,
        "reason": reason,
        "action": req.action,
        "resource": req.resource,
        "policies_evaluated": len(req.policies)
    }


@router.post("/evaluate-condition", summary="条件评估")
async def evaluate_condition(
    req: ConditionEvaluateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    评估条件表达式

    支持的操作符：
    - StringEquals / StringNotEquals
    - StringLike / StringNotLike
    - NumericEquals / NumericGreaterThan / NumericLessThan
    - DateGreaterThan / DateLessThan
    - IpAddress / NotIpAddress
    - Bool / Null
    """
    result = ConditionEvaluator.evaluate(req.condition, req.context)
    return {
        "result": result,
        "condition": req.condition,
        "context": req.context
    }


# ========== 有效权限 ==========

@router.get("/effective/{agent_id}", summary="获取用户有效权限")
async def get_effective_permissions(
    agent_id: str,
    resource_type: Optional[str] = Query(None, description="资源类型过滤"),
    resource_id: Optional[str] = Query(None, description="资源ID过滤"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户的有效权限（合并所有来源）

    包括：直接权限、角色权限（含继承）、资源级权限
    """
    rbac_service = RBACService(db)
    result = await rbac_service.get_effective_permissions(
        agent_id=agent_id,
        resource_type=resource_type,
        resource_id=resource_id
    )
    return result


# ========== 角色层级 ==========

@router.get("/roles/{role_id}/hierarchy", summary="获取角色层级")
@require_permission("system.role.get")
async def get_role_hierarchy(
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取角色的完整继承链"""
    rbac_service = RBACService(db)
    result = await rbac_service.get_role_hierarchy(role_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return result


# ========== 审计日志 ==========

@router.get("/audit", summary="审计日志查询")
@require_permission("system.audit.query")
async def query_audit_logs(
    actor_agent_id: Optional[str] = Query(None, description="操作者ID"),
    action_type: Optional[str] = Query(None, description="操作类型"),
    action_category: Optional[str] = Query(None, description="操作分类"),
    target_type: Optional[str] = Query(None, description="目标类型"),
    target_id: Optional[str] = Query(None, description="目标ID"),
    permission_code: Optional[str] = Query(None, description="权限代码"),
    status_filter: Optional[str] = Query(None, alias="status", description="状态"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """
    查询权限审计日志

    支持多条件过滤、分页
    """
    audit_service = AuditService(db)
    result = await audit_service.query_permission_audit_logs(
        actor_agent_id=actor_agent_id,
        action_type=action_type,
        action_category=action_category,
        target_type=target_type,
        target_id=target_id,
        permission_code=permission_code,
        status=status_filter,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )
    return result


@router.get("/audit/report", summary="审计报告")
@require_permission("system.audit.report")
async def get_audit_report(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db)
):
    """
    生成权限审计报告

    包含：
    - 总体统计（成功率、操作数等）
    - 权限检查/变更统计
    - Top 操作者
    - Top 权限
    - 失败分析
    - 策略统计
    """
    audit_service = AuditService(db)
    report = await audit_service.generate_permission_report(
        start_time=start_time,
        end_time=end_time
    )
    return report
