"""团队积分管理API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.models.schemas import *
from app.models.tables import Agent
from app.services.team_service import CreditService
from app.core.auth import get_current_agent
from app.core.exceptions import (
    success_response,
    NOT_FOUND,
    FORBIDDEN,
    INSUFFICIENT_BALANCE
)
from app.api.dependencies import (
    get_team,
    require_team_admin,
    require_team_member
)

router = APIRouter()


@router.post("/teams/{team_id}/credits/add", tags=["Team Credits"])
async def add_credits(
    team_id: str,
    req: TeamCreditAdd,
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """充值积分到团队池（需要 Admin 或 Owner 权限）

    将个人积分充值到团队积分池。
    充值后，积分将从个人账户扣除，存入团队池。
    """
    # 检查个人积分是否足够
    if member.agent.credits < req.amount:
        raise INSUFFICIENT_BALANCE

    # 从个人账户扣除
    member.agent.credits -= req.amount
    member.agent.total_spent += req.amount

    # 充值到团队池
    team = await CreditService.add_credits(
        db,
        team_id,
        member.agent.agent_id,
        req.amount
    )

    return success_response({
        "team_credits": team.credits,
        "agent_credits": member.agent.credits,
        "amount": req.amount
    })


@router.post("/teams/{team_id}/credits/transfer", tags=["Team Credits"])
async def transfer_credits(
    team_id: str,
    req: TeamCreditTransfer,
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """从团队积分池转账到成员账户（需要 Admin 或 Owner 权限）

    将团队积分池的积分转账给成员。
    用于团队分红或奖励成员。
    """
    result = await CreditService.transfer_credits(
        db,
        team_id,
        member.agent.agent_id,
        req.to_agent_id,
        req.amount
    )

    return success_response(result)


@router.get("/teams/{team_id}/credits/transactions", tags=["Team Credits"])
async def get_transactions(
    team_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    member: dict = Depends(require_team_member),  # 需要团队成员权限
    db: AsyncSession = Depends(get_db)
):
    """获取团队积分交易历史（需要团队成员权限）

    返回团队积分池的所有交易记录，包括充值、转账、购买等。
    支持分页查询。
    """
    history = await CreditService.get_transactions(db, team_id, page, page_size)

    return success_response(history)
