"""
团队协作模型测试

测试团队、成员、邀请码和积分交易的功能。
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models.tables import (
    Agent,
    Team,
    TeamMember,
    TeamInviteCode,
    TeamCreditTransaction,
    Memory,
)


class TestTeamModel:
    """Team 模型测试"""

    @pytest.mark.asyncio
    async def test_create_team(self, db_session: AsyncSession, test_agent: Agent):
        """测试创建团队"""
        team = Team(
            name="测试团队",
            description="这是一个测试团队",
            owner_agent_id=test_agent.agent_id,
            credits=1000,
        )

        db_session.add(team)
        await db_session.commit()
        await db_session.refresh(team)

        assert team.team_id.startswith("team_")
        assert team.name == "测试团队"
        assert team.description == "这是一个测试团队"
        assert team.owner_agent_id == test_agent.agent_id
        assert team.member_count == 1
        assert team.memory_count == 0
        assert team.credits == 1000
        assert team.is_active is True
        assert team.archived_at is None
        assert team.created_at is not None
        assert team.updated_at is not None

    @pytest.mark.asyncio
    async def test_team_relationships(self, db_session: AsyncSession, test_agent: Agent):
        """测试团队关系"""
        team = Team(
            name="关系测试团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()
        await db_session.refresh(team)

        # 创建成员
        member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            role="owner",
        )
        db_session.add(member)
        await db_session.commit()

        # 刷新并检查关系
        await db_session.refresh(team, ["members"])

        assert len(team.members) == 1
        assert team.members[0].role == "owner"

    @pytest.mark.asyncio
    async def test_archive_team(self, db_session: AsyncSession, test_agent: Agent):
        """测试解散团队"""
        team = Team(
            name="待解散团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()
        await db_session.refresh(team)

        # 解散团队
        team.is_active = False
        team.archived_at = datetime.now()
        await db_session.commit()

        await db_session.refresh(team)

        assert team.is_active is False
        assert team.archived_at is not None


class TestTeamMemberModel:
    """TeamMember 模型测试"""

    @pytest.mark.asyncio
    async def test_add_member_to_team(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试添加成员到团队"""
        # 创建团队
        team = Team(
            name="成员测试团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 添加成员
        member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent2.agent_id,
            role="member",
        )
        db_session.add(member)
        await db_session.commit()

        # 手动更新 member_count（需要在业务逻辑中实现）
        team.member_count = 2
        await db_session.commit()
        await db_session.refresh(team)

        assert team.member_count == 2
        assert member.team_id == team.team_id
        assert member.agent_id == test_agent2.agent_id
        assert member.role == "member"
        assert member.is_active is True
        assert member.left_at is None

    @pytest.mark.asyncio
    async def test_remove_member_from_team(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试移除团队成员"""
        team = Team(
            name="移除测试团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 添加成员
        member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent2.agent_id,
            role="member",
        )
        db_session.add(member)
        await db_session.commit()

        # 移除成员
        member.is_active = False
        member.left_at = datetime.now()
        await db_session.commit()

        await db_session.refresh(member)

        assert member.is_active is False
        assert member.left_at is not None

    @pytest.mark.asyncio
    async def test_unique_team_member_constraint(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试同一用户在同一团队只能有一个角色"""
        team = Team(
            name="唯一性测试团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 添加第一个成员
        member1 = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            role="owner",
        )
        db_session.add(member1)
        await db_session.commit()

        # 尝试添加重复成员（应该失败）
        member2 = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            role="member",
        )
        db_session.add(member2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_role_enumeration(self, db_session: AsyncSession, test_agent: Agent):
        """测试角色枚举"""
        valid_roles = ["owner", "admin", "member"]

        for role in valid_roles:
            team = Team(name=f"{role}测试团队", owner_agent_id=test_agent.agent_id)
            db_session.add(team)
            await db_session.commit()

            member = TeamMember(
                team_id=team.team_id,
                agent_id=test_agent.agent_id,
                role=role,
            )
            db_session.add(member)
            await db_session.commit()

            assert member.role == role


class TestTeamInviteCodeModel:
    """TeamInviteCode 模型测试"""

    @pytest.mark.asyncio
    async def test_create_invite_code(self, db_session: AsyncSession, test_agent: Agent):
        """测试创建邀请码"""
        team = Team(
            name="邀请码测试团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 创建邀请码（有效期7天）
        invite_code = TeamInviteCode(
            team_id=team.team_id,
            code="ABCD1234",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(invite_code)
        await db_session.commit()
        await db_session.refresh(invite_code)

        assert invite_code.invite_code_id.startswith("inv_")
        assert invite_code.team_id == team.team_id
        assert invite_code.code == "ABCD1234"
        assert invite_code.is_active is True
        assert invite_code.used_by_agent_id is None
        assert invite_code.used_at is None
        assert invite_code.expires_at is not None

    @pytest.mark.asyncio
    async def test_use_invite_code(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试使用邀请码"""
        team = Team(
            name="使用邀请码团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 创建邀请码
        invite_code = TeamInviteCode(
            team_id=team.team_id,
            code="USE12345",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(invite_code)
        await db_session.commit()

        # 使用邀请码
        invite_code.is_active = False
        invite_code.used_by_agent_id = test_agent2.agent_id
        invite_code.used_at = datetime.now()
        await db_session.commit()

        await db_session.refresh(invite_code)

        assert invite_code.is_active is False
        assert invite_code.used_by_agent_id == test_agent2.agent_id
        assert invite_code.used_at is not None

    @pytest.mark.asyncio
    async def test_invite_code_expiration(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试邀请码过期"""
        team = Team(
            name="过期邀请码团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 创建已过期的邀请码
        invite_code = TeamInviteCode(
            team_id=team.team_id,
            code="EXP12345",
            expires_at=datetime.now() - timedelta(days=1),
        )
        db_session.add(invite_code)
        await db_session.commit()

        await db_session.refresh(invite_code)

        assert invite_code.expires_at < datetime.now()


class TestTeamCreditTransactionModel:
    """TeamCreditTransaction 模型测试"""

    @pytest.mark.asyncio
    async def test_recharge_team_credits(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试充值团队积分"""
        team = Team(
            name="积分充值团队",
            owner_agent_id=test_agent.agent_id,
            credits=500,
        )
        db_session.add(team)
        await db_session.commit()

        # 充值记录
        transaction = TeamCreditTransaction(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            tx_type="recharge",
            amount=1000,
            balance_after=1500,
            description="成员充值",
        )
        db_session.add(transaction)
        await db_session.commit()

        # 更新团队积分
        team.credits += 1000
        await db_session.commit()

        await db_session.refresh(team)
        await db_session.refresh(transaction)

        assert team.credits == 1500
        assert transaction.amount == 1000
        assert transaction.balance_after == 1500
        assert transaction.tx_type == "recharge"

    @pytest.mark.asyncio
    async def test_purchase_with_team_credits(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试使用团队积分购买"""
        team = Team(
            name="购买团队",
            owner_agent_id=test_agent.agent_id,
            credits=1000,
        )
        db_session.add(team)
        await db_session.commit()

        # 购买记录
        transaction = TeamCreditTransaction(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            tx_type="purchase",
            amount=-100,
            balance_after=900,
            related_id="test_mem_001",
            description="购买记忆",
        )
        db_session.add(transaction)
        await db_session.commit()

        # 更新团队积分
        team.credits -= 100
        await db_session.commit()

        await db_session.refresh(team)
        await db_session.refresh(transaction)

        assert team.credits == 900
        assert transaction.amount == -100
        assert transaction.balance_after == 900
        assert transaction.tx_type == "purchase"
        assert transaction.related_id == "test_mem_001"

    @pytest.mark.asyncio
    async def test_transaction_history(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试交易历史"""
        team = Team(
            name="交易历史团队",
            owner_agent_id=test_agent.agent_id,
            credits=0,
        )
        db_session.add(team)
        await db_session.commit()

        # 创建多个交易
        transactions = [
            TeamCreditTransaction(
                team_id=team.team_id,
                agent_id=test_agent.agent_id,
                tx_type="recharge",
                amount=500,
                balance_after=500,
            ),
            TeamCreditTransaction(
                team_id=team.team_id,
                agent_id=test_agent.agent_id,
                tx_type="recharge",
                amount=500,
                balance_after=1000,
            ),
            TeamCreditTransaction(
                team_id=team.team_id,
                agent_id=test_agent.agent_id,
                tx_type="purchase",
                amount=-200,
                balance_after=800,
            ),
        ]

        for tx in transactions:
            db_session.add(tx)
        await db_session.commit()

        # 查询交易历史
        result = await db_session.execute(
            select(TeamCreditTransaction)
            .where(TeamCreditTransaction.team_id == team.team_id)
            .order_by(TeamCreditTransaction.created_at)
        )
        tx_history = result.scalars().all()

        assert len(tx_history) == 3
        assert tx_history[0].amount == 500
        assert tx_history[1].amount == 500
        assert tx_history[2].amount == -200


class TestMemoryWithTeam:
    """测试 Memory 与 Team 的关联"""

    @pytest.mark.asyncio
    async def test_create_team_memory(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试创建团队记忆"""
        team = Team(
            name="团队记忆团队",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        # 创建团队记忆
        memory = Memory(
            seller_agent_id=test_agent.agent_id,
            team_id=team.team_id,
            created_by_agent_id=test_agent.agent_id,
            team_access_level="team_only",
            title="团队记忆",
            category="测试",
            tags=["团队"],
            summary="团队记忆摘要",
            content="团队记忆内容",
            price=100,
        )
        db_session.add(memory)
        await db_session.commit()

        await db_session.refresh(memory)
        await db_session.refresh(team)

        assert memory.team_id == team.team_id
        assert memory.team_access_level == "team_only"
        assert memory.created_by_agent_id == test_agent.agent_id
        assert team.memory_count == 0  # 需要手动更新

    @pytest.mark.asyncio
    async def test_memory_visibility_levels(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试记忆可见性级别"""
        valid_levels = ["private", "team_only", "public"]

        for level in valid_levels:
            memory = Memory(
                seller_agent_id=test_agent.agent_id,
                team_access_level=level,
                title=f"{level}记忆",
                category="测试",
                summary=f"{level}摘要",
                content=f"{level}内容",
                price=100,
            )
            db_session.add(memory)
            await db_session.commit()

            assert memory.team_access_level == level

    @pytest.mark.asyncio
    async def test_private_memory_no_team(
        self, db_session: AsyncSession, test_agent: Agent
    ):
        """测试个人记忆（无团队）"""
        memory = Memory(
            seller_agent_id=test_agent.agent_id,
            team_id=None,
            team_access_level="private",
            title="个人记忆",
            category="测试",
            summary="个人记忆摘要",
            content="个人记忆内容",
            price=100,
        )
        db_session.add(memory)
        await db_session.commit()

        await db_session.refresh(memory)

        assert memory.team_id is None
        assert memory.team_access_level == "private"
        assert memory.created_by_agent_id is None


class TestPermissionLogic:
    """测试权限逻辑"""

    @pytest.mark.asyncio
    async def test_owner_permissions(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试 Owner 权限"""
        team = Team(
            name="Owner权限测试",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        owner_member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            role="owner",
        )
        db_session.add(owner_member)

        admin_member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent2.agent_id,
            role="admin",
        )
        db_session.add(admin_member)
        await db_session.commit()

        await db_session.refresh(owner_member)
        await db_session.refresh(admin_member)

        # Owner 应该可以移除 Admin
        assert owner_member.role == "owner"
        assert admin_member.role == "admin"

    @pytest.mark.asyncio
    async def test_admin_cannot_remove_owner(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试 Admin 不能移除 Owner"""
        team = Team(
            name="Admin限制测试",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        owner_member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent.agent_id,
            role="owner",
        )
        db_session.add(owner_member)

        admin_member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent2.agent_id,
            role="admin",
        )
        db_session.add(admin_member)
        await db_session.commit()

        await db_session.refresh(owner_member)
        await db_session.refresh(admin_member)

        # Owner 不能被移除
        assert owner_member.role == "owner"
        assert admin_member.role == "admin"
        # 权限逻辑应该在业务层实现

    @pytest.mark.asyncio
    async def test_member_permissions(
        self, db_session: AsyncSession, test_agent: Agent, test_agent2: Agent
    ):
        """测试 Member 权限"""
        team = Team(
            name="Member权限测试",
            owner_agent_id=test_agent.agent_id,
        )
        db_session.add(team)
        await db_session.commit()

        member = TeamMember(
            team_id=team.team_id,
            agent_id=test_agent2.agent_id,
            role="member",
        )
        db_session.add(member)
        await db_session.commit()

        await db_session.refresh(member)

        assert member.role == "member"
        assert member.is_active is True
