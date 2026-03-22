"""
API 端点测试

测试所有 API 端点的功能、权限、参数验证等。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Agent, Memory, Purchase


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient):
    """测试注册 Agent"""
    response = await client.post(
        "/api/v1/agents",
        json={
            "name": "新Agent",
            "description": "这是一个新Agent"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "新Agent"
    assert data["description"] == "这是一个新Agent"
    assert "agent_id" in data
    assert "api_key" in data
    assert data["credits"] >= 0


@pytest.mark.asyncio
async def test_get_my_info(client: AsyncClient, test_agent: Agent):
    """测试获取当前 Agent 信息"""
    response = await client.get(
        "/api/v1/agents/me",
        headers={"X-API-Key": test_agent.api_key}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent_id"] == test_agent.agent_id
    assert data["name"] == test_agent.name


@pytest.mark.asyncio
async def test_get_my_info_unauthorized(client: AsyncClient):
    """测试未授权访问 Agent 信息"""
    response = await client.get("/api/v1/agents/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_memory(client: AsyncClient, test_agent: Agent):
    """测试上传记忆"""
    response = await client.post(
        "/api/v1/memories",
        headers={"X-API-Key": test_agent.api_key},
        json={
            "title": "测试记忆标题",
            "category": "测试/分类",
            "summary": "测试摘要",
            "content": "测试内容",
            "format_type": "text",
            "price": 100,
            "tags": ["测试", "标签"]
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "测试记忆标题"
    assert data["price"] == 100
    assert "memory_id" in data


@pytest.mark.asyncio
async def test_upload_memory_unauthorized(client: AsyncClient):
    """测试未授权上传记忆"""
    response = await client.post(
        "/api/v1/memories",
        json={
            "title": "测试记忆",
            "category": "测试",
            "summary": "测试",
            "content": "测试",
            "format_type": "text",
            "price": 100
        }
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_memories(client: AsyncClient, test_memory: Memory):
    """测试搜索记忆"""
    response = await client.get("/api/v1/memories")

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_search_memories_with_filters(client: AsyncClient):
    """测试带过滤条件的搜索"""
    response = await client.get(
        "/api/v1/memories",
        params={
            "category": "测试/分类",
            "min_score": 4.0,
            "page": 1,
            "page_size": 10
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_get_memory_detail(client: AsyncClient, test_memory: Memory):
    """测试获取记忆详情"""
    response = await client.get(f"/api/v1/memories/{test_memory.memory_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["memory_id"] == test_memory.memory_id
    assert data["title"] == test_memory.title
    # 未购买时不应返回完整内容
    assert "content" not in data or data.get("content") is None


@pytest.mark.asyncio
async def test_get_memory_detail_not_found(client: AsyncClient):
    """测试获取不存在的记忆"""
    response = await client.get("/api/v1/memories/nonexistent_id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_purchase_memory(
    client: AsyncClient,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试购买记忆"""
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/purchase",
        headers={"X-API-Key": test_agent2.api_key}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert data["memory_id"] == test_memory.memory_id
    assert "credits_spent" in data


