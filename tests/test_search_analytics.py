"""搜索分析功能测试"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import SearchLog, SearchClick, SearchABTest, Agent, Memory
from app.api.search_analytics import (
    get_search_trends,
    get_search_quality,
    get_search_performance,
    get_zero_results_queries,
    get_user_search_behavior
)
from app.services.ab_test_service import ABTestService


@pytest.mark.asyncio
async def test_search_log_creation(db: AsyncSession, test_agent: Agent):
    """测试搜索日志创建"""
    log = SearchLog(
        agent_id=test_agent.agent_id,
        query="抖音爆款视频",
        search_type="hybrid",
        category="抖音",
        result_count=10,
        top_result_id="mem_test123",
        response_time_ms=150
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.log_id is not None
    assert log.query == "抖音爆款视频"
    assert log.result_count == 10


@pytest.mark.asyncio
async def test_search_click_creation(db: AsyncSession, test_agent: Agent, test_search_log: SearchLog):
    """测试搜索点击创建"""
    click = SearchClick(
        search_log_id=test_search_log.log_id,
        memory_id="mem_test123",
        position=1,
        agent_id=test_agent.agent_id,
        click_type="detail"
    )

    db.add(click)
    await db.commit()
    await db.refresh(click)

    assert click.click_id is not None
    assert click.position == 1


@pytest.mark.asyncio
async def test_search_trends_empty(db: AsyncSession, admin_agent: Agent):
    """测试空数据的搜索趋势"""
    trends = await get_search_trends(days=7, limit=10, db=db, current_agent=admin_agent)

    assert isinstance(trends, list)
    assert len(trends) == 0


@pytest.mark.asyncio
async def test_search_trends_with_data(db: AsyncSession, admin_agent: Agent, test_agent: Agent):
    """测试有数据的搜索趋势"""
    # 创建测试搜索日志
    now = datetime.utcnow()

    logs = [
        SearchLog(
            agent_id=test_agent.agent_id,
            query="抖音爆款",
            search_type="hybrid",
            category="抖音",
            result_count=10,
            response_time_ms=150,
            created_at=now - timedelta(hours=1)
        ),
        SearchLog(
            agent_id=test_agent.agent_id,
            query="抖音爆款",
            search_type="hybrid",
            category="抖音",
            result_count=8,
            response_time_ms=160,
            created_at=now - timedelta(hours=2)
        ),
        SearchLog(
            agent_id=test_agent.agent_id,
            query="小红书种草",
            search_type="hybrid",
            category="小红书",
            result_count=5,
            response_time_ms=120,
            created_at=now - timedelta(hours=3)
        )
    ]

    for log in logs:
        db.add(log)
    await db.commit()

    # 获取搜索趋势
    trends = await get_search_trends(days=1, limit=10, db=db, current_agent=admin_agent)

    assert len(trends) >= 1

    # 检查"抖音爆款"是否在结果中
    trend_queries = [t.query for t in trends]
    assert "抖音爆款" in trend_queries


@pytest.mark.asyncio
async def test_search_quality_metrics(db: AsyncSession, admin_agent: Agent, test_agent: Agent):
    """测试搜索质量指标"""
    # 创建测试数据
    now = datetime.utcnow()

    # 正常搜索
    for i in range(10):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query=f"测试查询{i}",
            search_type="hybrid",
            result_count=10,
            response_time_ms=150,
            created_at=now - timedelta(hours=i)
        )
        db.add(log)

    # 零结果搜索
    for i in range(2):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query="无结果查询",
            search_type="hybrid",
            result_count=0,
            response_time_ms=100,
            created_at=now - timedelta(hours=i + 10)
        )
        db.add(log)

    await db.commit()

    # 获取质量指标
    quality = await get_search_quality(days=1, db=db, current_agent=admin_agent)

    assert quality.total_searches >= 12
    assert quality.avg_result_count > 0
    assert quality.avg_response_time_ms > 0
    assert quality.zero_results_rate > 0


@pytest.mark.asyncio
async def test_search_performance_stats(db: AsyncSession, admin_agent: Agent, test_agent: Agent):
    """测试搜索性能统计"""
    # 创建测试数据
    now = datetime.utcnow()

    # 正常搜索
    for i in range(10):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query=f"性能测试{i}",
            search_type="hybrid",
            result_count=10,
            response_time_ms=100 + i * 10,  # 100-190ms
            created_at=now - timedelta(hours=i)
        )
        db.add(log)

    await db.commit()

    # 获取性能统计
    performance = await get_search_performance(period="hour", db=db, current_agent=admin_agent)

    assert performance.search_count >= 10
    assert performance.avg_response_time_ms > 0
    assert performance.slow_searches_count == 0  # 所有搜索都<1s


@pytest.mark.asyncio
async def test_zero_results_queries(db: AsyncSession, admin_agent: Agent, test_agent: Agent):
    """测试零结果查询"""
    # 创建测试数据
    now = datetime.utcnow()

    zero_result_queries = ["无结果1", "无结果2", "无结果3"]
    for query in zero_result_queries:
        for i in range(3):
            log = SearchLog(
                agent_id=test_agent.agent_id,
                query=query,
                search_type="hybrid",
                result_count=0,
                response_time_ms=100,
                created_at=now - timedelta(hours=i)
            )
            db.add(log)

    await db.commit()

    # 获取零结果查询
    result = await get_zero_results_queries(days=1, limit=10, db=db, current_agent=admin_agent)

    assert result["period_days"] == 1
    assert len(result["queries"]) >= 1

    # 检查"无结果1"是否在结果中
    query_list = [q["query"] for q in result["queries"]]
    assert "无结果1" in query_list


@pytest.mark.asyncio
async def test_user_search_behavior(db: AsyncSession, admin_agent: Agent, test_agent: Agent):
    """测试用户搜索行为"""
    # 创建测试数据
    now = datetime.utcnow()

    for i in range(20):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query=f"用户行为测试{i % 5}",  # 5个不同查询
            search_type="hybrid",
            result_count=10,
            response_time_ms=150,
            created_at=now - timedelta(hours=i)
        )
        db.add(log)

    await db.commit()

    # 获取用户搜索行为
    behaviors = await get_user_search_behavior(days=1, limit=10, db=db, current_agent=admin_agent)

    assert len(behaviors) >= 1

    # 检查test_agent的数据
    user_data = next((b for b in behaviors if b.agent_id == test_agent.agent_id), None)
    assert user_data is not None
    assert user_data.total_searches >= 20
    assert user_data.unique_queries <= 5


@pytest.mark.asyncio
async def test_ab_test_creation(db: AsyncSession, test_agent: Agent):
    """测试A/B测试创建"""
    from app.models.schemas import ABTestCreate

    ab_test_service = ABTestService()

    test_config = ABTestCreate(
        name="算法对比测试",
        description="对比向量搜索和混合搜索",
        test_type="algorithm",
        start_at=datetime.utcnow() + timedelta(hours=1),
        end_at=datetime.utcnow() + timedelta(days=7),
        split_ratio={"A": 0.5, "B": 0.5},
        group_configs={
            "A": {"algorithm": "vector"},
            "B": {"algorithm": "hybrid"}
        },
        metrics=["ctr", "zero_results_rate", "avg_response_time"]
    )

    test = await ab_test_service.create_test(db, test_agent.agent_id, test_config)

    assert test.test_id is not None
    assert test.name == "算法对比测试"
    assert test.status == "draft"
    assert test.split_ratio == {"A": 0.5, "B": 0.5}


@pytest.mark.asyncio
async def test_ab_test_user_grouping(db: AsyncSession, test_agent: Agent):
    """测试A/B测试用户分组"""
    from app.models.schemas import ABTestCreate

    ab_test_service = ABTestService()

    # 创建测试
    test_config = ABTestCreate(
        name="用户分组测试",
        test_type="algorithm",
        start_at=datetime.utcnow() - timedelta(hours=1),
        end_at=datetime.utcnow() + timedelta(days=7),
        split_ratio={"A": 0.5, "B": 0.5},
        group_configs={
            "A": {"algorithm": "vector"},
            "B": {"algorithm": "hybrid"}
        },
        metrics=["ctr"]
    )

    test = await ab_test_service.create_test(db, test_agent.agent_id, test_config)
    test.status = "running"
    await db.commit()

    # 获取用户分组
    group = await ab_test_service.get_user_group(db, test.test_id, test_agent.agent_id)

    assert group in ["A", "B"]

    # 同一用户应该始终在同一组
    group2 = await ab_test_service.get_user_group(db, test.test_id, test_agent.agent_id)
    assert group == group2


@pytest.mark.asyncio
async def test_ab_test_group_config(db: AsyncSession, test_agent: Agent):
    """测试A/B测试分组配置"""
    from app.models.schemas import ABTestCreate

    ab_test_service = ABTestService()

    test_config = ABTestCreate(
        name="配置测试",
        test_type="algorithm",
        start_at=datetime.utcnow() - timedelta(hours=1),
        end_at=datetime.utcnow() + timedelta(days=7),
        split_ratio={"A": 0.5, "B": 0.5},
        group_configs={
            "A": {"algorithm": "vector"},
            "B": {"algorithm": "hybrid"}
        },
        metrics=["ctr"]
    )

    test = await ab_test_service.create_test(db, test_agent.agent_id, test_config)

    # 获取分组配置
    config_a = await ab_test_service.get_group_config(db, test.test_id, "A")
    config_b = await ab_test_service.get_group_config(db, test.test_id, "B")

    assert config_a == {"algorithm": "vector"}
    assert config_b == {"algorithm": "hybrid"}


@pytest.mark.asyncio
async def test_ab_test_collect_results(db: AsyncSession, test_agent: Agent):
    """测试A/B测试结果收集"""
    from app.models.schemas import ABTestCreate

    ab_test_service = ABTestService()

    # 创建测试
    test_config = ABTestCreate(
        name="结果收集测试",
        test_type="algorithm",
        start_at=datetime.utcnow() - timedelta(hours=1),
        end_at=datetime.utcnow() + timedelta(days=7),
        split_ratio={"A": 0.5, "B": 0.5},
        group_configs={
            "A": {"algorithm": "vector"},
            "B": {"algorithm": "hybrid"}
        },
        metrics=["ctr"]
    )

    test = await ab_test_service.create_test(db, test_agent.agent_id, test_config)
    test.status = "running"
    await db.commit()

    # 创建测试搜索日志
    now = datetime.utcnow()

    # A组搜索
    for i in range(10):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query=f"测试{i}",
            search_type="vector",
            result_count=10,
            response_time_ms=150,
            ab_test_id=test.test_id,
            ab_test_group="A",
            created_at=now - timedelta(hours=i)
        )
        db.add(log)

    # B组搜索
    for i in range(10):
        log = SearchLog(
            agent_id=test_agent.agent_id,
            query=f"测试{i}",
            search_type="hybrid",
            result_count=12,
            response_time_ms=160,
            ab_test_id=test.test_id,
            ab_test_group="B",
            created_at=now - timedelta(hours=i + 10)
        )
        db.add(log)

    await db.commit()

    # 收集结果
    group_stats = await ab_test_service.collect_results(db, test.test_id)

    assert "A" in group_stats
    assert "B" in group_stats
    assert group_stats["A"]["searches"] >= 10
    assert group_stats["B"]["searches"] >= 10


@pytest.fixture
async def test_search_log(db: AsyncSession, test_agent: Agent) -> SearchLog:
    """创建测试搜索日志的fixture"""
    log = SearchLog(
        agent_id=test_agent.agent_id,
        query="测试搜索",
        search_type="hybrid",
        result_count=10,
        response_time_ms=150
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
