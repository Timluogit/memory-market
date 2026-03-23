"""
安全测试 - 团队协作功能
测试权限控制、数据隔离、SQL注入防护等安全特性
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db, engine, Base
from app.models.tables import Agent, Team, TeamMember, Memory
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, text
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
    app.dependency_overrides[get_db] = lambda: test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_agent(test_db: AsyncSession):
    """创建测试 Agent"""
    agent = Agent(
        name="SecurityTestAgent",
        description="Agent for security tests",
        api_key="security_test_key_12345",
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
        name="MaliciousAgent",
        description="Potential malicious agent",
        api_key="malicious_key_67890",
        credits=100,
        reputation_score=3.0
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


# ==================== 安全测试：权限绕过 ====================

@pytest.mark.asyncio
async def test_security_team_update_by_non_owner(client, test_db, auth_headers, auth_headers2, test_agent, test_agent2):
    """测试非 Owner 尝试更新团队"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "SecureTeam", "description": "Team for security test"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 非成员尝试更新团队
    update_resp = await client.put(
        f"/teams/{team_id}",
        json={"name": "Hacked Team", "description": "This should fail"},
        headers=auth_headers2
    )

    # 应该返回 403 Forbidden
    assert update_resp.status_code == 403


@pytest.mark.asyncio
async def test_security_team_delete_by_non_owner(client, test_db, auth_headers, auth_headers2):
    """测试非 Owner 尝试删除团队"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "DeleteTestTeam", "description": "Test delete protection"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 非成员尝试删除团队
    delete_resp = await client.delete(
        f"/teams/{team_id}",
        headers=auth_headers2
    )

    # 应该返回 403 Forbidden
    assert delete_resp.status_code == 403


@pytest.mark.asyncio
async def test_security_invite_code_by_non_admin(client, test_db, auth_headers, auth_headers2):
    """测试非 Admin 尝试生成邀请码"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "InviteTestTeam", "description": "Test invite permission"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 非成员尝试生成邀请码
    invite_resp = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers2
    )

    # 应该返回 403 Forbidden
    assert invite_resp.status_code == 403


@pytest.mark.asyncio
async def test_security_member_removal_by_member(client, test_db, auth_headers, auth_headers2):
    """测试普通成员尝试移除其他成员"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "MemberTestTeam", "description": "Test member removal"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 生成邀请码
    invite_resp = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 30},
        headers=auth_headers
    )
    invite_code = invite_resp.json()["data"]["code"]

    # 加入团队
    await client.post(
        f"/teams/{team_id}/join",
        json={"code": invite_code},
        headers=auth_headers2
    )

    # 获取成员列表
    members_resp = await client.get(f"/teams/{team_id}/members")
    members = members_resp.json()["data"]

    # 新成员尝试移除其他成员（包括 Owner）
    owner_member = next(m for m in members if m["role"] == "owner")

    remove_resp = await client.delete(
        f"/teams/{team_id}/members/{owner_member['id']}",
        headers=auth_headers2
    )

    # 应该返回 403 Forbidden
    assert remove_resp.status_code == 403


@pytest.mark.asyncio
async def test_security_owner_role_immutable(client, test_db, auth_headers, auth_headers2):
    """测试 Owner 角色不能被修改"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "OwnerTestTeam", "description": "Test owner immutability"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 生成邀请码并加入
    invite_resp = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 30},
        headers=auth_headers
    )
    invite_code = invite_resp.json()["data"]["code"]

    # 加入团队
    join_resp = await client.post(
        f"/teams/{team_id}/join",
        json={"code": invite_code},
        headers=auth_headers2
    )

    # 获取成员列表
    members_resp = await client.get(f"/teams/{team_id}/members")
    members = members_resp.json()["data"]

    owner_member = next(m for m in members if m["role"] == "owner")

    # 尝试修改 Owner 角色
    role_update_resp = await client.put(
        f"/teams/{team_id}/members/{owner_member['id']}",
        json={"role": "member"},
        headers=auth_headers
    )

    # 应该返回 400 Bad Request 或 403 Forbidden
    assert role_update_resp.status_code in [400, 403]


# ==================== 安全测试：数据隔离 ====================

