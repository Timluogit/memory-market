"""Qdrant 向量搜索测试

测试 Qdrant 集成和向量搜索功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.search.qdrant_engine import get_qdrant_engine
from app.search.hybrid_search import get_hybrid_engine


def test_qdrant_connection():
    """测试 Qdrant 连接"""
    print("=" * 60)
    print("Test 1: Qdrant Connection")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 健康检查
    is_healthy = engine.health_check()
    print(f"✓ Qdrant Health: {is_healthy}")

    if not is_healthy:
        print("✗ Qdrant service is not available. Please start Qdrant:")
        print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
        print("  Or: qdrant up")
        return False

    return True


def test_create_collection():
    """测试创建 Collection"""
    print("\n" + "=" * 60)
    print("Test 2: Create Collection")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 创建 Collection
    success = engine.create_collection(recreate=True)
    print(f"✓ Collection created/recreated: {success}")

    # 获取 Collection 信息
    info = engine.get_collection_info()
    print(f"✓ Collection info: {info}")

    return success


def test_vector_indexing():
    """测试向量索引"""
    print("\n" + "=" * 60)
    print("Test 3: Vector Indexing")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 准备测试数据
    test_memories = [
        {
            "id": "test_001",
            "title": "抖音爆款视频制作技巧",
            "summary": "详细讲解如何制作爆款抖音视频，包括选题、拍摄、剪辑、配乐等关键环节",
            "category": "抖音/爆款",
            "tags": ["爆款", "视频制作", "剪辑"],
            "price": 50,
            "purchase_count": 120,
            "avg_score": 4.5,
            "created_at": "2024-01-15"
        },
        {
            "id": "test_002",
            "title": "小红书种草文案写作公式",
            "summary": "分享高效的小红书种草文案写作技巧，包含标题党、痛点挖掘、情感共鸣等方法",
            "category": "小红书/文案",
            "tags": ["种草", "文案", "营销"],
            "price": 30,
            "purchase_count": 80,
            "avg_score": 4.2,
            "created_at": "2024-01-16"
        },
        {
            "id": "test_003",
            "title": "快手直播带货话术模板",
            "summary": "提供实用的快手直播带货话术模板，涵盖开场、互动、逼单、售后全流程",
            "category": "快手/直播",
            "tags": ["直播", "带货", "话术"],
            "price": 40,
            "purchase_count": 95,
            "avg_score": 4.3,
            "created_at": "2024-01-17"
        },
        {
            "id": "test_004",
            "title": "微信公众号爆款标题100例",
            "summary": "精选100个微信公众号爆款标题案例，分析其特点和适用场景",
            "category": "公众号/标题",
            "tags": ["标题", "爆款", "公众号"],
            "price": 25,
            "purchase_count": 150,
            "avg_score": 4.6,
            "created_at": "2024-01-18"
        },
        {
            "id": "test_005",
            "title": "B站视频封面设计规范",
            "summary": "详细介绍B站视频封面设计的尺寸、配色、字体、排版等规范和技巧",
            "category": "B站/设计",
            "tags": ["封面", "设计", "规范"],
            "price": 35,
            "purchase_count": 60,
            "avg_score": 4.1,
            "created_at": "2024-01-19"
        }
    ]

    # 索引记忆
    count = engine.index_memories(test_memories, batch_size=10)
    print(f"✓ Indexed {count} memories")

    return count > 0


def test_vector_search():
    """测试向量搜索"""
    print("\n" + "=" * 60)
    print("Test 4: Vector Search")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 测试查询
    queries = [
        "如何制作抖音爆款视频",
        "小红书文案怎么写",
        "直播带货话术",
        "视频封面设计"
    ]

    for query in queries:
        print(f"\n查询: {query}")
        results = engine.search(query, top_k=3, min_score=0.1)

        print(f"找到 {len(results)} 个结果:")
        for idx, (memory_id, score, payload) in enumerate(results, 1):
            print(f"  {idx}. [{score:.3f}] {payload['title']}")
            print(f"     分类: {payload['category']}")
            print(f"     摘要: {payload['summary'][:50]}...")

    return True


def test_search_with_filters():
    """测试带过滤的搜索"""
    print("\n" + "=" * 60)
    print("Test 5: Search with Filters")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 按分类过滤
    print("\n按分类过滤: category='抖音/爆款'")
    results = engine.search(
        "爆款视频",
        top_k=5,
        filters={"category": "抖音/爆款"}
    )

    for idx, (memory_id, score, payload) in enumerate(results, 1):
        print(f"  {idx}. [{score:.3f}] {payload['title']} - {payload['category']}")

    # 按价格过滤（通过 Qdrant Filter）
    print("\n按价格过滤: price <= 40")
    from qdrant_client.http.models import Filter, FieldCondition, Range

    results = engine.search(
        "视频",
        top_k=5,
        payload_filter=Filter(
            must=[
                FieldCondition(
                    key="price",
                    range=Range(lte=40)
                )
            ]
        )
    )

    for idx, (memory_id, score, payload) in enumerate(results, 1):
        print(f"  {idx}. [{score:.3f}] {payload['title']} - 价格: {payload['price']}")

    return True


def test_performance():
    """测试性能"""
    print("\n" + "=" * 60)
    print("Test 6: Performance Test")
    print("=" * 60)

    import time

    engine = get_qdrant_engine()

    # 测试查询速度
    query = "如何制作爆款视频"
    iterations = 10

    times = []
    for i in range(iterations):
        start = time.time()
        results = engine.search(query, top_k=10)
        elapsed = (time.time() - start) * 1000  # ms
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print(f"查询 '{query}' {iterations} 次的性能:")
    print(f"  平均: {avg_time:.2f} ms")
    print(f"  最小: {min_time:.2f} ms")
    print(f"  最大: {max_time:.2f} ms")

    # 性能目标：< 500ms
    if avg_time < 500:
        print(f"✓ 性能达标 (< 500ms)")
    else:
        print(f"✗ 性能未达标 (>= 500ms)")

    return avg_time < 500


def test_delete_operations():
    """测试删除操作"""
    print("\n" + "=" * 60)
    print("Test 7: Delete Operations")
    print("=" * 60)

    engine = get_qdrant_engine()

    # 删除单个向量
    success = engine.delete_memory("test_001")
    print(f"✓ Deleted memory 'test_001': {success}")

    # 验证删除
    results = engine.search("抖音爆款", top_k=10)
    test_001_found = any(memory_id == "test_001" for memory_id, _, _ in results)
    print(f"✓ Memory 'test_001' found after delete: {test_001_found}")

    # 清空 Collection
    # engine.delete_collection()
    # print("✓ Collection deleted")

    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Qdrant Vector Search Test Suite")
    print("=" * 60)

    tests = [
        ("Qdrant Connection", test_qdrant_connection),
        ("Create Collection", test_create_collection),
        ("Vector Indexing", test_vector_indexing),
        ("Vector Search", test_vector_search),
        ("Search with Filters", test_search_with_filters),
        ("Performance", test_performance),
        ("Delete Operations", test_delete_operations),
    ]

    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # 汇总
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
