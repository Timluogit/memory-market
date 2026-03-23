"""团队成员管理API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.models.schemas import *
from app.models.tables import Agent
from app.services.team_service import MemberService
from app.core.auth import get_current_agent
from app.core.exceptions import (
    success_response,
    NOT_FOUND,
    FORBIDDEN
)
from app.api.dependencies import (
    get_team,
    require_team_admin,
    require_team_member
)

router = APIRouter()


@router.post("/teams/{team_id}/invite", tags=["Team Members"])
async def generate_invite_code(
    team_id: str,
    req: TeamInviteCodeCreate,
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """生成邀请码（需要 Admin 或 Owner 权限）

    生成后可以分享给他人，他们可以通过邀请码加入团队。
    邀请码有效期为 7 天（可配置）。
    """
    invite = await MemberService.generate_invite_code(
        db,
        team_id,
        expires_days=req.expires_days
    )

    return success_response(invite)


@router.post("/teams/{team_id}/join", tags=["Team Members"])
async def join_team_by_code(
    team_id: str,
    req: TeamInviteCodeJoin,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """通过邀请码加入团队

    使用邀请码加入团队。邀请码必须是有效的、未过期的。
    每个邀请码只能使用一次。
    """
    # 验证 team_id 是否匹配邀请码
    from app.models.tables import TeamInviteCode
    from sqlalchemy import select

    result = await db.execute(
        select(TeamInviteCode).where(
            TeamInviteCode.code == req.code,
            TeamInviteCode.is_active == True
        )
    )
    invite = result.scalar_one_or_none()

    if not invite or invite.team_id != team_id:
        from app.core.exceptions import INVALID_PARAMS
        raise INVALID_PARAMS

    result = await MemberService.join_team_by_code(db, agent.agent_id, req.code)

    return success_response(result)


@router.put("/teams/{team_id}/members/{member_id}", tags=["Team Members"])
async def update_member_role(
    team_id: str,
    member_id: int,
    req: TeamMemberRoleUpdate,
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """更新成员角色（需要 Admin 或 Owner 权限）

    可以将成员的角色在 admin 和 member 之间切换。
    不能修改 owner 的角色。
    """
    updated_member = await MemberService.update_member_role(
        db,
        team_id,
        member_id,
        req.role
    )

    if not updated_member:
        raise NOT_FOUND

    return success_response({
        "member_id": member_id,
        "role": updated_member.role
    })


@router.delete("/teams/{team_id}/members/{member_id}", tags=["Team Members"])
async def remove_member(
    team_id: str,
    member_id: int,
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """移除成员（需要 Admin 或 Owner 权限）

    将成员从团队中移除。不能移除 owner。
    被移除的成员将无法访问团队记忆。
    """
    success = await MemberService.remove_member(db, team_id, member_id)

    if not success:
        raise NOT_FOUND

    return success_response({"message": "成员已移除"})


@router.get("/teams/{team_id}/invite-codes", tags=["Team Members"])
async def get_invite_codes(
    team_id: str,
    include_inactive: bool = Query(False, description="是否包含已失效的邀请码"),
    member: dict = Depends(require_team_admin),  # 需要 admin 权限
    db: AsyncSession = Depends(get_db)
):
    """获取邀请码列表（需要 Admin 或 Owner 权限）

    返回团队的所有邀请码，包括有效的和已失效的。
    """
    codes = await MemberService.get_invite_codes(
        db,
        team_id,
        include_inactive=include_inactive
    )

    return success_response(codes)
