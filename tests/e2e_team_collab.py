"""
端到端测试 - 团队协作功能
测试完整的团队创建、成员管理、记忆协作和购买流程
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db, engine, Base
from app.models.tables import Agent, Team, TeamMember, TeamInviteCode, Memory, TeamCreditTransaction
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from datetime import datetime, timedelta


# ==================== 测试数据库配置 ====================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def get_test_db():
    async with TestSessionLocal() as session:
        yield session


# ==================== Fixture ====================

@pytest.fixture(scope="function")
async def test_db():
    """创建测试数据库"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(test_db):
    """创建测试客户端"""
    from unittest.mock import AsyncMock

    # Mock database dependency
    app.dependency_overrides[get_db] = lambda: test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_agent(test_db: AsyncSession):
    """创建测试 Agent"""
    agent = Agent(
        name="TestAgent",
        description="Test agent for e2e tests",
        api_key="test_api_key_12345",
        credits=1000,
        reputation_score=5.0
    )
    test_db.add(agent)
    await test_db.commit()
    await test_db.refresh(agent)
    return agent


@pytest.fixture
async def test_agent2(test_db: AsyncSession):
    """创建第二个测试 Agent"""
    agent = Agent(
        name="TestAgent2",
        description="Second test agent",
        api_key="test_api_key_67890",
        credits=500,
        reputation_score=4.5
    )
    test_db.add(agent)
    await test_db.commit()
    await test_db.refresh(agent)
    return agent


@pytest.fixture
async def auth_headers(test_agent):
    """获取认证头"""
    return {"Authorization": f"Bearer {test_agent.api_key}"}


@pytest.fixture
async def auth_headers2(test_agent2):
    """获取第二个 Agent 的认证头"""
    return {"Authorization": f"Bearer {test_agent2.api_key}"}


# ==================== 端到端测试：团队创建流程 ====================

@pytest.mark.asyncio
async def test_e2e_team_creation(client, auth_headers, test_agent):
    """测试完整的团队创建流程"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "测试团队", "description": "这是一个测试团队"},
        headers=auth_headers
    )
    assert create_response.status_code == 200
    data = create_response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "测试团队"
    assert data["data"]["owner_agent_id"] == test_agent.agent_id
    assert data["data"]["member_count"] == 1

    team_id = data["data"]["team_id"]

    # 2. 获取团队详情
    detail_response = await client.get(f"/teams/{team_id}")
    assert detail_response.status_code == 200
    data = detail_response.json()
    assert data["success"] is True
    assert data["data"]["team_id"] == team_id
    assert data["data"]["owner_name"] == "TestAgent"

    # 3. 更新团队信息
    update_response = await client.put(
        f"/teams/{team_id}",
        json={"name": "更新后的团队", "description": "更新后的描述"},
        headers=auth_headers
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["data"]["name"] == "更新后的团队"


# ==================== 端到端测试：成员邀请和加入流程 ====================

@pytest.mark.asyncio
async def test_e2e_member_invitation(client, test_db, auth_headers, auth_headers2, test_agent, test_agent2):
    """测试完整的成员邀请和加入流程"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "测试团队", "description": "测试邀请功能"},
        headers=auth_headers
    )
    team_id = create_response.json()["data"]["team_id"]

    # 2. 生成邀请码
    invite_response = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers
    )
    assert invite_response.status_code == 200
    data = invite_response.json()
    assert data["success"] is True
    invite_code = data["data"]["code"]

    # 3. 通过邀请码加入团队
    join_response = await client.post(
        f"/teams/{team_id}/join",
        json={"code": invite_code},
        headers=auth_headers2
    )
    assert join_response.status_code == 200
    data = join_response.json()
    assert data["success"] is True
    assert data["data"]["role"] == "member"

    # 4. 获取成员列表
    members_response = await client.get(f"/teams/{team_id}/members")
    assert members_response.status_code == 200
    data = members_response.json()
    assert len(data["data"]) == 2  # Owner + Member

    # 5. 更新成员角色
    members = data["data"]
    member_id = next(m["id"] for m in members if m["agent_id"] == test_agent2.agent_id)
    role_update_response = await client.put(
        f"/teams/{team_id}/members/{member_id}",
        json={"role": "admin"},
        headers=auth_headers
    )
    assert role_update_response.status_code == 200


