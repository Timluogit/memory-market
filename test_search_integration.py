"""集成测试：验证语义搜索与数据库的集成"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.tables import Base, Memory, Agent
from app.services.memory_service import search_memories
from app.core.config import settings


async def setup_test_db():
    """设置测试数据库"""
    # 使用内存数据库
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_session


async def seed_test_data(async_session):
    """插入测试数据"""
    async with async_session() as db:
        # 创建测试 Agent
        agent = Agent(
            agent_id="agent_test_001",
            name="Test Agent",
            description="测试用 Agent",
            api_key="test_key_123",
            credits=1000
        )
        db.add(agent)

        # 创建测试记忆
        memories = [
            Memory(
                memory_id="mem_001",
                seller_agent_id="agent_test_001",
                title="Python FastAPI 开发指南",
                category="编程/Python",
                tags=["python", "fastapi", "web"],
                summary="介绍如何使用 FastAPI 框架快速构建 REST API",
                content={"sections": ["简介", "路由", "依赖注入"]},
                format_type="template",
                price=0
            ),
            Memory(
                memory_id="mem_002",
                seller_agent_id="agent_test_001",
                title="机器学习算法详解",
                category="AI/机器学习",
                tags=["ml", "算法", "python"],
                summary="深入讲解常用机器学习算法的原理和实现",
                content={"sections": ["监督学习", "无监督学习"]},
                format_type="tutorial",
                price=0
            ),
            Memory(
                memory_id="mem_003",
                seller_agent_id="agent_test_001",
                title="SQL 查询优化技巧",
                category="数据库/SQL",
                tags=["sql", "数据库", "优化"],
                summary="分享 SQL 查询性能优化的实用技巧",
                content={"sections": ["索引", "执行计划"]},
                format_type="strategy",
                price=0
            ),
            Memory(
                memory_id="mem_004",
                seller_agent_id="agent_test_001",
                title="Web API 安全防护",
                category="安全/Web",
                tags=["security", "api", "web"],
                summary="讨论 Web API 的常见安全威胁和防护措施",
                content={"sections": ["认证", "授权", "加密"]},
                format_type="warning",
                price=0
            ),
            Memory(
                memory_id="mem_005",
                seller_agent_id="agent_test_001",
                title="Python 异步编程实战",
                category="编程/Python",
                tags=["python", "async", "并发"],
                summary="Python async/await 异步编程实战指南",
                content={"sections": ["协程", "事件循环"]},
                format_type="tutorial",
                price=0
            )
        ]

        for mem in memories:
            db.add(mem)

        await db.commit()


async def test_search_types(async_session):
    """测试不同搜索类型"""
    async with async_session() as db:
        print("\n=== 测试搜索类型 ===\n")

        test_queries = [
            ("API开发", "语义相关查询"),
            ("Python编程", "关键词匹配"),
            ("web安全", "部分匹配"),
        ]

        for query, desc in test_queries:
            print(f"\n查询: '{query}' ({desc})")
            print("-" * 60)

            # 测试关键词搜索
            print("\n1. 关键词搜索 (keyword):")
            result = await search_memories(
                db, query=query, page=1, page_size=5,
                sort_by="relevance", search_type="keyword"
            )
            for item in result.items:
                print(f"   - {item.title}")

            # 测试语义搜索
            print("\n2. 语义搜索 (semantic):")
            result = await search_memories(
                db, query=query, page=1, page_size=5,
                sort_by="relevance", search_type="semantic"
            )
            for item in result.items:
                print(f"   - {item.title}")

            # 测试混合搜索（默认）
            print("\n3. 混合搜索 (hybrid):")
            result = await search_memories(
                db, query=query, page=1, page_size=5,
                sort_by="relevance", search_type="hybrid"
            )
            for item in result.items:
                print(f"   - {item.title}")


async def test_search_performance(async_session):
    """测试搜索性能"""
    async with async_session() as db:
        print("\n\n=== 性能测试 ===\n")

        import time

        test_cases = [
            ("API开发", "keyword"),
            ("API开发", "semantic"),
            ("API开发", "hybrid"),
        ]

        for query, search_type in test_cases:
            times = []
            iterations = 10

            for _ in range(iterations):
                start = time.time()
                await search_memories(
                    db, query=query, page=1, page_size=10,
                    search_type=search_type
                )
                elapsed = time.time() - start
                times.append(elapsed * 1000)  # 转为毫秒

            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)

            print(f"{search_type:12} - 平均: {avg_time:6.2f}ms, 最小: {min_time:6.2f}ms, 最大: {max_time:6.2f}ms")

            if avg_time > 200:
                print(f"  ⚠️  警告: 超过 200ms 目标")
            else:
                print(f"  ✓  性能良好")


async def test_search_filters(async_session):
    """测试搜索筛选功能"""
    async with async_session() as db:
        print("\n\n=== 测试筛选功能 ===\n")

        # 测试分类筛选
        print("分类筛选: '编程/Python'")
        result = await search_memories(
            db, category="编程/Python", page=1, page_size=10,
            search_type="hybrid"
        )
        print(f"找到 {result.total} 条结果:")
        for item in result.items:
            print(f"  - {item.title} ({item.category})")

        # 测试格式筛选
        print("\n格式筛选: 'tutorial'")
        result = await search_memories(
            db, format_type="tutorial", page=1, page_size=10,
            search_type="hybrid"
        )
        print(f"找到 {result.total} 条结果:")
        for item in result.items:
            print(f"  - {item.title} ({item.format_type})")


async def main():
    """主测试函数"""
    print("=" * 60)
    print("语义搜索集成测试")
    print("=" * 60)

    # 设置测试数据库
    async_session = await setup_test_db()

    # 插入测试数据
    await seed_test_data(async_session)
    print("✓ 测试数据已准备")

    # 运行测试
    await test_search_types(async_session)
    await test_search_performance(async_session)
    await test_search_filters(async_session)

    print("\n" + "=" * 60)
    print("所有测试完成 ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
