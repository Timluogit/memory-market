"""测试语义搜索功能"""
import asyncio
from app.search.vector_search import get_search_engine


def test_vector_search():
    """测试向量搜索引擎"""
    print("=== 测试向量搜索引擎 ===\n")

    # 创建测试数据
    test_memories = [
        {
            'id': 'mem_001',
            'title': 'Python FastAPI 开发指南',
            'summary': '介绍如何使用 FastAPI 框架快速构建 REST API，包括路由、依赖注入、数据验证等功能'
        },
        {
            'id': 'mem_002',
            'title': '机器学习入门教程',
            'summary': '涵盖机器学习基础概念、算法原理和实战案例，包括监督学习、无监督学习等'
        },
        {
            'id': 'mem_003',
            'title': '数据库设计与优化',
            'summary': '讲解关系型数据库设计原则、SQL 查询优化、索引策略等高级主题'
        },
        {
            'id': 'mem_004',
            'title': 'Web API 安全最佳实践',
            'summary': '讨论 API 认证、授权、数据加密、防止常见攻击等安全问题'
        },
        {
            'id': 'mem_005',
            'title': 'Python 异步编程',
            'summary': '深入讲解 async/await 语法、异步 I/O、并发编程模式和性能优化技巧'
        }
    ]

    # 获取搜索引擎
    engine = get_search_engine()

    # 索引测试数据
    print("1. 索引测试数据...")
    engine.index_memories(test_memories)
    print(f"   已索引 {engine.get_memory_count()} 条记忆\n")

    # 测试语义搜索
    print("2. 测试语义搜索")
    test_queries = [
        "API 开发",
        "数据库性能",
        "异步编程",
        "web安全"
    ]

    for query in test_queries:
        print(f"\n   查询: '{query}'")
        results = engine.search(query, top_k=3, min_similarity=0.1)

        if results:
            for i, (memory_id, score) in enumerate(results, 1):
                memory = next(m for m in test_memories if m['id'] == memory_id)
                print(f"   {i}. [{score:.3f}] {memory['title']}")
        else:
            print("   未找到结果")

    # 测试混合搜索
    print("\n\n3. 测试混合搜索")
    query = "API"
    keyword_ids = {'mem_001', 'mem_004'}  # 假设关键词匹配到这些

    print(f"   查询: '{query}'")
    print(f"   关键词匹配: {keyword_ids}")

    results = engine.search_with_keywords(
        query,
        keyword_ids,
        top_k=5,
        semantic_weight=0.6
    )

    print(f"   混合搜索结果:")
    for i, (memory_id, score) in enumerate(results, 1):
        memory = next(m for m in test_memories if m['id'] == memory_id)
        print(f"   {i}. [{score:.3f}] {memory['title']}")

    # 性能测试
    print("\n\n4. 性能测试")
    import time

    query = "Python 编程开发"
    iterations = 100

    start_time = time.time()
    for _ in range(iterations):
        engine.search(query, top_k=10)
    elapsed = time.time() - start_time

    avg_time = (elapsed / iterations) * 1000  # 转换为毫秒
    print(f"   平均搜索延迟: {avg_time:.2f}ms")
    print(f"   目标: < 200ms {'✓' if avg_time < 200 else '✗'}")

    # 缓存测试
    print("\n5. 缓存测试")
    engine.clear_cache()
    print("   缓存已清除")

    engine.batch_index_with_cache(test_memories)
    print("   使用缓存重新索引...")

    # 强制重建
    engine.batch_index_with_cache(test_memories, force_rebuild=True)
    print("   强制重建索引...")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_vector_search()