# ==================== 端到端测试：团队记忆创建和编辑 ====================

@pytest.mark.asyncio
async def test_e2e_team_memory(client, test_db, auth_headers, test_agent):
    """测试团队记忆的创建和编辑"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "记忆团队", "description": "测试记忆功能"},
        headers=auth_headers
    )
    team_id = create_response.json()["data"]["team_id"]

    # 2. 创建团队记忆
    memory_response = await client.post(
        "/team-memories",
        json={
            "title": "团队测试记忆",
            "category": "测试/示例",
            "tags": ["团队", "测试"],
            "content": {"key": "value"},
            "summary": "这是一个团队测试记忆",
            "format_type": "template",
            "price": 50,
            "team_access_level": "team_only"
        },
        headers=auth_headers
    )
    assert memory_response.status_code == 200
    data = memory_response.json()
    assert data["success"] is True
    memory_id = data["data"]["memory_id"]
    assert data["data"]["team_access_level"] == "team_only"

    # 3. 获取团队记忆列表
    list_response = await client.get(f"/teams/{team_id}/memories", headers=auth_headers)
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data["data"]["items"]) >= 1

    # 4. 更新团队记忆
    update_response = await client.put(
        f"/team-memories/{memory_id}",
        json={
            "summary": "更新后的摘要",
            "changelog": "更新摘要"
        },
        headers=auth_headers
    )
    assert update_response.status_code == 200


# ==================== 端到端测试：团队购买流程 ====================

@pytest.mark.asyncio
async def test_e2e_team_purchase(client, test_db, auth_headers, auth_headers2, test_agent, test_agent2):
    """测试团队购买记忆的完整流程"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "购买团队", "description": "测试购买功能"},
        headers=auth_headers
    )
    team_id = create_response.json()["data"]["team_id"]

    # 2. 充值团队积分
    credit_response = await client.post(
        f"/teams/{team_id}/credits/add",
        json={"amount": 500},
        headers=auth_headers
    )
    assert credit_response.status_code == 200
    data = credit_response.json()
    assert data["data"]["team_credits"] >= 500

    # 3. 创建一个公开记忆（由另一个 Agent）
    memory_response = await client.post(
        "/memories",
        json={
            "title": "可购买的记忆",
            "category": "销售/测试",
            "tags": ["购买"],
            "content": {"data": "test"},
            "summary": "可以购买的测试记忆",
            "format_type": "template",
            "price": 100
        },
        headers=auth_headers2
    )
    memory_id = memory_response.json()["data"]["memory_id"]

    # 4. 团队购买记忆
    purchase_response = await client.post(
        f"/teams/{team_id}/memories/purchase",
        json={"memory_id": memory_id},
        headers=auth_headers
    )
    assert purchase_response.status_code == 200
    data = purchase_response.json()
    assert data["success"] is True
    assert data["data"]["credits_spent"] == 100

    # 5. 验证团队积分减少
    team_info = await client.get(f"/teams/{team_id}/credits")
    assert team_info.status_code == 200
    data = team_info.json()
    assert data["data"]["credits"] < 500


# ==================== 端到端测试：权限验证 ====================

