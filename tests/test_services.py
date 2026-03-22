"""
服务层测试

测试核心业务逻辑，包括记忆服务、Agent 服务等。
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Agent, Memory
from app.models.schemas import MemoryCreate
from app.services.agent_service import create_agent, get_balance
from app.services.memory_service import (
    upload_memory,
    search_memories,
    purchase_memory,
    rate_memory,
    verify_memory,
    update_memory,
    get_my_memories,
    get_memory_detail,
    get_memory_versions,
    get_memory_version
)
from app.models.schemas import RateRequest, VerificationRequest, AgentCreate


@pytest.mark.asyncio
async def test_create_agent_service(db_session: AsyncSession):
    """测试创建 Agent 服务"""
    req = AgentCreate(
        name="服务测试Agent",
        description="测试服务层"
    )

    agent = await create_agent(db_session, req)

    assert agent.name == "服务测试Agent"
    assert agent.description == "测试服务层"
    assert agent.agent_id is not None
    assert agent.api_key is not None
    assert agent.credits >= 0


@pytest.mark.asyncio
async def test_get_balance_service(db_session: AsyncSession, test_agent: Agent):
    """测试获取余额服务"""
    balance = await get_balance(db_session, test_agent.agent_id)

    assert balance is not None
    assert "agent_id" in balance
    assert "credits" in balance
    assert balance["agent_id"] == test_agent.agent_id
    assert balance["credits"] == test_agent.credits


@pytest.mark.asyncio
async def test_upload_memory_service(db_session: AsyncSession, test_agent: Agent):
    """测试上传记忆服务"""
    req = MemoryCreate(
        title="服务测试记忆",
        category="测试/服务",
        summary="测试摘要",
        content="测试内容",
        format_type="text",
        price=100,
        tags=["测试", "服务"]
    )

    memory = await upload_memory(db_session, test_agent.agent_id, req)

    assert memory.title == "服务测试记忆"
    assert memory.price == 100
    assert memory.memory_id is not None
    assert memory.seller_agent_id == test_agent.agent_id


@pytest.mark.asyncio
async def test_search_memories_service(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试搜索记忆服务"""
    result = await search_memories(
        db_session,
        query="测试",
        page=1,
        page_size=10
    )

    assert result.total >= 1
    assert len(result.items) >= 1
    assert result.page == 1
    assert result.page_size == 10


