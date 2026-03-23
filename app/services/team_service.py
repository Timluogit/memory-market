"""团队管理服务层"""
from typing import Optional, List
from datetime import datetime, timedelta
import random
import string

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

import app.models.tables as tables
from app.models.tables import Team, TeamMember, TeamInviteCode, TeamCreditTransaction, Agent, Memory
from app.models.schemas import (
    TeamCreate, TeamUpdate, TeamResponse, TeamMemberResponse,
    TeamInviteCodeResponse, TeamCreditTransaction
)
from app.core.exceptions import AppError, ALREADY_EXISTS, INVALID_PARAMS, NOT_FOUND


def generate_invite_code() -> str:
    """生成8位邀请码"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


# ============ TeamService ============

class TeamService:
    """团队业务逻辑"""

    @staticmethod
    async def create_team(
        db: AsyncSession,
        owner_agent_id: str,
        req: TeamCreate
    ) -> Team:
        """创建团队"""
        # 检查团队名称是否重复（同一 owner 下）
        result = await db.execute(
            select(Team).where(
                Team.owner_agent_id == owner_agent_id,
                Team.name == req.name,
                Team.is_active == True
            )
        )
        if result.scalar_one_or_none():
            raise AppError(
                code="TEAM_NAME_EXISTS",
                message="团队名称已存在",
                status_code=409
            )

        # 创建团队
        team = Team(
            name=req.name,
            description=req.description,
            owner_agent_id=owner_agent_id,
            member_count=1,
            memory_count=0,
            credits=0,
            total_earned=0,
            total_spent=0,
            is_active=True
        )
        db.add(team)
        await db.flush()  # 获取 team_id

        # 添加 owner 为成员
        member = TeamMember(
            team_id=team.team_id,
            agent_id=owner_agent_id,
            role="owner",
            is_active=True
        )
        db.add(member)

        await db.commit()
        await db.refresh(team)

        return team

    @staticmethod
    async def get_team_detail(
        db: AsyncSession,
        team_id: str
    ) -> Optional[TeamResponse]:
        """获取团队详情"""
        result = await db.execute(
            select(Team, Agent)
            .join(Agent, Team.owner_agent_id == Agent.agent_id)
            .where(Team.team_id == team_id, Team.is_active == True)
        )
        row = result.scalar_one_or_none()

        if not row:
            return None

        team = row[0] if isinstance(row, tuple) else row
        owner = row[1] if isinstance(row, tuple) else None

        return TeamResponse(
            team_id=team.team_id,
            name=team.name,
            description=team.description,
            owner_agent_id=team.owner_agent_id,
            owner_name=owner.name if owner else "",
            member_count=team.member_count,
            memory_count=team.memory_count,
            credits=team.credits,
            total_earned=team.total_earned,
            total_spent=team.total_spent,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at
        )

    @staticmethod
    async def update_team(
        db: AsyncSession,
        team_id: str,
        owner_agent_id: str,
        req: TeamUpdate
    ) -> Optional[Team]:
        """更新团队信息"""
        # 构建更新数据
        update_data = {}
        if req.name is not None:
            update_data["name"] = req.name
        if req.description is not None:
            update_data["description"] = req.description

        if not update_data:
            raise INVALID_PARAMS

        # 检查团队名称是否重复
        if "name" in update_data:
            result = await db.execute(
                select(Team).where(
                    Team.team_id != team_id,
                    Team.owner_agent_id == owner_agent_id,
                    Team.name == req.name,
                    Team.is_active == True
                )
            )
            if result.scalar_one_or_none():
                raise AppError(
                    code="TEAM_NAME_EXISTS",
                    message="团队名称已存在",
                    status_code=409
                )

        # 更新
        result = await db.execute(
            update(Team)
            .where(Team.team_id == team_id, Team.owner_agent_id == owner_agent_id)
            .values(**update_data)
            .returning(Team)
        )
        team = result.scalar_one_or_none()

        if not team:
            return None

        await db.commit()
        await db.refresh(team)

        return team

    @staticmethod
    async def delete_team(
        db: AsyncSession,
        team_id: str,
        owner_agent_id: str
    ) -> bool:
        """删除团队（软删除）"""
        result = await db.execute(
            update(Team)
            .where(
                Team.team_id == team_id,
                Team.owner_agent_id == owner_agent_id,
                Team.is_active == True
            )
            .values(
                is_active=False,
                archived_at=datetime.now()
            )
        )

        if result.rowcount == 0:
            return False

        # 将所有成员设置为非活跃
        await db.execute(
            update(TeamMember)
            .where(TeamMember.team_id == team_id)
            .values(is_active=False, left_at=datetime.now())
        )

        # 使所有邀请码失效
        await db.execute(
            update(TeamInviteCode)
            .where(TeamInviteCode.team_id == team_id, TeamInviteCode.is_active == True)
            .values(is_active=False)
        )

        await db.commit()
        return True

    @staticmethod
    async def get_team_members(
        db: AsyncSession,
        team_id: str
    ) -> List[TeamMemberResponse]:
        """获取成员列表"""
        result = await db.execute(
            select(TeamMember, Agent)
            .join(Agent, TeamMember.agent_id == Agent.agent_id)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True
            )
            .order_by(TeamMember.joined_at)
        )

        members = []
        for row in result:
            member = row[0]
            agent = row[1]
            members.append(TeamMemberResponse(
                id=member.id,
                team_id=member.team_id,
                agent_id=member.agent_id,
                agent_name=agent.name,
                role=member.role,
                joined_at=member.joined_at,
                is_active=member.is_active
            ))

        return members

    @staticmethod
    async def get_credits_info(
        db: AsyncSession,
        team_id: str
    ) -> dict:
        """获取积分池信息"""
        result = await db.execute(
            select(Team).where(Team.team_id == team_id)
        )
        team = result.scalar_one_or_none()

        if not team:
            return None

        return {
            "team_id": team.team_id,
            "credits": team.credits,
            "total_earned": team.total_earned,
            "total_spent": team.total_spent
        }


# ============ MemberService ============

class MemberService:
    """成员管理业务逻辑"""

    @staticmethod
    async def generate_invite_code(
        db: AsyncSession,
        team_id: str,
        expires_days: int = 7
    ) -> TeamInviteCodeResponse:
        """生成邀请码"""
        # 生成邀请码
        code = generate_invite_code()

        # 检查是否重复（极小概率）
        result = await db.execute(
            select(TeamInviteCode).where(
                TeamInviteCode.code == code,
                TeamInviteCode.is_active == True
            )
        )
        while result.scalar_one_or_none():
            code = generate_invite_code()
            result = await db.execute(
                select(TeamInviteCode).where(
                    TeamInviteCode.code == code,
                    TeamInviteCode.is_active == True
                )
            )

        # 创建邀请码
        invite = TeamInviteCode(
            team_id=team_id,
            code=code,
            is_active=True,
            expires_at=datetime.now() + timedelta(days=expires_days)
        )
        db.add(invite)
        await db.commit()
        await db.refresh(invite)

        return TeamInviteCodeResponse(
            invite_code_id=invite.invite_code_id,
            team_id=invite.team_id,
            code=invite.code,
            is_active=invite.is_active,
            expires_at=invite.expires_at,
            created_at=invite.created_at
        )

    @staticmethod
    async def get_invite_codes(
        db: AsyncSession,
        team_id: str,
        include_inactive: bool = False
    ) -> List[TeamInviteCodeResponse]:
        """获取邀请码列表"""
        query = select(TeamInviteCode).where(TeamInviteCode.team_id == team_id)

        if not include_inactive:
            query = query.where(TeamInviteCode.is_active == True)

        query = query.order_by(TeamInviteCode.created_at.desc())

        result = await db.execute(query)
        invites = result.scalars().all()

        return [
            TeamInviteCodeResponse(
                invite_code_id=inv.invite_code_id,
                team_id=inv.team_id,
                code=inv.code,
                is_active=inv.is_active,
                expires_at=inv.expires_at,
                created_at=inv.created_at
            )
            for inv in invites
        ]

    @staticmethod
    async def join_team_by_code(
        db: AsyncSession,
        agent_id: str,
        code: str
    ) -> dict:
        """通过邀请码加入团队"""
        # 查找邀请码
        result = await db.execute(
            select(TeamInviteCode).where(
                TeamInviteCode.code == code,
                TeamInviteCode.is_active == True
            )
        )
        invite = result.scalar_one_or_none()

        if not invite:
            raise AppError(
                code="INVALID_INVITE_CODE",
                message="邀请码无效或已过期",
                status_code=400
            )

        # 检查是否过期
        if invite.expires_at < datetime.now():
            invite.is_active = False
            await db.commit()
            raise AppError(
                code="INVITE_CODE_EXPIRED",
                message="邀请码已过期",
                status_code=400
            )

        # 检查是否已经在团队中
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == invite.team_id,
                TeamMember.agent_id == agent_id,
                TeamMember.is_active == True
            )
        )
        if result.scalar_one_or_none():
            raise AppError(
                code="ALREADY_IN_TEAM",
                message="已经是团队成员",
                status_code=409
            )

        # 加入团队
        member = TeamMember(
            team_id=invite.team_id,
            agent_id=agent_id,
            role="member",
            is_active=True
        )
        db.add(member)

        # 更新邀请码状态
        invite.used_by_agent_id = agent_id
        invite.used_at = datetime.now()
        invite.is_active = False

        # 更新团队成员数
        await db.execute(
            update(Team)
            .where(Team.team_id == invite.team_id)
            .values(member_count=Team.member_count + 1)
        )

        await db.commit()

        return {
            "team_id": invite.team_id,
            "role": "member"
        }

    @staticmethod
    async def update_member_role(
        db: AsyncSession,
        team_id: str,
        member_id: int,
        new_role: str
    ) -> Optional[TeamMember]:
        """更新成员角色"""
        # 不能修改 owner
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
                TeamMember.role != "owner"
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            return None

        # 更新角色
        member.role = new_role
        await db.commit()
        await db.refresh(member)

        return member

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        team_id: str,
        member_id: int
    ) -> bool:
        """移除成员"""
        # 不能移除 owner
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
                TeamMember.role != "owner"
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            return False

        # 设置为非活跃
        member.is_active = False
        member.left_at = datetime.now()

        # 更新团队成员数
        await db.execute(
            update(Team)
            .where(Team.team_id == team_id)
            .values(member_count=Team.member_count - 1)
        )

        await db.commit()
        return True


# ============ CreditService ============

class CreditService:
    """积分管理业务逻辑"""

    @staticmethod
    async def add_credits(
        db: AsyncSession,
        team_id: str,
        agent_id: str,
        amount: int
    ) -> Team:
        """充值积分"""
        # 获取团队
        result = await db.execute(
            select(Team).where(Team.team_id == team_id)
        )
        team = result.scalar_one_or_none()

        if not team:
            raise NOT_FOUND

        # 更新积分
        team.credits += amount
        team.total_earned += amount

        # 创建交易记录
        transaction = tables.TeamCreditTransaction(
            team_id=team_id,
            agent_id=agent_id,
            tx_type="recharge",
            amount=amount,
            balance_after=team.credits,
            description=f"充值 {amount} 积分"
        )
        db.add(transaction)

        await db.commit()
        await db.refresh(team)

        return team

    @staticmethod
    async def transfer_credits(
        db: AsyncSession,
        team_id: str,
        from_agent_id: str,
        to_agent_id: str,
        amount: int
    ) -> dict:
        """转账（从团队积分池转到成员个人积分）"""
        # 获取团队
        result = await db.execute(
            select(Team).where(Team.team_id == team_id)
        )
        team = result.scalar_one_or_none()

        if not team:
            raise NOT_FOUND

        # 检查余额
        if team.credits < amount:
            raise AppError(
                code="INSUFFICIENT_CREDITS",
                message="团队积分不足",
                status_code=400
            )

        # 更新团队积分
        team.credits -= amount
        team.total_spent += amount

        # 更新成员积分
        result = await db.execute(
            select(Agent).where(Agent.agent_id == to_agent_id)
        )
        to_agent = result.scalar_one_or_none()

        if not to_agent:
            raise NOT_FOUND

        to_agent.credits += amount
        to_agent.total_earned += amount

        # 创建团队交易记录
        team_tx = tables.TeamCreditTransaction(
            team_id=team_id,
            agent_id=from_agent_id,
            tx_type="purchase",  # 从团队池购买
            amount=-amount,
            balance_after=team.credits,
            related_id=to_agent_id,
            description=f"转账给 {to_agent.name}"
        )
        db.add(team_tx)

        # 创建成员交易记录
        agent_tx = tables.Transaction(
            agent_id=to_agent_id,
            tx_type="bonus",  # 团队分红
            amount=amount,
            balance_after=to_agent.credits,
            description=f"团队 {team.name} 分红"
        )
        db.add(agent_tx)

        await db.commit()

        return {
            "team_credits": team.credits,
            "agent_credits": to_agent.credits
        }

    @staticmethod
    async def get_transactions(
        db: AsyncSession,
        team_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """获取交易历史"""
        # 获取总数
        count_result = await db.execute(
            select(func.count(tables.TeamCreditTransaction.tx_id))
            .where(tables.TeamCreditTransaction.team_id == team_id)
        )
        total = count_result.scalar()

        # 获取记录
        result = await db.execute(
            select(tables.TeamCreditTransaction, Agent)
            .outerjoin(Agent, tables.TeamCreditTransaction.agent_id == Agent.agent_id)
            .where(tables.TeamCreditTransaction.team_id == team_id)
            .order_by(tables.TeamCreditTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        items = []
        for row in result:
            tx = row[0]
            agent = row[1]
            items.append(TeamCreditTransaction(
                tx_id=tx.tx_id,
                team_id=tx.team_id,
                agent_id=tx.agent_id,
                agent_name=agent.name if agent else None,
                tx_type=tx.tx_type,
                amount=tx.amount,
                balance_after=tx.balance_after,
                related_id=tx.related_id,
                description=tx.description,
                created_at=tx.created_at
            ))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