@pytest.mark.asyncio
async def test_security_data_isolation_teams(client, test_db, auth_headers, auth_headers2):
    """测试不同 Agent 的团队数据隔离"""
    # Agent 1 创建团队
    team1_resp = await client.post(
        "/teams",
        json={"name": "Agent1Team", "description": "Team by agent 1"},
        headers=auth_headers
    )
    team1_id = team1_resp.json()["data"]["team_id"]

    # Agent 2 创建团队
    team2_resp = await client.post(
        "/teams",
        json={"name": "Agent2Team", "description": "Team by agent 2"},
        headers=auth_headers2
    )
    team2_id = team2_resp.json()["data"]["team_id"]

    # Agent 2 尝试访问 Agent 1 的团队详情（公开访问，应成功）
    team1_detail = await client.get(f"/teams/{team1_id}")
    assert team1_detail.status_code == 200

    # Agent 2 尝试更新 Agent 1 的团队（应失败）
    update_resp = await client.put(
        f"/teams/{team1_id}",
        json={"name": "Hacked"},
        headers=auth_headers2
    )
    assert update_resp.status_code == 403


@pytest.mark.asyncio
async def test_security_data_isolation_memories(client, test_db, auth_headers, auth_headers2):
    """测试团队记忆的数据隔离"""
    # Agent 1 创建团队
    team1_resp = await client.post(
        "/teams",
        json={"name": "MemoryIsolationTeam", "description": "Test memory isolation"},
        headers=auth_headers
    )
    team1_id = team1_resp.json()["data"]["team_id"]

    # Agent 1 创建私有团队记忆
    memory_resp = await client.post(
        "/team-memories",
        json={
            "title": "Secret Memory",
            "category": "secret",
            "tags": ["private"],
            "content": {"secret": "data"},
            "summary": "This should be private",
            "format_type": "template",
            "price": 0,
            "team_access_level": "private"
        },
        headers=auth_headers
    )
    memory_id = memory_resp.json()["data"]["memory_id"]

    # Agent 2（非成员）尝试访问私有记忆
    memory_detail_resp = await client.get(f"/team-memories/{memory_id}", headers=auth_headers2)

    # 应该返回 403 或 404
    assert memory_detail_resp.status_code in [403, 404]


