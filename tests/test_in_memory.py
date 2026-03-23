"""内存运行架构测试

覆盖：
- MemoryIndex 索引构建、更新、持久化
- InMemoryVectorEngine 向量搜索
- InMemoryHybridEngine 混合搜索
- 性能基准测试
"""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

# ===== 测试数据 =====

SAMPLE_MEMORIES = [
    {
        "memory_id": "mem_001",
        "title": "Python异步编程最佳实践",
        "summary": "介绍Python asyncio模块的使用方法，包括协程、事件循环、任务管理等核心概念",
        "content": "async/await语法、asyncio.gather并发执行、aiohttp网络请求",
        "category": "编程/python",
        "tags": ["python", "async", "asyncio"],
        "price": 50.0,
        "purchase_count": 120,
        "avg_score": 4.5,
        "verification_score": 0.9,
        "created_at": 1700000000.0,
        "updated_at": 1700100000.0,
        "is_active": True,
        "expiry_time": None,
        "seller_name": "python_expert",
        "seller_reputation": 4.8,
    },
    {
        "memory_id": "mem_002",
        "title": "React Hooks完全指南",
        "summary": "深入理解React Hooks的原理和使用场景，useState、useEffect、useContext等",
        "content": "React函数组件、自定义Hooks、性能优化技巧",
        "category": "编程/react",
        "tags": ["react", "hooks", "javascript"],
        "price": 30.0,
        "purchase_count": 200,
        "avg_score": 4.2,
        "verification_score": 0.85,
        "created_at": 1700200000.0,
        "updated_at": 1700300000.0,
        "is_active": True,
        "expiry_time": None,
        "seller_name": "frontend_dev",
        "seller_reputation": 4.5,
    },
    {
        "memory_id": "mem_003",
        "title": "机器学习入门教程",
        "summary": "从零开始学习机器学习，涵盖监督学习、无监督学习、特征工程等基础内容",
        "content": "scikit-learn、pandas、numpy、线性回归、决策树",
        "category": "AI/机器学习",
        "tags": ["ml", "机器学习", "python"],
        "price": 80.0,
        "purchase_count": 500,
        "avg_score": 4.8,
        "verification_score": 0.95,
        "created_at": 1699000000.0,
        "updated_at": 1699100000.0,
        "is_active": True,
        "expiry_time": None,
        "seller_name": "ml_researcher",
        "seller_reputation": 4.9,
    },
    {
        "memory_id": "mem_004",
        "title": "Docker容器化部署实战",
        "summary": "Docker基础概念和实战部署，包括Dockerfile编写、docker-compose编排",
        "content": "容器、镜像、Docker Hub、多阶段构建、网络配置",
        "category": "运维/docker",
        "tags": ["docker", "devops", "容器"],
        "price": 25.0,
        "purchase_count": 80,
        "avg_score": 4.0,
        "verification_score": 0.7,
        "created_at": 1698000000.0,
        "updated_at": 1698100000.0,
        "is_active": True,
        "expiry_time": None,
        "seller_name": "devops_eng",
        "seller_reputation": 4.3,
    },
    {
        "memory_id": "mem_005",
        "title": "过期记忆测试",
        "summary": "这是一条已过期的记忆，用于测试过滤功能",
        "content": "过期内容",
        "category": "测试",
        "tags": ["test", "expired"],
        "price": 0.0,
        "purchase_count": 0,
        "avg_score": 1.0,
        "verification_score": 0.0,
        "created_at": 1600000000.0,
        "updated_at": 1600000000.0,
        "is_active": True,
        "expiry_time": 1600100000.0,  # 已过期
        "seller_name": "test_seller",
        "seller_reputation": 1.0,
    },
]

# 随机向量（512维，模拟 BGE 嵌入）
VECTOR_DIM = 512