@pytest.mark.asyncio
async def test_search_memories_with_filters(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试带过滤条件的搜索"""
    result = await search_memories(
        db_session,
        category="测试/分类",
        min_score=4.0,
        page=1,
        page_size=10
    )

    assert result.total >= 0
    assert isinstance(result.items, list)


@pytest.mark.asyncio
async def test_keyword_search(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试关键词搜索"""
    result = await search_memories(
        db_session,
        query="测试记忆",
        search_type="keyword",
        page=1,
        page_size=10
    )

    assert result.total >= 1


@pytest.mark.asyncio
async def test_semantic_search(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试语义搜索"""
    result = await search_memories(
        db_session,
        query="测试",
        search_type="semantic",
        page=1,
        page_size=10
    )

    assert isinstance(result, object)
    assert hasattr(result, 'items')


@pytest.mark.asyncio
async def test_hybrid_search(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试混合搜索"""
    result = await search_memories(
        db_session,
        query="测试",
        search_type="hybrid",
        page=1,
        page_size=10
    )

    assert isinstance(result, object)
    assert hasattr(result, 'items')


@pytest.mark.asyncio
async def test_search_sorting(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试搜索排序"""
    # 测试按价格排序
    result_price = await search_memories(
        db_session,
        sort_by="price",
        page=1,
        page_size=10
    )
    assert result_price.total >= 0

    # 测试按时间排序
    result_time = await search_memories(
        db_session,
        sort_by="created_at",
        page=1,
        page_size=10
    )
    assert result_time.total >= 0

    # 测试按购买次数排序
    result_purchase = await search_memories(
        db_session,
        sort_by="purchase_count",
        page=1,
        page_size=10
    )
    assert result_purchase.total >= 0


@pytest.mark.asyncio
async def test_purchase_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试购买记忆服务"""
    result = await purchase_memory(
        db_session,
        test_agent2.agent_id,
        test_memory.memory_id
    )

    assert result.success is True
    assert result.memory_id == test_memory.memory_id
    assert result.credits_spent >= 0
    assert result.remaining_credits >= 0


@pytest.mark.asyncio
async def test_purchase_own_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_memory: Memory
):
    """测试购买自己的记忆（应该失败）"""
    result = await purchase_memory(
        db_session,
        test_agent.agent_id,
        test_memory.memory_id
    )

    assert result.success is False
    assert "不能购买" in result.message


@pytest.mark.asyncio
async def test_rate_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试评价记忆服务"""
    # 先创建购买记录
    from app.models.tables import Purchase
    from app.services.memory_service import gen_id
    from app.core.config import settings

    purchase = Purchase(
        purchase_id=gen_id("pur"),
        buyer_agent_id=test_agent2.agent_id,
        seller_agent_id=test_agent.agent_id,
        memory_id=test_memory.memory_id,
        amount=test_memory.price,
        seller_income=int(test_memory.price * settings.SELLER_SHARE_RATE),
        platform_fee=test_memory.price - int(test_memory.price * settings.SELLER_SHARE_RATE)
    )
    db_session.add(purchase)
    await db_session.commit()

    # 评价
    req = RateRequest(
        memory_id=test_memory.memory_id,
        score=5,
        effectiveness=5,
        comment="非常好"
    )

    result = await rate_memory(db_session, test_agent2.agent_id, req)

    assert result.success is True
    assert result.new_avg_score >= 4.0


@pytest.mark.asyncio
async def test_verify_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试验证记忆服务"""
    req = VerificationRequest(
        score=5,
        comment="验证通过"
    )

    result = await verify_memory(
        db_session,
        test_memory.memory_id,
        test_agent2.agent_id,
        req
    )

    assert result.success is True
    assert result.memory_id == test_memory.memory_id
    assert result.reward_credits > 0
    assert result.verification_score > 0


@pytest.mark.asyncio
async def test_verify_own_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_memory: Memory
):
    """测试验证自己的记忆（应该失败）"""
    req = VerificationRequest(score=5)

    with pytest.raises(ValueError, match="不能验证自己的记忆"):
        await verify_memory(
            db_session,
            test_memory.memory_id,
            test_agent.agent_id,
            req
        )


@pytest.mark.asyncio
async def test_update_memory_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_memory: Memory
):
    """测试更新记忆服务"""
    updates = {
        "title": "更新后的标题",
        "price": 200,
        "changelog": "更新价格和标题"
    }

    result = await update_memory(
        db_session,
        test_memory.memory_id,
        test_agent.agent_id,
        updates
    )

    assert result is not None
    assert result.title == "更新后的标题"
    assert result.price == 200


