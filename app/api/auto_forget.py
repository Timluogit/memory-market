"""自动遗忘API

提供自动遗忘机制的配置、管理和监控接口
"""
from typing import Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.services.auto_forget_service import get_auto_forget_service
from app.services.forget_scheduler import get_forget_scheduler
from app.core.config import settings

router = APIRouter(prefix="/auto-forget", tags=["auto-forget"])


# ============ 请求/响应模型 ============

class TTLConfigRequest(BaseModel):
    """TTL配置请求"""
    personal: Optional[int] = Field(None, description="个人信息TTL（天）", ge=1)
    preference: Optional[int] = Field(None, description="偏好TTL（天）", ge=1)
    habit: Optional[int] = Field(None, description="习惯TTL（天）", ge=1)
    skill: Optional[int] = Field(None, description="技能TTL（天）", ge=1)
    interest: Optional[int] = Field(None, description="兴趣TTL（天）", ge=1)


class TTLConfigResponse(BaseModel):
    """TTL配置响应"""
    personal: int
    preference: int
    habit: int
    skill: int
    interest: int
    default_ttl_days: int


class MemoryTTLRequest(BaseModel):
    """记忆TTL设置请求"""
    memory_id: str = Field(..., description="记忆ID")
    ttl_days: int = Field(..., description="生存时间（天）", ge=1, le=3650)


class FactOverrideRequest(BaseModel):
    """事实覆盖请求"""
    agent_id: str = Field(..., description="用户ID")
    fact_type: str = Field(..., description="事实类型")
    fact_key: str = Field(..., description="事实键")
    new_value: dict = Field(..., description="新值")
    confidence: float = Field(0.8, description="置信度", ge=0.0, le=1.0)


class ManualTriggerResponse(BaseModel):
    """手动触发响应"""
    checked: int
    expired_memories: int
    expired_facts: int
    errors: int
    triggered_at: datetime


class StatsResponse(BaseModel):
    """统计信息响应"""
    expired_memories: int
    expired_facts: int
    near_expiry_memories: int
    near_expiry_facts: int
    enabled: bool
    default_ttl_days: int
    scheduler_running: bool


# ============ API端点 ============

@router.get("/config", response_model=TTLConfigResponse)
async def get_ttl_config():
    """获取失效配置

    Returns:
        TTL配置
    """
    service = get_auto_forget_service()

    return TTLConfigResponse(
        personal=service.ttl_config["personal"],
        preference=service.ttl_config["preference"],
        habit=service.ttl_config["habit"],
        skill=service.ttl_config["skill"],
        interest=service.ttl_config["interest"],
        default_ttl_days=service.default_ttl_days,
    )


@router.post("/config", response_model=TTLConfigResponse)
async def update_ttl_config(
    request: TTLConfigRequest,
    db: AsyncSession = Depends(async_session)
):
    """更新失效配置

    Args:
        request: TTL配置请求
        db: 数据库会话

    Returns:
        更新后的TTL配置
    """
    service = get_auto_forget_service()

    # 更新TTL配置
    if request.personal is not None:
        service.ttl_config["personal"] = request.personal
    if request.preference is not None:
        service.ttl_config["preference"] = request.preference
    if request.habit is not None:
        service.ttl_config["habit"] = request.habit
    if request.skill is not None:
        service.ttl_config["skill"] = request.skill
    if request.interest is not None:
        service.ttl_config["interest"] = request.interest

    return TTLConfigResponse(
        personal=service.ttl_config["personal"],
        preference=service.ttl_config["preference"],
        habit=service.ttl_config["habit"],
        skill=service.ttl_config["skill"],
        interest=service.ttl_config["interest"],
        default_ttl_days=service.default_ttl_days,
    )


@router.post("/set-memory-ttl")
async def set_memory_ttl(
    request: MemoryTTLRequest,
    db: AsyncSession = Depends(async_session)
):
    """设置记忆TTL

    Args:
        request: 记忆TTL设置请求
        db: 数据库会话

    Returns:
        设置结果
    """
    service = get_auto_forget_service()

    memory = await service.set_memory_ttl(
        db,
        request.memory_id,
        request.ttl_days
    )

    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory not found: {request.memory_id}"
        )

    return {
        "memory_id": memory.memory_id,
        "ttl_days": memory.ttl_days,
        "expiry_time": memory.expiry_time,
        "message": f"TTL set to {request.ttl_days} days"
    }


@router.post("/override-fact")
async def override_fact(
    request: FactOverrideRequest,
    db: AsyncSession = Depends(async_session)
):
    """覆盖事实（事件失效）

    Args:
        request: 事实覆盖请求
        db: 数据库会话

    Returns:
        覆盖结果
    """
    service = get_auto_forget_service()

    new_fact, old_fact = await service.override_fact(
        db,
        request.agent_id,
        request.fact_type,
        request.fact_key,
        request.new_value,
        request.confidence
    )

    return {
        "agent_id": request.agent_id,
        "fact_type": request.fact_type,
        "fact_key": request.fact_key,
        "new_value": new_fact.fact_value,
        "old_value": old_fact.fact_value if old_fact else None,
        "expires_at": new_fact.expires_at,
        "message": "Fact overridden successfully"
    }


@router.post("/manual", response_model=ManualTriggerResponse)
async def manual_trigger(
    db: AsyncSession = Depends(async_session)
):
    """手动触发清理任务

    Args:
        db: 数据库会话

    Returns:
        清理结果
    """
    scheduler = get_forget_scheduler()

    stats = await scheduler.manual_trigger()

    return ManualTriggerResponse(
        checked=stats["checked"],
        expired_memories=stats["expired_memories"],
        expired_facts=stats["expired_facts"],
        errors=stats["errors"],
        triggered_at=datetime.now()
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(async_session)
):
    """获取失效统计

    Args:
        db: 数据库会话

    Returns:
        统计信息
    """
    service = get_auto_forget_service()
    scheduler = get_forget_scheduler()

    stats = await service.get_stats(db)

    return StatsResponse(
        expired_memories=stats["expired_memories"],
        expired_facts=stats["expired_facts"],
        near_expiry_memories=stats["near_expiry_memories"],
        near_expiry_facts=stats["near_expiry_facts"],
        enabled=stats["enabled"],
        default_ttl_days=stats["default_ttl_days"],
        scheduler_running=scheduler.is_running(),
    )


@router.post("/scheduler/start")
async def start_scheduler():
    """启动调度器

    Returns:
        启动结果
    """
    scheduler = get_forget_scheduler()

    if not settings.AUTO_FORGET_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auto-forget is disabled in settings"
        )

    await scheduler.start()

    return {
        "message": "Forget scheduler started",
        "running": scheduler.is_running(),
        "interval_minutes": settings.AUTO_FORGET_SCHEDULE_MINUTES
    }


@router.post("/scheduler/stop")
async def stop_scheduler():
    """停止调度器

    Returns:
        停止结果
    """
    scheduler = get_forget_scheduler()

    await scheduler.stop()

    return {
        "message": "Forget scheduler stopped",
        "running": scheduler.is_running()
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态

    Returns:
        调度器状态
    """
    scheduler = get_forget_scheduler()

    return {
        "running": scheduler.is_running(),
        "enabled": settings.AUTO_FORGET_ENABLED,
        "interval_minutes": settings.AUTO_FORGET_SCHEDULE_MINUTES,
        "batch_size": settings.AUTO_FORGET_BATCH_SIZE
    }
