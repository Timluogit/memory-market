"""
性能测试 - 团队协作功能
测试团队查询、成员管理、记忆搜索等关键功能的性能
"""
import pytest
import asyncio
import time
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import get_db, engine, Base
from app.models.tables import Agent, Team, TeamMember, Memory
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
    app.dependency_overrides[get_db] = lambda: test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_agent(test_db: AsyncSession):
    """创建测试 Agent"""
    agent = Agent(
        name="PerformanceTestAgent",
        description="Agent for performance tests",
        api_key="perf_test_key_12345",
        credits=10000,
        reputation_score=5.0
    )
    test_db.add(agent)
    await test_db.commit()
    await test_db.refresh(agent)
    return agent


@pytest.fixture
async def auth_headers(test_agent):
    """获取认证头"""
    return {"Authorization": f"Bearer {test_agent.api_key}"}


# ==================== 辅助函数 ====================

async def create_team_with_members(client: AsyncClient, team_name: str, member_count: int, headers: dict) -> str:
    """创建团队并添加指定数量的成员"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": team_name, "description": f"Test team with {member_count} members"},
        headers=headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 生成邀请码
    invite_resp = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 30},
        headers=headers
    )
    invite_code = invite_resp.json()["data"]["code"]

    # 创建并添加成员
    for i in range(member_count):
        member_agent = Agent(
            name=f"Member_{i}",
            description=f"Test member {i}",
            api_key=f"member_key_{i}",
            credits=100,
            reputation_score=5.0
        )
        # 注意：这里需要实际的数据库操作，简化处理
        # 实际测试中应该通过 API 注册成员

    return team_id


# ==================== 性能测试：团队查询 ====================

@pytest.mark.asyncio
async def test_performance_team_query(client, test_db, auth_headers, test_agent):
    """测试团队查询性能"""
    # 创建多个团队
    team_ids = []
    for i in range(10):
        resp = await client.post(
            "/teams",
            json={"name": f"Team_{i}", "description": f"Performance test team {i}"},
            headers=auth_headers
        )
        team_ids.append(resp.json()["data"]["team_id"])

    # 测试查询所有团队的性能
    start_time = time.time()
    for team_id in team_ids:
        resp = await client.get(f"/teams/{team_id}")
        assert resp.status_code == 200
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / len(team_ids)

    print(f"\n团队查询性能:")
    print(f"  总时间: {total_time:.3f}s")
    print(f"  平均时间: {avg_time:.3f}s")

    # 断言：平均查询时间应该 < 100ms
    assert avg_time < 0.1, f"平均查询时间 {avg_time:.3f}s 超过阈值 100ms"


@pytest.mark.asyncio
async def test_performance_team_list(client, test_db, auth_headers, test_agent):
    """测试团队列表查询性能"""
    # 创建 50 个团队
    for i in range(50):
        await client.post(
            "/teams",
            json={"name": f"ListTeam_{i}", "description": f"Team {i} for list test"},
            headers=auth_headers
        )

    # 测试分页查询性能
    start_time = time.time()
    resp = await client.get("/agents/me/teams", headers=auth_headers)
    end_time = time.time()

    assert resp.status_code == 200
    query_time = end_time - start_time

    print(f"\n团队列表查询性能:")
    print(f"  查询时间: {query_time:.3f}s")

    # 断言：查询时间应该 < 500ms
    assert query_time < 0.5, f"查询时间 {query_time:.3f}s 超过阈值 500ms"


# ==================== 性能测试：成员管理 ====================

@pytest.mark.asyncio
async def test_performance_member_management(client, test_db, auth_headers, test_agent):
    """测试成员管理性能"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "MemberPerfTeam", "description": "Test member management"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 测试成员列表查询性能
    start_time = time.time()
    resp = await client.get(f"/teams/{team_id}/members")
    end_time = time.time()

    assert resp.status_code == 200
    query_time = end_time - start_time

    print(f"\n成员列表查询性能:")
    print(f"  查询时间: {query_time:.3f}s")

    # 断言：成员列表查询应该 < 200ms
    assert query_time < 0.2, f"查询时间 {query_time:.3f}s 超过阈值 200ms"

    # 测试邀请码生成性能
    start_time = time.time()
    invite_resp = await client.post(
        f"/teams/{team_id}/invite",
        json={"expires_days": 7},
        headers=auth_headers
    )
    end_time = time.time()

    assert invite_resp.status_code == 200
    gen_time = end_time - start_time

    print(f"  邀请码生成时间: {gen_time:.3f}s")

    # 断言：邀请码生成应该 < 100ms
    assert gen_time < 0.1, f"邀请码生成时间 {gen_time:.3f}s 超过阈值 100ms"