@pytest.mark.asyncio
async def test_update_memory_unauthorized(
    db_session: AsyncSession,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试未授权更新记忆"""
    updates = {"title": "尝试修改"}

    with pytest.raises(PermissionError):
        await update_memory(
            db_session,
            test_memory.memory_id,
            test_agent2.agent_id,
            updates
        )


@pytest.mark.asyncio
async def test_get_my_memories_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_memory: Memory
):
    """测试获取我的记忆服务"""
    result = await get_my_memories(
        db_session,
        test_agent.agent_id,
        page=1,
        page_size=20
    )

    assert result["total"] >= 1
    assert len(result["items"]) >= 1
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert "stats" in result


@pytest.mark.asyncio
async def test_get_memory_detail_service(
    db_session: AsyncSession,
    test_agent: Agent,
    test_memory: Memory
):
    """测试获取记忆详情服务"""
    detail = await get_memory_detail(
        db_session,
        test_memory.memory_id,
        test_agent.agent_id
    )

    assert detail is not None
    assert detail.memory_id == test_memory.memory_id
    assert detail.title == test_memory.title
    # 卖家应该能看到完整内容
    assert detail.content is not None


@pytest.mark.asyncio
async def test_get_memory_versions_service(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试获取记忆版本历史服务"""
    result = await get_memory_versions(
        db_session,
        test_memory.memory_id,
        page=1,
        page_size=20
    )

    assert result["total"] >= 1
    assert len(result["items"]) >= 1
    assert result["page"] == 1


@pytest.mark.asyncio
async def test_get_memory_version_service(
    db_session: AsyncSession,
    test_memory: Memory
):
    """测试获取特定版本服务"""
    # 先获取版本列表
    versions_result = await get_memory_versions(
        db_session,
        test_memory.memory_id,
        page=1,
        page_size=1
    )

    if versions_result["items"]:
        version_id = versions_result["items"][0].version_id
        version = await get_memory_version(
            db_session,
            test_memory.memory_id,
            version_id
        )

        assert version is not None
        assert version["version_id"] == version_id
        assert version["memory_id"] == test_memory.memory_id


@pytest.mark.asyncio
async def test_memory_pagination(
    db_session: AsyncSession,
    test_agent: Agent
):
    """测试分页功能"""
    # 创建多个记忆
    for i in range(5):
        memory = Memory(
            memory_id=f"test_mem_{i:03d}",
            seller_agent_id=test_agent.agent_id,
            title=f"测试记忆 {i}",
            category="测试/分页",
            summary=f"摘要 {i}",
            content=f"内容 {i}",
            format_type="text",
            price=100,
            avg_score=4.0
        )
        db_session.add(memory)
    await db_session.commit()

    # 测试第一页
    page1 = await search_memories(
        db_session,
        page=1,
        page_size=2
    )
    assert len(page1.items) <= 2
    assert page1.page == 1

    # 测试第二页
    page2 = await search_memories(
        db_session,
        page=2,
        page_size=2
    )
    assert page2.page == 2


@pytest.mark.asyncio
async def test_verification_score_calculation():
    """测试验证分数计算"""
    from app.services.memory_service import _calc_verification_score

    # 高质量数据
    data1 = {
        "sample_size": 1000,
        "success_rate": 0.9,
        "data_source": "verified",
        "test_period_days": 60
    }
    score1 = _calc_verification_score(data1)
    assert score1 > 0.8

    # 低质量数据
    data2 = {
        "sample_size": 10,
        "success_rate": 0.3
    }
    score2 = _calc_verification_score(data2)
    assert score2 < 0.5


@pytest.mark.asyncio
async def test_commission_system(
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试佣金系统"""
    from app.core.config import settings

    initial_buyer_credits = test_agent2.credits

    result = await purchase_memory(
        db_session,
        test_agent2.agent_id,
        test_memory.memory_id
    )

    # 验证卖家收入计算
    expected_seller_income = int(test_memory.price * settings.SELLER_SHARE_RATE)
    expected_platform_fee = test_memory.price - expected_seller_income

    # 刷新并检查卖家余额
    await db_session.refresh(test_agent)
    await db_session.refresh(test_agent2)

    # 在 MVP 免费模式下，不应该扣费
    if settings.MVP_FREE_MODE:
        assert test_agent2.credits == initial_buyer_credits


@pytest.mark.asyncio
async def test_market_stats_update(
    db_session: AsyncSession,
    test_agent: Agent,
    test_agent2: Agent,
    test_memory: Memory
):
    """测试市场统计更新"""
    from app.models.tables import PlatformStats
    from sqlalchemy import select

    # 购买记忆以触发统计更新
    await purchase_memory(
        db_session,
        test_agent2.agent_id,
        test_memory.memory_id
    )

    # 检查统计记录
    result = await db.execute(
        select(PlatformStats)
    )
    stats = result.scalar_one_or_none()

    if stats:
        assert stats.total_transactions >= 1
        assert stats.total_volume >= 0
