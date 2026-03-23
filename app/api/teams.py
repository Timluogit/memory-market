"""团队管理API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.models.schemas import *
from app.models.tables import Agent
from app.services.team_service import TeamService
from app.core.auth import get_current_agent
from app.core.exceptions import (
    success_response,
    NOT_FOUND,
    FORBIDDEN,
    INVALID_PARAMS
)

router = APIRouter()


@router.post("/teams", tags=["Team"])
async def create_team(
    req: TeamCreate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """创建团队"""
    team = await TeamService.create_team(db, agent.agent_id, req)

    return success_response(TeamResponse(
        team_id=team.team_id,
        name=team.name,
        description=team.description,
        owner_agent_id=team.owner_agent_id,
        owner_name=agent.name,
        member_count=team.member_count,
        memory_count=team.memory_count,
        credits=team.credits,
        total_earned=team.total_earned,
        total_spent=team.total_spent,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at
    ))


@router.get("/teams/{team_id}", tags=["Team"])
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取团队详情"""
    team = await TeamService.get_team_detail(db, team_id)

    if not team:
        raise NOT_FOUND

    return success_response(team)


@router.put("/teams/{team_id}", tags=["Team"])
async def update_team(
    team_id: str,
    req: TeamUpdate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """更新团队信息（仅限 Owner）"""
    team = await TeamService.update_team(db, team_id, agent.agent_id, req)

    if not team:
        raise NOT_FOUND

    return success_response(TeamResponse(
        team_id=team.team_id,
        name=team.name,
        description=team.description,
        owner_agent_id=team.owner_agent_id,
        owner_name=agent.name,
        member_count=team.member_count,
        memory_count=team.memory_count,
        credits=team.credits,
        total_earned=team.total_earned,
        total_spent=team.total_spent,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at
    ))


@router.delete("/teams/{team_id}", tags=["Team"])
async def delete_team(
    team_id: str,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """删除团队（软删除，仅限 Owner）"""
    success = await TeamService.delete_team(db, team_id, agent.agent_id)

    if not success:
        raise NOT_FOUND

    return success_response({"message": "团队已删除"})


@router.get("/teams/{team_id}/members", tags=["Team"])
async def get_team_members(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取成员列表（公开访问）"""
    members = await TeamService.get_team_members(db, team_id)
    return success_response(members)


@router.get("/teams/{team_id}/credits", tags=["Team"])
async def get_team_credits(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取积分池信息（公开访问）"""
    info = await TeamService.get_credits_info(db, team_id)

    if not info:
        raise NOT_FOUND

    return success_response(info)
