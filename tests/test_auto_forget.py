"""自动遗忘机制测试"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auto_forget_service import get_auto_forget_service, AutoForgetService
from app.services.forget_scheduler import get_forget_scheduler, ForgetScheduler
from app.models.tables import Memory, ProfileFact, UserProfile, ProfileChange
from app.db.database import get_async_session


@pytest.mark.asyncio
async def test_auto_forget_service_initialization():
    """测试自动遗忘服务初始化"""
    service = get_auto_forget_service()
    assert isinstance(service, AutoForgetService)
    assert service.enabled is not None


@pytest.mark.asyncio
async def test_forget_scheduler_initialization():
    """测试遗忘调度器初始化"""
    scheduler = get_forget_scheduler()
    assert isinstance(scheduler, ForgetScheduler)


@pytest.mark.asyncio
async def test_check_expired_memories(db_session: AsyncSession):
    """测试检查过期记忆"""
    service = get_auto_forget_service()

    # 创建测试记忆
    now = datetime.now()

    # 未过期的记忆
    valid_memory = Memory(
        seller_agent_id="test_agent_1",
        title="Valid Memory",
        category="test",
        tags=["test"],
        summary="This is a valid memory",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now + timedelta(days=30)  # 30天后过期
    )
    db_session.add(valid_memory)

    # 已过期的记忆
    expired_memory = Memory(
        seller_agent_id="test_agent_1",
        title="Expired Memory",
        category="test",
        tags=["test"],
        summary="This memory is expired",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now - timedelta(days=1)  # 1天前过期
    )
    db_session.add(expired_memory)

    await db_session.commit()

    # 检查过期记忆
    expired_memories = await service.check_expired_memories(db_session)

    # 验证结果
    assert len(expired_memories) >= 1
    assert any(m["title"] == "Expired Memory" for m in expired_memories)
    assert not any(m["title"] == "Valid Memory" for m in expired_memories)


@pytest.mark.asyncio
async def test_expire_memories(db_session: AsyncSession):
    """测试过期记忆"""
    service = get_auto_forget_service()

    # 创建测试记忆
    now = datetime.now()
    memory = Memory(
        seller_agent_id="test_agent_2",
        title="Memory to Expire",
        category="test",
        tags=["test"],
        summary="This memory will be expired",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now - timedelta(days=1)
    )
    db_session.add(memory)
    await db_session.commit()

    # 过期记忆
    expired_count = await service.expire_memories(db_session, [memory.memory_id])

    # 验证结果
    assert expired_count == 1

    # 检查记忆状态
    await db_session.refresh(memory)
    assert memory.is_active is False


@pytest.mark.asyncio
async def test_check_expired_facts(db_session: AsyncSession):
    """测试检查过期事实"""
    service = get_auto_forget_service()

    # 创建用户画像
    profile = UserProfile(agent_id="test_agent_3")
    db_session.add(profile)
    await db_session.flush()

    # 未过期的事实
    valid_fact = ProfileFact(
        profile_id=profile.profile_id,
        agent_id="test_agent_3",
        fact_type="preference",
        fact_key="language",
        fact_value="zh",
        confidence=0.9,
        source="manual",
        expires_at=datetime.now() + timedelta(days=30),
        is_valid=True
    )
    db_session.add(valid_fact)

    # 已过期的事实
    expired_fact = ProfileFact(
        profile_id=profile.profile_id,
        agent_id="test_agent_3",
        fact_type="preference",
        fact_key="editor",
        fact_value="vscode",
        confidence=0.9,
        source="manual",
        expires_at=datetime.now() - timedelta(days=1),
        is_valid=True
    )
    db_session.add(expired_fact)

    await db_session.commit()

    # 检查过期事实
    expired_facts = await service.check_expired_facts(db_session)

    # 验证结果
    assert len(expired_facts) >= 1
    assert any(f["fact_key"] == "editor" for f in expired_facts)
    assert not any(f["fact_key"] == "language" for f in expired_facts)


@pytest.mark.asyncio
async def test_expire_facts(db_session: AsyncSession):
    """测试过期事实"""
    service = get_auto_forget_service()

    # 创建用户画像
    profile = UserProfile(agent_id="test_agent_4")
    db_session.add(profile)
    await db_session.flush()

    # 创建事实
    fact = ProfileFact(
        profile_id=profile.profile_id,
        agent_id="test_agent_4",
        fact_type="preference",
        fact_key="theme",
        fact_value="dark",
        confidence=0.9,
        source="manual",
        expires_at=datetime.now() - timedelta(days=1),
        is_valid=True
    )
    db_session.add(fact)
    await db_session.commit()

    # 过期事实
    expired_count = await service.expire_facts(db_session, [fact.fact_id])

    # 验证结果
    assert expired_count == 1

    # 检查事实状态
    await db_session.refresh(fact)
    assert fact.is_valid is False


@pytest.mark.asyncio
async def test_override_fact(db_session: AsyncSession):
    """测试覆盖事实"""
    service = get_auto_forget_service()

    # 创建用户画像
    profile = UserProfile(agent_id="test_agent_5")
    db_session.add(profile)
    await db_session.flush()

    # 创建旧事实
    old_fact = ProfileFact(
        profile_id=profile.profile_id,
        agent_id="test_agent_5",
        fact_type="preference",
        fact_key="editor",
        fact_value="vim",
        confidence=0.8,
        source="manual",
        expires_at=datetime.now() + timedelta(days=30),
        is_valid=True
    )
    db_session.add(old_fact)
    await db_session.commit()

    # 覆盖事实
    new_fact, returned_old_fact = await service.override_fact(
        db_session,
        "test_agent_5",
        "preference",
        "editor",
        "vscode",
        confidence=0.9
    )

    # 验证结果
    assert new_fact is not None
    assert new_fact.fact_value == "vscode"
    assert new_fact.confidence == 0.9

    # 检查旧事实是否失效
    await db_session.refresh(old_fact)
    assert old_fact.is_valid is False

    # 检查是否有变更记录
    change_stmt = ProfileChange.__table__.select().where(
        ProfileChange.profile_id == profile.profile_id
    )
    change_result = await db_session.execute(change_stmt)
    changes = change_result.all()

    assert len(changes) >= 1
    assert changes[0].change_type == "expired"
    assert changes[0].field_name == "editor"


@pytest.mark.asyncio
async def test_set_memory_ttl(db_session: AsyncSession):
    """测试设置记忆TTL"""
    service = get_auto_forget_service()

    # 创建记忆
    memory = Memory(
        seller_agent_id="test_agent_6",
        title="Memory with TTL",
        category="test",
        tags=["test"],
        summary="This memory has TTL",
        content={"text": "content"},
        price=100,
        is_active=True
    )
    db_session.add(memory)
    await db_session.commit()

    # 设置TTL
    ttl_days = 30
    updated_memory = await service.set_memory_ttl(db_session, memory.memory_id, ttl_days)

    # 验证结果
    assert updated_memory is not None
    assert updated_memory.ttl_days == ttl_days
    assert updated_memory.expiry_time is not None

    # 检查过期时间是否正确
    now = datetime.now()
    expected_expiry = now + timedelta(days=ttl_days)
    time_diff = abs((updated_memory.expiry_time - expected_expiry).total_seconds())
    assert time_diff < 60  # 允许1分钟的误差


@pytest.mark.asyncio
async def test_auto_expire_memories(db_session: AsyncSession):
    """测试自动过期记忆"""
    service = get_auto_forget_service()

    # 创建测试数据
    now = datetime.now()

    # 过期记忆
    expired_memory = Memory(
        seller_agent_id="test_agent_7",
        title="Auto Expired Memory",
        category="test",
        tags=["test"],
        summary="This memory will be auto expired",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now - timedelta(days=1)
    )
    db_session.add(expired_memory)

    # 有效记忆
    valid_memory = Memory(
        seller_agent_id="test_agent_7",
        title="Valid Memory for Auto Test",
        category="test",
        tags=["test"],
        summary="This memory is valid",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now + timedelta(days=30)
    )
    db_session.add(valid_memory)

    await db_session.commit()

    # 执行自动过期
    stats = await service.auto_expire_memories(db_session)

    # 验证结果
    assert stats["checked"] >= 2
    assert stats["expired_memories"] >= 1


@pytest.mark.asyncio
async def test_get_stats(db_session: AsyncSession):
    """测试获取统计信息"""
    service = get_auto_forget_service()

    # 获取统计
    stats = await service.get_stats(db_session)

    # 验证统计字段
    assert "expired_memories" in stats
    assert "expired_facts" in stats
    assert "near_expiry_memories" in stats
    assert "near_expiry_facts" in stats
    assert "enabled" in stats
    assert "default_ttl_days" in stats

    # 验证数据类型
    assert isinstance(stats["expired_memories"], int)
    assert isinstance(stats["expired_facts"], int)
    assert isinstance(stats["enabled"], bool)


@pytest.mark.asyncio
async def test_forget_scheduler_manual_trigger(db_session: AsyncSession):
    """测试遗忘调度器手动触发"""
    scheduler = get_forget_scheduler()

    # 手动触发
    stats = await scheduler.manual_trigger()

    # 验证结果
    assert "checked" in stats
    assert "expired_memories" in stats
    assert "expired_facts" in stats
    assert "errors" in stats


@pytest.mark.asyncio
async def test_ttl_config():
    """测试TTL配置"""
    service = get_auto_forget_service()

    # 验证TTL配置
    assert "personal" in service.ttl_config
    assert "preference" in service.ttl_config
    assert "habit" in service.ttl_config
    assert "skill" in service.ttl_config
    assert "interest" in service.ttl_config

    # 验证默认值
    assert service.ttl_config["personal"] >= 1
    assert service.ttl_config["preference"] >= 1


@pytest.mark.asyncio
async def test_filter_expired_memories():
    """测试过滤过期记忆（搜索集成）"""
    from app.search.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine()

    # 创建测试数据
    now = datetime.now()

    class MockRow:
        def __init__(self, memory):
            self.Memory = memory

    # 过期记忆
    expired_memory = Memory(
        seller_agent_id="test_agent_8",
        title="Expired Memory for Search",
        category="test",
        tags=["test"],
        summary="This memory is expired",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now - timedelta(days=1)
    )

    # 有效记忆
    valid_memory = Memory(
        seller_agent_id="test_agent_8",
        title="Valid Memory for Search",
        category="test",
        tags=["test"],
        summary="This memory is valid",
        content={"text": "content"},
        price=100,
        is_active=True,
        expiry_time=now + timedelta(days=30)
    )

    # 过滤
    filtered = engine._filter_expired_memories([
        MockRow(expired_memory),
        MockRow(valid_memory)
    ])

    # 验证结果
    assert len(filtered) == 1
    assert filtered[0].Memory.title == "Valid Memory for Search"


# 测试夹具
@pytest.fixture
async def db_session():
    """创建数据库会话夹具"""
    async for session in get_async_session():
        yield session
        # 清理测试数据
        # 注意：实际使用时应该使用事务回滚
