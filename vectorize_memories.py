"""向量化和索引现有记忆

将数据库中的现有记忆批量向量化并索引到 Qdrant
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import async_session
from app.models.tables import Memory
from app.search.qdrant_engine import get_qdrant_engine
from sqlalchemy import select, func


async def vectorize_all_memories(batch_size=100):
    """向量化和索引所有记忆

    Args:
        batch_size: 批量处理大小
    """
    print("=" * 60)
    print("Vectorize Existing Memories")
    print("=" * 60)

    # 获取 Qdrant 引擎
    engine = get_qdrant_engine()

    # 检查 Qdrant 服务
    print("\n[1/6] Checking Qdrant service...")
    if not engine.health_check():
        print("✗ Qdrant service is not available!")
        print("  Please start Qdrant:")
        print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
        print("  Or: qdrant up")
        return False

    print("✓ Qdrant service is available")

    # 创建 Collection
    print("\n[2/6] Creating Qdrant collection...")
    engine.create_collection(recreate=True)
    print("✓ Collection created")

    # 获取记忆总数
    print("\n[3/6] Counting memories...")
    async with async_session() as db:
        count_stmt = select(func.count()).select_from(Memory).where(Memory.is_active == True)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

    print(f"✓ Found {total} active memories")

    if total == 0:
        print("\nNo memories to vectorize. Exiting.")
        return True

    # 批量加载记忆
    print(f"\n[4/6] Loading memories (batch_size={batch_size})...")

    all_memories = []
    offset = 0

    async with async_session() as db:
        while offset < total:
            stmt = (
                select(Memory)
                .where(Memory.is_active == True)
                .offset(offset)
                .limit(batch_size)
                .order_by(Memory.created_at)
            )
            result = await db.execute(stmt)
            batch = result.scalars().all()

            for memory in batch:
                all_memories.append({
                    "id": memory.memory_id,
                    "title": memory.title,
                    "summary": memory.summary,
                    "category": memory.category,
                    "tags": memory.tags or [],
                    "price": memory.price,
                    "purchase_count": memory.purchase_count,
                    "avg_score": memory.avg_score or 0,
                    "created_at": memory.created_at.isoformat() if memory.created_at else "",
                })

            print(f"  Loaded {len(all_memories)}/{total} memories...")
            offset += batch_size

    print(f"✓ Loaded {len(all_memories)} memories")

    # 向量化并索引
    print(f"\n[5/6] Vectorizing and indexing memories...")
    start_time = datetime.now()

    # 索引记忆
    indexed_count = engine.index_memories(all_memories, batch_size=batch_size)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"✓ Indexed {indexed_count}/{len(all_memories)} memories")
    print(f"  Time: {elapsed:.2f} seconds")
    print(f"  Speed: {indexed_count / elapsed:.2f} memories/second")

    # 验证索引
    print(f"\n[6/6] Verifying index...")
    info = engine.get_collection_info()
    if info:
        print(f"✓ Collection info:")
        print(f"  Points count: {info['points_count']}")
        print(f"  Segments count: {info['segments_count']}")
        print(f"  Status: {info['status']}")
    else:
        print("✗ Failed to get collection info")
        return False

    # 测试搜索
    print(f"\n[7/6] Testing vector search...")
    test_queries = [
        "抖音爆款",
        "小红书文案",
        "直播带货",
        "视频制作",
    ]

    for query in test_queries:
        results = engine.search(query, top_k=3)
        print(f"\n  查询: '{query}' - 找到 {len(results)} 个结果")
        for idx, (memory_id, score, payload) in enumerate(results[:2], 1):
            print(f"    {idx}. [{score:.3f}] {payload['title']}")

    print("\n" + "=" * 60)
    print("Vectorization Complete!")
    print("=" * 60)
    print(f"✓ Successfully indexed {indexed_count} memories")
    print(f"✓ Vector search is now ready")
    print(f"\nNext steps:")
    print(f"  1. Test the search API: python test_api_search.py")
    print(f"  2. Update the API to use hybrid search")

    return True


async def incremental_vectorize(batch_size=100):
    """增量向量化（仅向量化新增的记忆）

    Args:
        batch_size: 批量处理大小
    """
    print("=" * 60)
    print("Incremental Vectorization")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 获取 Collection 信息
    info = engine.get_collection_info()
    if not info:
        print("✗ Qdrant collection does not exist")
        return False

    indexed_count = info.get("points_count", 0)
    print(f"Currently indexed: {indexed_count} memories")

    # 获取数据库中的记忆总数
    async with async_session() as db:
        count_stmt = select(func.count()).select_from(Memory).where(Memory.is_active == True)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

    print(f"Database memories: {total}")

    if total <= indexed_count:
        print("\n✓ All memories are already indexed")
        return True

    # 加载新增的记忆
    print(f"\nLoading {total - indexed_count} new memories...")

    async with async_session() as db:
        # 简化实现：重新索引所有记忆
        # 生产环境可以优化为只索引新增的记忆
        stmt = (
            select(Memory)
            .where(Memory.is_active == True)
            .order_by(Memory.created_at)
        )
        result = await db.execute(stmt)
        all_memories = result.scalars().all()

        memories_data = []
        for memory in all_memories:
            memories_data.append({
                "id": memory.memory_id,
                "title": memory.title,
                "summary": memory.summary,
                "category": memory.category,
                "tags": memory.tags or [],
                "price": memory.price,
                "purchase_count": memory.purchase_count,
                "avg_score": memory.avg_score or 0,
                "created_at": memory.created_at.isoformat() if memory.created_at else "",
            })

    # 重新索引
    print(f"\nRe-indexing {len(memories_data)} memories...")
    indexed = engine.index_memories(memories_data, batch_size=batch_size)
    print(f"✓ Indexed {indexed} memories")

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vectorize memories")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Incremental vectorization (only new memories)"
    )

    args = parser.parse_args()

    if args.incremental:
        success = asyncio.run(incremental_vectorize(batch_size=args.batch_size))
    else:
        success = asyncio.run(vectorize_all_memories(batch_size=args.batch_size))

    sys.exit(0 if success else 1)
