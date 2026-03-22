"""测试搜索排序功能"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.services.memory_service import search_memories
from app.models.tables import Base
from app.core.config import settings

async def test_sorting():
    """测试不同的排序方式"""
    # 创建数据库连接
    engine = create_async_engine(
        settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://"),
        echo=False
    )
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as db:
        print("=" * 60)
        print("测试1: 综合评分排序 (relevance) - 默认")
        print("=" * 60)
        result = await search_memories(
            db, query="", page=1, page_size=5, sort_by="relevance"
        )
        print(f"总数: {result.total}")
        for i, item in enumerate(result.items, 1):
            print(f"\n{i}. {item.title}")
            print(f"   评分: {item.avg_score:.1f}/5.0 | 购买: {item.purchase_count}次 | 收藏: {item.favorite_count}次")
            print(f"   验证: {item.verification_score or 'N/A'} | 价格: {item.price}分")

        print("\n" + "=" * 60)
        print("测试2: 按创建时间排序 (created_at)")
        print("=" * 60)
        result = await search_memories(
            db, query="", page=1, page_size=5, sort_by="created_at"
        )
        for i, item in enumerate(result.items, 1):
            print(f"{i}. {item.title} - 创建于 {item.created_at}")

        print("\n" + "=" * 60)
        print("测试3: 按购买次数排序 (purchase_count)")
        print("=" * 60)
        result = await search_memories(
            db, query="", page=1, page_size=5, sort_by="purchase_count"
        )
        for i, item in enumerate(result.items, 1):
            print(f"{i}. {item.title} - {item.purchase_count}次购买")

        print("\n" + "=" * 60)
        print("测试4: 按价格排序 (price)")
        print("=" * 60)
        result = await search_memories(
            db, query="", page=1, page_size=5, sort_by="price"
        )
        for i, item in enumerate(result.items, 1):
            print(f"{i}. {item.title} - {item.price}分")

        print("\n" + "=" * 60)
        print("测试5: 搜索关键词 + 综合评分排序")
        print("=" * 60)
        result = await search_memories(
            db, query="agent", page=1, page_size=5, sort_by="relevance"
        )
        print(f"搜索 'agent' 结果: {result.total}条")
        for i, item in enumerate(result.items, 1):
            print(f"{i}. {item.title} (评分: {item.avg_score:.1f})")

    await engine.dispose()

if __name__ == "__main__":
    print("开始测试搜索排序功能...")
    asyncio.run(test_sorting())
    print("\n测试完成!")