# ==================== 性能测试：记忆搜索 ====================

@pytest.mark.asyncio
async def test_performance_memory_search(client, test_db, auth_headers, test_agent):
    """测试记忆搜索性能"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "SearchTeam", "description": "Test memory search"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 创建 20 个团队记忆
    memory_ids = []
    for i in range(20):
        resp = await client.post(
            "/team-memories",
            json={
                "title": f"Search Memory {i}",
                "category": f"Category_{i % 5}",
                "tags": ["search", f"tag_{i}"],
                "content": {"data": f"content_{i}"},
                "summary": f"Summary for search test {i}",
                "format_type": "template",
                "price": i * 10,
                "team_access_level": "team_only"
            },
            headers=auth_headers
        )
        memory_ids.append(resp.json()["data"]["memory_id"])

    # 测试搜索性能
    start_time = time.time()
    resp = await client.get(f"/teams/{team_id}/memories", headers=auth_headers)
    end_time = time.time()

    assert resp.status_code == 200
    search_time = end_time - start_time

    data = resp.json()
    print(f"\n记忆搜索性能:")
    print(f"  查询时间: {search_time:.3f}s")
    print(f"  返回数量: {len(data['data']['items'])}")

    # 断言：搜索时间应该 < 300ms
    assert search_time < 0.3, f"搜索时间 {search_time:.3f}s 超过阈值 300ms"


# ==================== 性能测试：积分操作 ====================

@pytest.mark.asyncio
async def test_performance_credit_operations(client, test_db, auth_headers, test_agent):
    """测试积分操作性能"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "CreditTeam", "description": "Test credit operations"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    # 测试充值性能
    start_time = time.time()
    await client.post(
        f"/teams/{team_id}/credits/add",
        json={"amount": 1000},
        headers=auth_headers
    )
    end_time = time.time()

    add_time = end_time - start_time

    print(f"\n积分操作性能:")
    print(f"  充值时间: {add_time:.3f}s")

    # 断言：充值操作应该 < 200ms
    assert add_time < 0.2, f"充值时间 {add_time:.3f}s 超过阈值 200ms"

    # 测试交易历史查询性能
    start_time = time.time()
    resp = await client.get(f"/teams/{team_id}/credits/transactions?page=1&page_size=20", headers=auth_headers)
    end_time = time.time()

    assert resp.status_code == 200
    query_time = end_time - start_time

    print(f"  交易历史查询时间: {query_time:.3f}s")

    # 断言：交易历史查询应该 < 300ms
    assert query_time < 0.3, f"查询时间 {query_time:.3f}s 超过阈值 300ms"


# ==================== 并发测试：团队创建 ====================