@pytest.mark.asyncio
async def test_purchase_own_memory(
    client: AsyncClient,
    test_agent: Agent,
    test_memory: Memory
):
    """测试购买自己的记忆（应该失败）"""
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/purchase",
        headers={"X-API-Key": test_agent.api_key}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_purchase_memory_unauthorized(client: AsyncClient, test_memory: Memory):
    """测试未授权购买记忆"""
    response = await client.post(f"/api/v1/memories/{test_memory.memory_id}/purchase")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rate_memory(
    client: AsyncClient,
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试评价记忆"""
    # 先创建购买记录
    purchase = Purchase(
        purchase_id="test_purchase_001",
        buyer_agent_id=test_agent2.agent_id,
        seller_agent_id=test_agent.agent_id,
        memory_id=test_memory.memory_id,
        amount=100,
        seller_income=80,
        platform_fee=20
    )
    db_session.add(purchase)
    await db_session.commit()

    # 评价记忆
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/rate",
        headers={"X-API-Key": test_agent2.api_key},
        json={
            "score": 5,
            "effectiveness": 5,
            "comment": "非常有用的记忆！"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True


@pytest.mark.asyncio
async def test_rate_memory_without_purchase(
    client: AsyncClient,
    test_agent: Agent,
    test_memory: Memory
):
    """测试未购买时评价记忆（应该失败）"""
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/rate",
        headers={"X-API-Key": test_agent.api_key},
        json={
            "score": 5,
            "effectiveness": 5
        }
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_memory(
    client: AsyncClient,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试验证记忆"""
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/verify",
        headers={"X-API-Key": test_agent2.api_key},
        json={
            "score": 5,
            "comment": "验证通过"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert data["memory_id"] == test_memory.memory_id
    assert data["reward_credits"] > 0


@pytest.mark.asyncio
async def test_verify_own_memory(
    client: AsyncClient,
    test_agent: Agent,
    test_memory: Memory
):
    """测试验证自己的记忆（应该失败）"""
    response = await client.post(
        f"/api/v1/memories/{test_memory.memory_id}/verify",
        headers={"X-API-Key": test_agent.api_key},
        json={"score": 5}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_memory(
    client: AsyncClient,
    test_agent: Agent,
    test_memory: Memory
):
    """测试更新记忆"""
    response = await client.put(
        f"/api/v1/memories/{test_memory.memory_id}",
        headers={"X-API-Key": test_agent.api_key},
        json={
            "title": "更新后的标题",
            "price": 150
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "更新后的标题"
    assert data["price"] == 150


@pytest.mark.asyncio
async def test_update_memory_unauthorized(
    client: AsyncClient,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试未授权更新记忆"""
    response = await client.put(
        f"/api/v1/memories/{test_memory.memory_id}",
        headers={"X-API-Key": test_agent2.api_key},
        json={"title": "尝试修改"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_my_memories(
    client: AsyncClient,
    test_agent: Agent,
    test_memory: Memory
):
    """测试获取自己上传的记忆列表"""
    response = await client.get(
        "/api/v1/agents/me/memories",
        headers={"X-API-Key": test_agent.api_key}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_credit_history(
    client: AsyncClient,
    test_agent: Agent
):
    """测试获取积分流水"""
    response = await client.get(
        "/api/v1/agents/me/credits/history",
        headers={"X-API-Key": test_agent.api_key}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_market_trends(client: AsyncClient):
    """测试获取市场趋势"""
    response = await client.get("/api/v1/market/trends")

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_capture_experience(
    client: AsyncClient,
    test_agent: Agent
):
    """测试经验捕获"""
    response = await client.post(
        "/api/v1/capture",
        headers={"X-API-Key": test_agent.api_key},
        json={
            "task_description": "测试任务",
            "work_log": "执行了测试工作",
            "outcome": "success",
            "category": "测试",
            "tags": ["测试"]
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True


@pytest.mark.asyncio
async def test_batch_capture_experience(
    client: AsyncClient,
    test_agent: Agent
):
    """测试批量经验捕获"""
    response = await client.post(
        "/api/v1/capture/batch",
        headers={"X-API-Key": test_agent.api_key},
        json={
            "items": [
                {
                    "task_description": "任务1",
                    "work_log": "日志1",
                    "outcome": "success"
                },
                {
                    "task_description": "任务2",
                    "work_log": "日志2",
                    "outcome": "partial"
                }
            ]
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert data["processed"] == 2


@pytest.mark.asyncio
async def test_invalid_search_type(client: AsyncClient):
    """测试无效的搜索类型"""
    response = await client.get(
        "/api/v1/memories",
        params={"search_type": "invalid_type"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_semantic_search(client: AsyncClient, test_memory: Memory):
    """测试语义搜索"""
    response = await client.get(
        "/api/v1/memories",
        params={
            "query": "测试",
            "search_type": "semantic"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data


@pytest.mark.asyncio
async def test_hybrid_search(client: AsyncClient, test_memory: Memory):
    """测试混合搜索"""
    response = await client.get(
        "/api/v1/memories",
        params={
            "query": "测试",
            "search_type": "hybrid"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data


@pytest.mark.asyncio
async def test_get_memory_versions(client: AsyncClient, test_memory: Memory):
    """测试获取记忆版本历史"""
    response = await client.get(
        f"/api/v1/memories/{test_memory.memory_id}/versions"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    # 应该至少有初始版本
    assert data["total"] >= 1
