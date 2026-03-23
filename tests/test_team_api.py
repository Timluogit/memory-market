"""团队管理API测试"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tables import Agent, Team, TeamMember, TeamInviteCode, TeamCreditTransaction
from app.models.schemas import TeamCreate, TeamUpdate


@pytest.mark.asyncio
class TestTeamAPI:
    """团队管理API测试"""

    async def test_create_team(self, client: AsyncClient, test_agent: Agent, db_session: AsyncSession):
        """测试创建团队"""
        req = TeamCreate(name="测试团队", description="这是一个测试团队")

        response = await client.post(
            "/api/teams",
            json=req.model_dump(),
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "测试团队"
        assert data["description"] == "这是一个测试团队"
        assert data["owner_agent_id"] == test_agent.agent_id
        assert data["member_count"] == 1

    async def test_create_team_duplicate_name(self, client: AsyncClient, test_agent: Agent, db_session: AsyncSession):
        """测试创建同名团队"""
        req = TeamCreate(name="重复团队", description="测试重复名称")

        # 创建第一个团队
        response1 = await client.post(
            "/api/teams",
            json=req.model_dump(),
            headers={"X-API-Key": test_agent.api_key}
        )
        assert response1.status_code == 200

        # 尝试创建同名团队
        response2 = await client.post(
            "/api/teams",
            json=req.model_dump(),
            headers={"X-API-Key": test_agent.api_key}
        )
        assert response2.status_code == 409

    async def test_get_team(self, client: AsyncClient, test_team: Team, db_session: AsyncSession):
        """测试获取团队详情"""
        response = await client.get(f"/api/teams/{test_team.team_id}")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["team_id"] == test_team.team_id
        assert data["name"] == test_team.name

    async def test_get_team_not_found(self, client: AsyncClient, db_session: AsyncSession):
        """测试获取不存在的团队"""
        response = await client.get("/api/teams/team_not_found")

        assert response.status_code == 404

    async def test_update_team(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试更新团队"""
        req = TeamUpdate(name="更新后的团队", description="更新描述")

        response = await client.put(
            f"/api/teams/{test_team.team_id}",
            json=req.model_dump(),
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "更新后的团队"
        assert data["description"] == "更新描述"

    async def test_update_team_unauthorized(self, client: AsyncClient, test_team: Team, other_agent: Agent, db_session: AsyncSession):
        """测试非所有者更新团队"""
        req = TeamUpdate(name="非法更新")

        response = await client.put(
            f"/api/teams/{test_team.team_id}",
            json=req.model_dump(),
            headers={"X-API-Key": other_agent.api_key}
        )

        assert response.status_code == 404  # 非所有者，返回 404

    async def test_delete_team(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试删除团队"""
        response = await client.delete(
            f"/api/teams/{test_team.team_id}",
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200

    async def test_get_team_members(self, client: AsyncClient, test_team: Team, db_session: AsyncSession):
        """测试获取成员列表"""
        response = await client.get(f"/api/teams/{test_team.team_id}/members")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1  # 至少有 owner


@pytest.mark.asyncio
class TestTeamMemberAPI:
    """成员管理API测试"""

    async def test_generate_invite_code(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试生成邀请码"""
        response = await client.post(
            f"/api/teams/{test_team.team_id}/invite",
            json={"expires_days": 7},
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "code" in data
        assert len(data["code"]) == 8

    async def test_join_team_by_code(self, client: AsyncClient, test_team: Team, test_agent: Agent, other_agent: Agent, db_session: AsyncSession):
        """测试通过邀请码加入团队"""
        # 先生成邀请码
        invite_response = await client.post(
            f"/api/teams/{test_team.team_id}/invite",
            json={"expires_days": 7},
            headers={"X-API-Key": test_agent.api_key}
        )
        code = invite_response.json()["data"]["code"]

        # 使用邀请码加入
        response = await client.post(
            f"/api/teams/{test_team.team_id}/join",
            json={"code": code},
            headers={"X-API-Key": other_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["team_id"] == test_team.team_id
        assert data["role"] == "member"

    async def test_join_team_invalid_code(self, client: AsyncClient, test_team: Team, test_agent: Agent, other_agent: Agent, db_session: AsyncSession):
        """测试使用无效邀请码"""
        response = await client.post(
            f"/api/teams/{test_team.team_id}/join",
            json={"code": "INVALID"},
            headers={"X-API-Key": other_agent.api_key}
        )

        assert response.status_code in [400, 422]

    async def test_update_member_role(self, client: AsyncClient, test_team: Team, test_agent: Agent, test_member: TeamMember, db_session: AsyncSession):
        """测试更新成员角色"""
        response = await client.put(
            f"/api/teams/{test_team.team_id}/members/{test_member.id}",
            json={"role": "admin"},
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["role"] == "admin"

    async def test_remove_member(self, client: AsyncClient, test_team: Team, test_agent: Agent, test_member: TeamMember, db_session: AsyncSession):
        """测试移除成员"""
        response = await client.delete(
            f"/api/teams/{test_team.team_id}/members/{test_member.id}",
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200

    async def test_get_invite_codes(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试获取邀请码列表"""
        # 先生成几个邀请码
        await client.post(
            f"/api/teams/{test_team.team_id}/invite",
            json={"expires_days": 7},
            headers={"X-API-Key": test_agent.api_key}
        )

        # 获取邀请码列表
        response = await client.get(
            f"/api/teams/{test_team.team_id}/invite-codes",
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1


@pytest.mark.asyncio
class TestTeamCreditAPI:
    """积分管理API测试"""

    async def test_add_credits(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试充值积分"""
        # 先给 test_agent 充值
        test_agent.credits = 10000
        await db_session.commit()

        response = await client.post(
            f"/api/teams/{test_team.team_id}/credits/add",
            json={"amount": 1000},
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["team_credits"] >= 1000
        assert data["amount"] == 1000

    async def test_add_credits_insufficient_balance(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试余额不足充值"""
        test_agent.credits = 0
        await db_session.commit()

        response = await client.post(
            f"/api/teams/{test_team.team_id}/credits/add",
            json={"amount": 1000},
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 400

    async def test_transfer_credits(self, client: AsyncClient, test_team: Team, test_agent: Agent, other_agent: Agent, db_session: AsyncSession):
        """测试转账"""
        # 先给团队充值
        test_team.credits = 2000
        await db_session.commit()

        response = await client.post(
            f"/api/teams/{test_team.team_id}/credits/transfer",
            json={"to_agent_id": other_agent.agent_id, "amount": 500},
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "team_credits" in data
        assert "agent_credits" in data

    async def test_get_transactions(self, client: AsyncClient, test_team: Team, test_agent: Agent, db_session: AsyncSession):
        """测试获取交易历史"""
        response = await client.get(
            f"/api/teams/{test_team.team_id}/credits/transactions",
            headers={"X-API-Key": test_agent.api_key}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "items" in data
        assert "total" in data


# ============ Fixtures ============

@pytest.fixture
async def test_team(db_session: AsyncSession, test_agent: Agent):
    """测试团队"""
    team = Team(
        name="测试团队",
        description="测试团队描述",
        owner_agent_id=test_agent.agent_id,
        member_count=1,
        is_active=True
    )
    db_session.add(team)
    await db_session.commit()
    await db_session.refresh(team)

    # 添加 owner 成员
    member = TeamMember(
        team_id=team.team_id,
        agent_id=test_agent.agent_id,
        role="owner",
        is_active=True
    )
    db_session.add(member)
    await db_session.commit()

    yield team

    # 清理
    await db_session.delete(team)
    await db_session.commit()


@pytest.fixture
async def test_member(db_session: AsyncSession, test_team: Team, other_agent: Agent):
    """测试成员"""
    member = TeamMember(
        team_id=test_team.team_id,
        agent_id=other_agent.agent_id,
        role="member",
        is_active=True
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)

    yield member

    # 清理
    await db_session.delete(member)
    await db_session.commit()


@pytest.fixture
async def other_agent(db_session: AsyncSession):
    """其他测试 Agent"""
    agent = Agent(
        name="其他测试Agent",
        description="测试用",
        api_key="test_other_api_key",
        credits=100,
        is_active=True
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)

    yield agent

    # 清理
    await db_session.delete(agent)
    await db_session.commit()