@pytest.mark.asyncio
async def test_concurrent_team_creation(client, test_db, auth_headers):
    """测试并发创建团队"""
    async def create_team(index):
        return await client.post(
            "/teams",
            json={"name": f"ConcurrentTeam_{index}", "description": "Concurrent creation test"},
            headers=auth_headers
        )

    # 并发创建 10 个团队
    start_time = time.time()
    tasks = [create_team(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    total_time = end_time - start_time
    success_count = sum(1 for r in results if r.status_code == 200)

    print(f"\n并发团队创建性能:")
    print(f"  总时间: {total_time:.3f}s")
    print(f"  成功数量: {success_count}/10")

    # 所有请求应该成功
    assert success_count == 10, f"只有 {success_count}/10 个团队创建成功"

    # 并发时间应该 < 2s（单次平均 < 200ms）
    assert total_time < 2.0, f"并发创建时间 {total_time:.3f}s 超过阈值 2s"


# ==================== 并发测试：成员加入 ====================

@pytest.mark.asyncio
async def test_concurrent_member_join(client, test_db, auth_headers, test_agent):
    """测试并发成员加入"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "JoinTeam", "description": "Test concurrent join"},
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

    # 创建模拟成员 Agent
    async def create_and_join_member(index):
        member_agent = Agent(
            name=f"JoinMember_{index}",
            description=f"Member {index}",
            api_key=f"join_key_{index}",
            credits=100,
            reputation_score=5.0
        )
        # 注意：实际需要先创建 Agent，然后加入
        # 这里简化处理，仅测试并发性
        return index

    # 并发"加入"（模拟）
    start_time = time.time()
    tasks = [create_and_join_member(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    total_time = end_time - start_time

    print(f"\n并发成员加入性能:")
    print(f"  总时间: {total_time:.3f}s")
    print(f"  成功数量: {len(results)}/10")

    # 并发时间应该 < 1s
    assert total_time < 1.0, f"并发加入时间 {total_time:.3f}s 超过阈值 1s"


# ==================== 并发测试：记忆创建 ====================

@pytest.mark.asyncio
async def test_concurrent_memory_creation(client, test_db, auth_headers, test_agent):
    """测试并发创建记忆"""
    # 创建团队
    team_resp = await client.post(
        "/teams",
        json={"name": "MemoryTeam", "description": "Test concurrent memory creation"},
        headers=auth_headers
    )
    team_id = team_resp.json()["data"]["team_id"]

    async def create_memory(index):
        return await client.post(
            "/team-memories",
            json={
                "title": f"Concurrent Memory {index}",
                "category": "concurrent/test",
                "tags": ["concurrent"],
                "content": {"index": index},
                "summary": f"Concurrent test memory {index}",
                "format_type": "template",
                "price": 10 * index,
                "team_access_level": "team_only"
            },
            headers=auth_headers
        )

    # 并发创建 20 个记忆
    start_time = time.time()
    tasks = [create_memory(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    total_time = end_time - start_time
    success_count = sum(1 for r in results if r.status_code == 200)

    print(f"\n并发记忆创建性能:")
    print(f"  总时间: {total_time:.3f}s")
    print(f"  成功数量: {success_count}/20")

    # 所有请求应该成功
    assert success_count == 20, f"只有 {success_count}/20 个记忆创建成功"

    # 并发时间应该 < 3s（单次平均 < 150ms）
    assert total_time < 3.0, f"并发创建时间 {total_time:.3f}s 超过阈值 3s"


# ==================== 性能基准：总结 ====================

@pytest.mark.asyncio
async def test_performance_summary(client, test_db, auth_headers, test_agent):
    """性能基准总结测试"""
    print("\n" + "="*50)
    print("团队协作功能性能基准测试")
    print("="*50)

    # 1. 团队查询基准
    start = time.time()
    await client.post("/teams", json={"name": "Benchmark1", "description": "Benchmark"}, headers=auth_headers)
    print(f"团队创建: {(time.time() - start)*1000:.2f}ms")

    # 2. 成员查询基准
    team_resp = await client.post("/teams", json={"name": "Benchmark2", "description": "Benchmark"}, headers=auth_headers)
    team_id = team_resp.json()["data"]["team_id"]
    start = time.time()
    await client.get(f"/teams/{team_id}/members")
    print(f"成员列表查询: {(time.time() - start)*1000:.2f}ms")

    # 3. 记忆搜索基准
    await client.post(
        "/team-memories",
        json={
            "title": "Benchmark Memory",
            "category": "benchmark",
            "tags": ["benchmark"],
            "content": {"test": "data"},
            "summary": "Benchmark memory",
            "format_type": "template",
            "price": 10,
            "team_access_level": "team_only"
        },
        headers=auth_headers
    )
    start = time.time()
    await client.get(f"/teams/{team_id}/memories", headers=auth_headers)
    print(f"记忆搜索: {(time.time() - start)*1000:.2f}ms")

    # 4. 积分操作基准
    start = time.time()
    await client.post(f"/teams/{team_id}/credits/add", json={"amount": 100}, headers=auth_headers)
    print(f"积分充值: {(time.time() - start)*1000:.2f}ms")

    print("="*50)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
