"""
Pytest 配置和共享 fixtures

这个文件包含了所有测试共享的 pytest fixtures 和配置。
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.models.tables import Base, Agent, Memory
from app.core.config import settings


# 测试数据库 URL（使用内存 SQLite）
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    async_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_agent(db_session: AsyncSession) -> Agent:
    """创建测试 Agent"""
    agent = Agent(
        agent_id="test_agent_001",
        api_key="test_api_key_123456789012",
        name="测试Agent",
        description="用于测试的Agent",
        credits=1000,
        reputation_score=5.0
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest.fixture
async def test_agent2(db_session: AsyncSession) -> Agent:
    """创建第二个测试 Agent"""
    agent = Agent(
        agent_id="test_agent_002",
        api_key="test_api_key_987654321098",
        name="测试Agent2",
        description="第二个测试Agent",
        credits=500,
        reputation_score=4.5
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest.fixture
async def test_memory(db_session: AsyncSession, test_agent: Agent) -> Memory:
    """创建测试记忆"""
    memory = Memory(
        memory_id="test_mem_001",
        seller_agent_id=test_agent.agent_id,
        title="测试记忆",
        category="测试/分类",
        tags=["测试", "示例"],
        summary="这是一个测试记忆的摘要",
        content="这是测试记忆的完整内容",
        format_type="text",
        price=100,
        avg_score=4.5,
        verification_score=0.8,
        purchase_count=5,
        favorite_count=2
    )
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)
    return memory


@pytest.fixture
def auth_headers(test_agent: Agent) -> dict:
    """创建认证头"""
    return {"X-API-Key": test_agent.api_key}


# pytest 配置
def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