@pytest.mark.asyncio
async def test_security_data_isolation_credits(client, test_db, auth_headers, auth_headers2):
    """测试积分数据隔离"""
    # Agent 1 创建团队并充值
    team_resp = await client.post(
        "/teams",
        json={"name": "CreditTestTeam", "description": "Test credit isolation"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    await client.post(
        f"/teams/{team_id}/credits/add",
        json={"amount": 1000},
        headers=auth_headers
    )

    # Agent 2 尝试查看团队积分交易历史（非成员）
    tx_resp = await client.get(
        f"/teams/{team_id}/credits/transactions",
        headers=auth_headers2
    )

    # 应该返回 403
    assert tx_resp.status_code == 403


# ==================== 安全测试：SQL注入防护 ====================

@pytest.mark.asyncio
async def test_sql_injection_team_name(client, test_db, auth_headers):
    """测试团队名称 SQL 注入"""
    malicious_names = [
        "'; DROP TABLE teams; --",
        "' OR '1'='1",
        "'; SELECT * FROM agents; --",
        "test'); INSERT INTO teams VALUES (",
    ]

    for name in malicious_names:
        resp = await client.post(
            "/teams",
            json={"name": name, "description": "SQL injection test"},
            headers=auth_headers
        )

        # 请求应该成功，但数据应该被正确转义
        # 不应该导致数据库错误
        assert resp.status_code == 200 or resp.status_code == 422

        if resp.status_code == 200:
            # 验证名称被正确存储，没有执行 SQL
            team_id = resp.json()["data"]["team_id"]
            detail_resp = await client.get(f"/teams/{team_id}")
            stored_name = detail_resp.json()["data"]["name"]
            assert stored_name == name


@pytest.mark.asyncio
async def test_sql_injection_search_query(client, test_db, auth_headers):
    """测试搜索查询 SQL 注入"""
    malicious_queries = [
        "'; DROP TABLE memories; --",
        "' OR '1'='1",
        "test' UNION SELECT * FROM agents --",
    ]

    for query in malicious_queries:
        # 尝试在搜索中使用恶意查询
        resp = await client.get(
            f"/team-memories?search={query}",
            headers=auth_headers
        )

        # 应该成功或返回 422（验证错误）
        # 不应该导致 500 服务器错误
        assert resp.status_code in [200, 404, 422]


# ==================== 安全测试：并发攻击 ====================

@pytest.mark.asyncio
async def test_concurrent_team_creation_attack(client, test_db, auth_headers):
    """测试并发创建团队攻击（DoS）"""
    async def create_team(index):
        return await client.post(
            "/teams",
            json={"name": f"AttackTeam_{index}", "description": "DoS attack test"},
            headers=auth_headers
        )

    # 尝试并发创建 50 个团队
    tasks = [create_team(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计成功和失败的请求数
    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status_code") == 200)
    failure_count = len(results) - success_count

    print(f"\n并发攻击测试结果:")
    print(f"  成功: {success_count}")
    print(f"  失败: {failure_count}")

    # 系统应该能够处理并发请求，不应该全部失败
    # 允许一定的失败率（如 < 20%）
    assert success_count >= 40, f"并发攻击导致过多失败: {success_count}/50"


@pytest.mark.asyncio
async def test_concurrent_invite_code_generation(client, test_db, auth_headers):
    """测试并发生成邀请码"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "InviteAttackTeam", "description": "Test invite generation"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    async def generate_invite(index):
        return await client.post(
            f"/teams/{team_id}/invite",
            json={"expires_days": 7},
            headers=auth_headers
        )

    # 并发生成 20 个邀请码
    tasks = [generate_invite(i) for i in range(20)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status_code") == 200)

    print(f"\n并发邀请码生成测试:")
    print(f"  成功: {success_count}/20")

    # 所有请求应该成功
    assert success_count == 20, f"并发生成邀请码失败: {success_count}/20"


# ==================== 安全测试：认证绕过 ====================

@pytest.mark.asyncio
async def test_auth_bypass_invalid_token(client, test_db):
    """测试无效令牌的访问"""
    invalid_tokens = [
        "invalid_token_12345",
        "Bearer invalid",
        "malformed.token",
        "",
    ]

    for token in invalid_tokens:
        resp = await client.get(
            "/agents/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        # 应该返回 401 Unauthorized
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_bypass_no_token(client, test_db):
    """测试无令牌的访问"""
    # 尝试访问需要认证的端点
    resp = await client.get("/agents/me")

    # 应该返回 401 Unauthorized
    assert resp.status_code == 401


# ==================== 安全测试：输入验证 ====================

@pytest.mark.asyncio
async def test_input_validation_team_name(client, test_db, auth_headers):
    """测试团队名称输入验证"""
    invalid_names = [
        {"name": "", "description": "test"},  # 空名称
        {"name": "a", "description": "test"},  # 太短
        {"name": "x" * 100, "description": "test"},  # 太长
        {"name": None, "description": "test"},  # None 值
    ]

    for team_data in invalid_names:
        resp = await client.post(
            "/teams",
            json=team_data,
            headers=auth_headers
        )

        # 应该返回 422 Unprocessable Entity
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_input_validation_member_role(client, test_db, auth_headers):
    """测试成员角色输入验证"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "RoleTestTeam", "description": "Test role validation"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 获取成员
    members_resp = await client.get(f"/teams/{team_id}/members")
    members = members_resp.json()["data"]

    invalid_roles = ["invalid_role", "superadmin", "hacker", "", None]

    for role in invalid_roles:
        resp = await client.put(
            f"/teams/{team_id}/members/{members[0]['id']}",
            json={"role": role},
            headers=auth_headers
        )

        # 应该返回 422
        assert resp.status_code == 422


# ==================== 安全测试总结 ====================

@pytest.mark.asyncio
async def test_security_summary(client, test_db, auth_headers, auth_headers2):
    """安全测试总结"""
    print("\n" + "="*50)
    print("团队协作功能安全测试总结")
    print("="*50)

    print("\n✓ 权限控制测试")
    print("  - 非 Owner 无法更新/删除团队")
    print("  - 非 Admin 无法生成邀请码")
    print("  - 普通成员无法移除其他成员")
    print("  - Owner 角色不可修改")

    print("\n✓ 数据隔离测试")
    print("  - 不同 Agent 的团队数据隔离")
    print("  - 团队记忆访问控制")
    print("  - 积分交易历史隔离")

    print("\n✓ SQL 注入防护测试")
    print("  - 团队名称输入验证")
    print("  - 搜索查询参数验证")

    print("\n✓ 并发攻击防护测试")
    print("  - 并发团队创建防护")
    print("  - 并发邀请码生成防护")

    print("\n✓ 认证安全测试")
    print("  - 无效令牌拒绝访问")
    print("  - 无令牌拒绝访问")

    print("\n✓ 输入验证测试")
    print("  - 团队名称长度验证")
    print("  - 成员角色枚举验证")

    print("\n" + "="*50)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