def _make_vectors(n: int, dim: int = VECTOR_DIM, seed: int = 42) -> list:
    """生成随机向量"""
    rng = np.random.RandomState(seed)
    vectors = []
    for _ in range(n):
        v = rng.randn(dim).astype(np.float32)
        v /= np.linalg.norm(v)  # 归一化
        vectors.append(v)
    return vectors


# ===== MemoryIndex 测试 =====

class TestMemoryIndex:
    """内存索引测试"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp(prefix="test_memory_index_")

    def teardown_method(self):
        """每个测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_index(self):
        """测试索引构建"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        count = index.build_index(SAMPLE_MEMORIES)

        assert count == 5
        assert index.get_entry_count() == 5
        assert not index.is_empty()

    def test_build_index_with_vectors(self):
        """测试带向量的索引构建"""
        from app.services.memory_index import MemoryIndex

        vectors = _make_vectors(len(SAMPLE_MEMORIES))
        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES, vectors=vectors)

        assert index.get_vector_count() == 5
        matrix, ids = index.get_vectors()
        assert matrix is not None
        assert matrix.shape == (5, VECTOR_DIM)
        assert len(ids) == 5

    def test_keyword_search(self):
        """测试关键词搜索"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        # 搜索"Python"
        results = index.keyword_search("Python")
        assert len(results) > 0
        result_ids = [mid for mid, _ in results]
        assert "mem_001" in result_ids  # Python异步编程

        # 搜索"React"
        results = index.keyword_search("React")
        result_ids = [mid for mid, _ in results]
        assert "mem_002" in result_ids  # React Hooks

    def test_category_filter(self):
        """测试分类过滤"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        python_ids = index.filter_by_category("编程/python")
        assert "mem_001" in python_ids

        ml_ids = index.filter_by_category("AI/机器学习")
        assert "mem_003" in ml_ids

    def test_tag_filter(self):
        """测试标签过滤"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        python_ids = index.filter_by_tag("python")
        assert "mem_001" in python_ids
        assert "mem_003" in python_ids  # 机器学习也带python标签

    def test_add_memory(self):
        """测试增量添加记忆"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES[:3])

        new_mem = {
            "memory_id": "mem_new",
            "title": "新增测试记忆",
            "summary": "测试增量添加",
            "category": "测试",
            "tags": ["test"],
        }
        index.add_memory(new_mem)

        assert index.get_entry_count() == 4
        entry = index.get_entry("mem_new")
        assert entry is not None
        assert entry.title == "新增测试记忆"

    def test_update_memory(self):
        """测试更新记忆"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        index.update_memory({
            "memory_id": "mem_001",
            "title": "Python异步编程高级技巧",
            "summary": "更新后的摘要",
            "category": "编程/python",
            "tags": ["python", "async"],
        })

        entry = index.get_entry("mem_001")
        assert entry.title == "Python异步编程高级技巧"

    def test_remove_memory(self):
        """测试删除记忆"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        assert index.remove_memory("mem_001")
        assert index.get_entry("mem_001") is None
        assert index.get_entry_count() == 4

        # 删除不存在的
        assert not index.remove_memory("nonexistent")

    def test_persist_and_load(self):
        """测试持久化和加载"""
        from app.services.memory_index import MemoryIndex

        vectors = _make_vectors(len(SAMPLE_MEMORIES))

        # 构建并持久化
        index1 = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index1.build_index(SAMPLE_MEMORIES, vectors=vectors)
        assert index1.persist()

        # 验证文件存在
        assert (Path(self.temp_dir) / "entries.json").exists()
        assert (Path(self.temp_dir) / "vectors.npy").exists()
        assert (Path(self.temp_dir) / "meta.json").exists()

        # 加载到新索引
        index2 = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        assert index2.load()

        assert index2.get_entry_count() == 5
        assert index2.get_vector_count() == 5

        # 验证关键词搜索仍然工作
        results = index2.keyword_search("Python")
        assert len(results) > 0

    def test_clear(self):
        """测试清空索引"""
        from app.services.memory_index import MemoryIndex

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES)

        index.clear()
        assert index.is_empty()
        assert index.get_entry_count() == 0
        assert index.get_vector_count() == 0


# ===== InMemoryVectorEngine 测试 =====

class TestInMemoryVectorEngine:
    """内存向量搜索引擎测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_vector_")
        self.vectors = _make_vectors(len(SAMPLE_MEMORIES))

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build_index(self):
        from app.services.memory_index import MemoryIndex
        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES, vectors=self.vectors)
        return index

    def test_cosine_search(self):
        """测试余弦相似度搜索"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index, similarity_metric="cosine")

        # 用第一个向量搜索自己
        results = engine.search(self.vectors[0], top_k=5)
        assert len(results) > 0
        assert results[0][0] == "mem_001"  # 应该最匹配自己
        assert results[0][1] > 0.99  # 余弦相似度接近1

    def test_euclidean_search(self):
        """测试欧氏距离搜索"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index, similarity_metric="euclidean")

        results = engine.search(self.vectors[0], top_k=5)
        assert len(results) > 0
        assert results[0][0] == "mem_001"

    def test_batch_search(self):
        """测试批量搜索"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index, similarity_metric="cosine")

        query_vectors = self.vectors[:3]
        results = engine.batch_search(query_vectors, top_k=3)

        assert len(results) == 3
        # 每个查询应该最匹配自己
        assert results[0][0][0] == "mem_001"
        assert results[1][0][0] == "mem_002"
        assert results[2][0][0] == "mem_003"

    def test_filter_ids(self):
        """测试带过滤的搜索"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index)

        # 只搜索 mem_003 和 mem_004
        results = engine.search(
            self.vectors[0], top_k=5,
            filter_ids={"mem_003", "mem_004"}
        )
        result_ids = [mid for mid, _ in results]
        assert "mem_001" not in result_ids
        assert "mem_003" in result_ids or "mem_004" in result_ids

    def test_min_score(self):
        """测试最小分数过滤"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index)

        results = engine.search(self.vectors[0], top_k=5, min_score=0.99)
        # 严格阈值下应该只有自己或很少的结果
        for _, score in results:
            assert score >= 0.99

    def test_empty_index(self):
        """测试空索引搜索"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        index.clear()
        engine = InMemoryVectorEngine(index=index)

        results = engine.search(self.vectors[0])
        assert results == []

    def test_stats(self):
        """测试统计信息"""
        from app.search.in_memory_vector import InMemoryVectorEngine

        index = self._build_index()
        engine = InMemoryVectorEngine(index=index)

        engine.search(self.vectors[0])
        engine.search(self.vectors[1])

        stats = engine.get_stats()
        assert stats['total_searches'] == 2
        assert stats['avg_search_time'] > 0


