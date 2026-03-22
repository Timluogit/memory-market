"""交易记录 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.core.auth import get_current_agent
from app.core.exceptions import success_response
from app.models.tables import Agent

router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


class TransactionResponse(BaseModel):
    """交易记录响应"""
    tx_id: str
    agent_id: str
    tx_type: str
    amount: int
    balance_after: int
    related_id: Optional[str]
    description: Optional[str]
    commission: Optional[int]
    created_at: datetime


class TransactionListResponse(BaseModel):
    """交易列表响应"""
    items: List[TransactionResponse]
    total: int


@router.get("/", summary="获取所有交易记录")
async def get_all_transactions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    tx_type: Optional[str] = Query(None, description="交易类型过滤: purchase/sale/recharge/withdraw/refund/bonus"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有交易记录（公开透明）

    - **page**: 页码
    - **page_size**: 每页数量
    - **tx_type**: 交易类型过滤
    """
    from app.models.tables import Transaction

    # 构建查询
    query = select(Transaction).order_by(desc(Transaction.created_at))

    if tx_type:
        query = query.where(Transaction.tx_type == tx_type)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    transactions = result.scalars().all()

    # 获取总数
    from sqlalchemy import func
    count_query = select(func.count()).select_from(Transaction)
    if tx_type:
        count_query = count_query.where(Transaction.tx_type == tx_type)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    items = [
        TransactionResponse(
            tx_id=tx.tx_id,
            agent_id=tx.agent_id,
            tx_type=tx.tx_type,
            amount=tx.amount,
            balance_after=tx.balance_after,
            related_id=tx.related_id,
            description=tx.description,
            commission=tx.commission,
            created_at=tx.created_at
        )
        for tx in transactions
    ]

    return success_response({
        "items": items,
        "total": total
    })


@router.get("/my", summary="获取我的交易记录")
async def get_my_transactions(
    agent: Agent = Depends(get_current_agent),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前认证 Agent 的交易记录（需要认证）
    """
    from app.models.tables import Transaction

    # 构建查询 - 使用认证后的 agent_id
    query = select(Transaction).where(
        Transaction.agent_id == agent.agent_id
    ).order_by(desc(Transaction.created_at))

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    transactions = result.scalars().all()

    # 获取总数
    from sqlalchemy import func
    count_query = select(func.count()).select_from(Transaction).where(Transaction.agent_id == agent.agent_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    items = [
        TransactionResponse(
            tx_id=tx.tx_id,
            agent_id=tx.agent_id,
            tx_type=tx.tx_type,
            amount=tx.amount,
            balance_after=tx.balance_after,
            related_id=tx.related_id,
            description=tx.description,
            commission=tx.commission,
            created_at=tx.created_at
        )
        for tx in transactions
    ]

    return success_response({
        "items": items,
        "total": total
    })


class PlatformStatsResponse(BaseModel):
    """平台统计响应"""
    stats_id: str
    total_transactions: int
    total_revenue: int
    total_volume: int
    daily_transactions: int
    daily_revenue: int
    daily_volume: int
    date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@router.get("/stats", summary="获取平台收入统计")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    获取平台收入统计（公开透明）

    返回最新的平台统计数据，包括：
    - total_transactions: 累计交易数
    - total_revenue: 平台总收入（佣金）
    - total_volume: 累计交易额
    - daily_transactions: 当日交易数
    - daily_revenue: 当日佣金收入
    - daily_volume: 当日交易额
    """
    from app.models.tables import PlatformStats
    from app.core.config import settings

    # 获取最新的统计记录（今日或最新日期）
    query = select(PlatformStats).order_by(desc(PlatformStats.date)).limit(1)
    result = await db.execute(query)
    stats = result.scalar_one_or_none()

    if not stats:
        # 如果没有统计记录，返回空数据
        return success_response({
            "stats": None,
            "message": "暂无统计数据"
        })

    stats_response = PlatformStatsResponse(
        stats_id=stats.stats_id,
        total_transactions=stats.total_transactions,
        total_revenue=stats.total_revenue,
        total_volume=stats.total_volume,
        daily_transactions=stats.daily_transactions,
        daily_revenue=stats.daily_revenue,
        daily_volume=stats.daily_volume,
        date=stats.date,
        created_at=stats.created_at,
        updated_at=stats.updated_at
    )

    return success_response({
        "stats": stats_response,
        "commission_rate": settings.PLATFORM_FEE_RATE,
        "seller_share_rate": settings.SELLER_SHARE_RATE
    })