@pytest.mark.asyncio
async def test_e2e_permission_checks(client, test_db, auth_headers, auth_headers2, test_agent, test_agent2):
    """测试权限验证"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "权限测试团队", "description": "测试权限"},
        headers=auth_headers
    )
    team_id = create_response.json()["data"]["team_id"]

    # 2. 尝试用非 Owner 更新团队（应该失败）
    update_response = await client.put(
        f"/teams/{team_id}",
        json={"name": "尝试修改"},
        headers=auth_headers2
    )
    assert update_response.status_code == 403  # Forbidden

    # 3. 生成邀请码需要 Admin 权限（非成员不能生成）
    invite_response = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers2
    )
    assert invite_response.status_code == 403  # Forbidden

    # 4. 加入团队后，仍然不能生成邀请码（需要 Admin 权限）
    invite_code_response = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers
    )
    invite_code = invite_code_response.json()["data"]["code"]

    join_response = await client.post(
        f"/teams/{team_id}/join",
        json={"code": invite_code},
        headers=auth_headers2
    )
    assert join_response.status_code == 200

    # 5. 成员尝试生成邀请码（应该失败）
    invite_member_response = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers2
    )
    assert invite_member_response.status_code == 403  # Forbidden


# ==================== 端到端测试：团队删除 ====================

@pytest.mark.asyncio
async def test_e2e_team_deletion(client, test_db, auth_headers, test_agent):
    """测试团队删除（软删除）"""
    # 1. 创建团队
    create_response = await client.post(
        "/teams",
        json={"name": "待删除团队", "description": "将被删除"},
        headers=auth_headers
    )
    team_id = create_response.json()["data"]["team_id"]

    # 2. 删除团队
    delete_response = await client.delete(
        f"/teams/{team_id}",
        headers=auth_headers
    )
    assert delete_response.status_code == 200
    data = delete_response.json()
    assert data["success"] is True

    # 3. 验证团队已被软删除
    detail_response = await client.get(f"/teams/{team_id}")
    assert detail_response.status_code == 404  # Not Found


# ==================== 端到端测试：完整工作流 ====================

@pytest.mark.asyncio
async def test_e2e_complete_workflow(client, test_db, auth_headers, auth_headers2, test_agent, test_agent2):
    """测试完整的团队协作工作流"""
    # 阶段 1：创建团队
    team_response = await client.post(
        "/teams",
        json={"name": "完整测试团队", "description": "完整工作流测试"},
        headers=auth_headers
    )
    team_id = team_response.json()["data"]["team_id"]

    # 阶段 2：邀请成员
    invite_response = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers
    )
    invite_code = invite_response.json()["data"]["code"]

    join_response = await client.post(
        f"/teams/{team_id}/join",
        json={"code": invite_code},
        headers=auth_headers2
    )
    assert join_response.status_code == 200

    # 阶段 3：充值团队积分
    credit_response = await client.post(
        f"/teams/{team_id}/credits/add",
        json={"amount": 1000},
        headers=auth_headers
    )
    assert credit_response.json()["data"]["team_credits"] >= 1000

    # 阶段 4：创建团队记忆
    memory_response = await client.post(
        "/team-memories",
        json={
            "title": "团队共享知识",
            "category": "知识库",
            "tags": ["共享"],
            "content": {"knowledge": "shared"},
            "summary": "团队共享的知识库",
            "format_type": "template",
            "price": 0,
            "team_access_level": "team_only"
        },
        headers=auth_headers
    )
    memory_id = memory_response.json()["data"]["memory_id"]

    # 阶段 5：成员查看团队记忆
    list_response = await client.get(
        f"/teams/{team_id}/memories",
        headers=auth_headers2
    )
    assert len(list_response.json()["data"]["items"]) >= 1

    # 阶段 6：升级成员为 Admin
    members = (await client.get(f"/teams/{team_id}/members")).json()["data"]
    member_id = next(m["id"] for m in members if m["agent_id"] == test_agent2.agent_id)

    await client.put(
        f"/teams/{team_id}/members/{member_id}",
        json={"role": "admin"},
        headers=auth_headers
    )

    # 阶段 7：新 Admin 生成邀请码
    new_invite = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers2
    )
    assert new_invite.status_code == 200

    # 阶段 8：删除团队
    await client.delete(f"/teams/{team_id}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