# ===== InMemoryHybridEngine 测试 =====

class TestInMemoryHybridEngine:
    """内存混合搜索引擎测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_hybrid_")
        self.vectors = _make_vectors(len(SAMPLE_MEMORIES))

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build_engines(self):
        from app.services.memory_index import MemoryIndex
        from app.search.in_memory_vector import InMemoryVectorEngine
        from app.search.in_memory_hybrid import InMemoryHybridEngine

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(SAMPLE_MEMORIES, vectors=self.vectors)

        vector_engine = InMemoryVectorEngine(index=index)
        hybrid_engine = InMemoryHybridEngine(
            index=index,
            vector_engine=vector_engine,
            enable_rerank=True
        )
        return index, vector_engine, hybrid_engine

    def test_full_search(self):
        """测试全功能搜索"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="Python编程",
            query_vector=self.vectors[0],
            top_k=5,
            search_mode="full"
        )

        assert 'items' in result
        assert 'total' in result
        assert 'search_time' in result
        assert result['total'] > 0
        assert result['search_mode'] == 'full'

    def test_vector_only_search(self):
        """测试纯向量搜索"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="test",
            query_vector=self.vectors[0],
            search_mode="vector"
        )

        assert result['total'] > 0
        assert result['search_mode'] == 'vector'

    def test_keyword_only_search(self):
        """测试纯关键词搜索"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="Python",
            search_mode="keyword"
        )

        assert result['total'] > 0
        ids = [item['memory_id'] for item in result['items']]
        assert "mem_001" in ids  # Python异步编程

    def test_category_filter(self):
        """测试分类过滤"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="编程",
            filter_category="编程/python"
        )

        for item in result['items']:
            assert item['category'] == '编程/python'

    def test_tag_filter(self):
        """测试标签过滤"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="技术",
            filter_tag="python"
        )

        for item in result['items']:
            assert 'python' in item['tags']

    def test_expired_filter(self):
        """测试过期记忆过滤"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="测试",
            filter_expired=True
        )

        ids = [item['memory_id'] for item in result['items']]
        assert "mem_005" not in ids  # 过期记忆应该被过滤

    def test_pagination(self):
        """测试分页"""
        _, _, engine = self._build_engines()

        page1 = engine.search(query="编程", page=1, page_size=2)
        page2 = engine.search(query="编程", page=2, page_size=2)

        assert len(page1['items']) <= 2
        assert len(page2['items']) <= 2

        # 页码不同，结果应该不同
        if page1['items'] and page2['items']:
            p1_ids = {item['memory_id'] for item in page1['items']}
            p2_ids = {item['memory_id'] for item in page2['items']}
            assert p1_ids != p2_ids

    def test_sort_by_time(self):
        """测试按时间排序"""
        _, _, engine = self._build_engines()

        result = engine.search(query="编程", sort_by="time")
        items = result['items']
        if len(items) > 1:
            for i in range(len(items) - 1):
                assert items[i]['updated_at'] >= items[i + 1]['updated_at']

    def test_sort_by_popularity(self):
        """测试按热度排序"""
        _, _, engine = self._build_engines()

        result = engine.search(query="编程", sort_by="popularity")
        items = result['items']
        if len(items) > 1:
            for i in range(len(items) - 1):
                assert items[i]['purchase_count'] >= items[i + 1]['purchase_count']

    def test_rerank(self):
        """测试重排功能"""
        _, _, engine = self._build_engines()

        with_rerank = engine.search(
            query="Python",
            query_vector=self.vectors[0],
            enable_rerank=True
        )
        engine.enable_rerank = False
        without_rerank = engine.search(
            query="Python",
            query_vector=self.vectors[0],
        )

        # 重排后分数应该不同
        assert with_rerank['items'][0]['relevance_score'] != without_rerank['items'][0]['relevance_score']

    def test_empty_result(self):
        """测试空结果"""
        _, _, engine = self._build_engines()

        result = engine.search(
            query="xyznonexistent12345",
            search_mode="keyword"
        )

        # 可能找到也可能找不到，关键不报错
        assert 'items' in result
        assert 'total' in result

    def test_stats(self):
        """测试统计"""
        _, _, engine = self._build_engines()

        engine.search(query="test", query_vector=self.vectors[0])
        engine.search(query="test", search_mode="keyword")

        stats = engine.get_stats()
        assert stats['total_searches'] == 2
        assert stats['mode_counts']['full'] == 1
        assert stats['mode_counts']['keyword'] == 1


# ===== 性能基准测试 =====

class TestPerformance:
    """性能基准测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_perf_")

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_build_performance(self):
        """索引构建性能"""
        from app.services.memory_index import MemoryIndex

        # 生成1000条测试数据
        memories = []
        for i in range(1000):
            memories.append({
                "memory_id": f"perf_{i:04d}",
                "title": f"性能测试记忆 {i} - 关于Python和机器学习",
                "summary": f"这是第{i}条性能测试记忆的摘要，包含编程、AI、深度学习等内容",
                "content": f"详细内容 {i}" * 10,
                "category": "测试/性能",
                "tags": ["perf", "test", "python"],
                "price": float(i % 100),
                "purchase_count": i * 10,
                "avg_score": 3.0 + (i % 20) * 0.1,
                "verification_score": 0.5,
                "created_at": 1700000000.0 + i,
                "updated_at": 1700000000.0 + i,
                "is_active": True,
                "expiry_time": None,
                "seller_name": f"seller_{i % 10}",
                "seller_reputation": 4.0,
            })

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)

        start = time.time()
        index.build_index(memories)
        build_time = time.time() - start

        print(f"\n索引构建: 1000条记忆, {build_time:.2f}s")
        assert build_time < 10.0  # 应该在10秒内完成
        assert index.get_entry_count() == 1000

    def test_vector_search_performance(self):
        """向量搜索性能"""
        from app.services.memory_index import MemoryIndex
        from app.search.in_memory_vector import InMemoryVectorEngine

        n = 5000
        memories = [{"memory_id": f"v_{i}", "title": f"记忆{i}", "summary": f"摘要{i}"} for i in range(n)]
        vectors = _make_vectors(n)

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(memories, vectors=vectors)

        engine = InMemoryVectorEngine(index=index)

        query_vec = vectors[0]
        # 预热
        engine.search(query_vec, top_k=10)

        # 计时
        start = time.time()
        iterations = 100
        for _ in range(iterations):
            engine.search(query_vec, top_k=10)
        elapsed = time.time() - start

        avg_ms = (elapsed / iterations) * 1000
        print(f"\n向量搜索: {n}条记忆, 平均{avg_ms:.2f}ms/次 ({iterations}次)")
        assert avg_ms < 100  # 平均应小于100ms

    def test_keyword_search_performance(self):
        """关键词搜索性能"""
        from app.services.memory_index import MemoryIndex

        n = 5000
        memories = []
        for i in range(n):
            memories.append({
                "memory_id": f"k_{i}",
                "title": f"Python编程技巧第{i}篇",
                "summary": f"关于Python、Django、Flask框架的第{i}个知识点",
                "content": f"Python是编程语言 " * 5,
                "tags": ["python", "programming"],
            })

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(memories)

        # 预热
        index.keyword_search("Python")

        start = time.time()
        iterations = 1000
        for _ in range(iterations):
            index.keyword_search("Python编程")
        elapsed = time.time() - start

        avg_ms = (elapsed / iterations) * 1000
        print(f"\n关键词搜索: {n}条记忆, 平均{avg_ms:.2f}ms/次 ({iterations}次)")
        assert avg_ms < 50  # 倒排索引应该非常快

    def test_persist_performance(self):
        """持久化性能"""
        from app.services.memory_index import MemoryIndex

        n = 2000
        memories = [{"memory_id": f"p_{i}", "title": f"持久化测试{i}", "summary": f"摘要{i}"} for i in range(n)]
        vectors = _make_vectors(n)

        index = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index.build_index(memories, vectors=vectors)

        start = time.time()
        index.persist()
        persist_time = time.time() - start

        print(f"\n持久化: {n}条记忆, {persist_time:.2f}s")
        assert persist_time < 15.0

    def test_load_performance(self):
        """加载性能"""
        from app.services.memory_index import MemoryIndex

        n = 2000
        memories = [{"memory_id": f"l_{i}", "title": f"加载测试{i}", "summary": f"摘要{i}"} for i in range(n)]
        vectors = _make_vectors(n)

        # 先持久化
        index1 = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index1.build_index(memories, vectors=vectors)
        index1.persist()

        # 测试加载
        start = time.time()
        index2 = MemoryIndex(persist_dir=self.temp_dir, auto_persist=False)
        index2.load()
        load_time = time.time() - start

        print(f"\n加载: {n}条记忆, {load_time:.2f}s")
        assert load_time < 10.0
        assert index2.get_entry_count() == n


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
