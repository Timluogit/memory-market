"""Cross-Encoder 重排功能测试"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.services.model_manager import ModelManager, get_model_manager, reset_model_manager
from app.services.reranking_service import RerankingService, get_reranking_service, reset_reranking_service
from app.core.config import settings


class TestModelManager:
    """模型管理器测试"""

    @pytest.fixture
    def model_manager(self, tmp_path):
        """创建模型管理器实例"""
        manager = ModelManager(model_cache_dir=tmp_path, force_cpu=True)
        yield manager
        reset_model_manager()

    def test_detect_device_cpu(self, model_manager):
        """测试设备检测（CPU）"""
        model_manager.force_cpu = True
        device = model_manager._detect_device()
        assert device == "cpu"

    def test_get_model_path(self, model_manager):
        """测试模型路径生成"""
        path = model_manager._get_model_path("BAAI/bge-reranker-large")
        assert path.is_absolute()
        assert "bge-reranker-large" in str(path)

    def test_get_cache_size_empty(self, model_manager):
        """测试空缓存大小"""
        size_info = model_manager.get_cache_size()
        assert size_info["total_size_bytes"] == 0
        assert size_info["model_count"] == 0

    def test_version_info(self, model_manager):
        """测试版本信息管理"""
        # 保存版本信息
        versions = {
            "BAAI/bge-reranker-large": {
                "loaded_at": datetime.now().isoformat(),
                "device": "cpu"
            }
        }
        model_manager._save_version_info(versions)

        # 加载版本信息
        loaded = model_manager._load_version_info()
        assert "BAAI/bge-reranker-large" in loaded
        assert loaded["BAAI/bge-reranker-large"]["device"] == "cpu"

    def test_clear_cache(self, model_manager, tmp_path):
        """测试缓存清理"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # 清理缓存
        model_manager.clear_cache()

        # 检查文件已被删除
        assert not test_file.exists()


class TestRerankingService:
    """重排序服务测试"""

    @pytest.fixture
    def rerank_service(self):
        """创建重排序服务实例"""
        service = RerankingService(
            model_name="BAAI/bge-reranker-large",
            top_k=10,
            threshold=0.3,
            cache_ttl=60
        )
        yield service
        reset_reranking_service()

    @pytest.fixture
    def sample_candidates(self):
        """创建测试候选结果"""
        return [
            {
                'memory_id': 'mem_001',
                'title': 'Python编程教程',
                'summary': 'Python基础语法讲解',
                'content': 'Python是一种高级编程语言，...',
                'base_score': 0.8
            },
            {
                'memory_id': 'mem_002',
                'title': '机器学习入门',
                'summary': '机器学习基础概念',
                'content': '机器学习是人工智能的一个分支...',
                'base_score': 0.7
            },
            {
                'memory_id': 'mem_003',
                'title': 'Web开发指南',
                'summary': 'HTML和CSS基础',
                'content': 'Web开发涉及前端和后端技术...',
                'base_score': 0.6
            }
        ]

    def test_get_cache_key(self, rerank_service):
        """测试缓存键生成"""
        query = "Python教程"
        memory_ids = ["mem_001", "mem_002"]
        key = rerank_service._get_cache_key(query, memory_ids)
        assert key.startswith("rerank:")
        assert "mem_001" not in key  # ID 应该被哈希

    @pytest.mark.asyncio
    async def test_rerank_empty_candidates(self, rerank_service):
        """测试空候选列表"""
        result = await rerank_service.rerank("test", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_skip_small_list(self, rerank_service, sample_candidates):
        """测试候选数量 <= top_k 时跳过重排"""
        # top_k 默认为 10，候选只有 3 个，应该跳过重排
        result = await rerank_service.rerank("Python", sample_candidates)
        assert len(result) == 3
        # 应该返回原始结果
        assert result == sample_candidates

    @pytest.mark.asyncio
    async def test_rerank_with_threshold(self, rerank_service, sample_candidates):
        """测试阈值过滤"""
        # 创建更多候选以触发重排
        large_candidates = sample_candidates * 20  # 60 个候选

        # Mock CrossEncoder.predict 返回低分
        with patch.object(rerank_service, 'encoder') as mock_encoder:
            mock_encoder.predict.return_value = [0.1] * 60  # 所有结果都低于阈值 0.3

            result = await rerank_service.rerank("Python", large_candidates, threshold=0.3)

            # 应该返回空列表（所有结果都低于阈值）
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_rerank_top_k(self, rerank_service):
        """测试 Top-K 筛选"""
        # 创建大量候选
        candidates = [
            {
                'memory_id': f'mem_{i:03d}',
                'title': f'Title {i}',
                'summary': f'Summary {i}',
                'content': f'Content {i}'
            }
            for i in range(100)
        ]

        # Mock CrossEncoder.predict 返回递减分数
        with patch.object(rerank_service, 'encoder') as mock_encoder:
            mock_encoder.predict.return_value = list(range(100, 0, -1))

            result = await rerank_service.rerank("test", candidates, top_k=20, threshold=0.0)

            # 应该返回 Top-20
            assert len(result) == 20
            # 检查是否按分数降序排序
            scores = [r['rerank_score'] for r in result]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_rerank_prediction_error(self, rerank_service, sample_candidates):
        """测试预测失败时的回退"""
        # 创建大量候选以触发重排
        large_candidates = sample_candidates * 20

        # Mock CrossEncoder.predict 抛出异常
        with patch.object(rerank_service, 'encoder') as mock_encoder:
            mock_encoder.predict.side_effect = Exception("Model error")

            # 应该返回原始结果（回退）
            result = await rerank_service.rerank("Python", large_candidates)
            assert len(result) == len(large_candidates)

    @pytest.mark.asyncio
    async def test_evaluate_reranking_mrr(self, rerank_service):
        """测试 MRR 计算"""
        candidates = [
            {'memory_id': 'mem_001', 'title': 'Python教程', 'content': 'Python...'},
            {'memory_id': 'mem_002', 'title': 'Java教程', 'content': 'Java...'},
            {'memory_id': 'mem_003', 'title': 'Python高级', 'content': 'Python...'}
        ]
        ground_truth = ['mem_003', 'mem_001']  # 正确结果顺序

        # Mock 重排结果：正确结果排在第一位
        with patch.object(rerank_service, 'rerank', return_value=[
            {'memory_id': 'mem_003', 'rerank_score': 0.9},
            {'memory_id': 'mem_002', 'rerank_score': 0.5},
            {'memory_id': 'mem_001', 'rerank_score': 0.4}
        ]):
            metrics = await rerank_service.evaluate_reranking("Python教程", candidates, ground_truth)

            # MRR = 1/1 = 1.0（第一个结果就是正确的）
            assert metrics['mrr'] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_reranking_ndcg(self, rerank_service):
        """测试 NDCG 计算"""
        candidates = [
            {'memory_id': 'mem_001', 'title': 'Python', 'content': '...'},
            {'memory_id': 'mem_002', 'title': 'Java', 'content': '...'},
            {'memory_id': 'mem_003', 'title': 'Python高级', 'content': '...'}
        ]
        ground_truth = ['mem_003', 'mem_001']

        # Mock 重排结果
        with patch.object(rerank_service, 'rerank', return_value=[
            {'memory_id': 'mem_001', 'rerank_score': 0.8},  # 第2个正确
            {'memory_id': 'mem_003', 'rerank_score': 0.6},  # 第1个正确
            {'memory_id': 'mem_002', 'rerank_score': 0.4}
        ]):
            metrics = await rerank_service.evaluate_reranking("Python", candidates, ground_truth)

            # NDCG 应该在 0 和 1 之间
            assert 0 <= metrics['ndcg@5'] <= 1.0
            assert 0 <= metrics['ndcg@10'] <= 1.0

    def test_calculate_mrr(self, rerank_service):
        """测试 MRR 计算逻辑"""
        ranked_ids = ['mem_005', 'mem_003', 'mem_001', 'mem_002']
        ground_truth = ['mem_001', 'mem_002']

        # 正确结果在位置 2（索引1）
        mrr = rerank_service._calculate_mrr(ranked_ids, ground_truth)
        assert mrr == pytest.approx(1.0 / 2, rel=1e-6)

        # 无正确结果
        mrr = rerank_service._calculate_mrr(['mem_004', 'mem_005'], ground_truth)
        assert mrr == 0.0

    def test_calculate_ndcg(self, rerank_service):
        """测试 NDCG 计算逻辑"""
        ranked_ids = ['mem_001', 'mem_003', 'mem_002']
        ground_truth = ['mem_001', 'mem_002']

        ndcg = rerank_service._calculate_ndcg(ranked_ids, ground_truth, k=5)
        assert 0 < ndcg <= 1.0

        # 空 ground truth
        ndcg = rerank_service._calculate_ndcg(ranked_ids, [], k=5)
        assert ndcg == 0.0


class TestRerankingCache:
    """重排序缓存测试"""

    @pytest.fixture
    def rerank_service(self):
        """创建重排序服务实例（启用缓存）"""
        service = RerankingService(
            model_name="BAAI/bge-reranker-large",
            top_k=10,
            threshold=0.3,
            cache_ttl=60
        )
        yield service
        reset_reranking_service()

    @pytest.mark.asyncio
    async def test_cache_hit(self, rerank_service):
        """测试缓存命中"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b'{"reranked_ids": ["mem_001"], "top_k": 10, "threshold": 0.3, "model": "BAAI/bge-reranker-large"}'
        rerank_service._redis = mock_redis

        candidates = [
            {'memory_id': 'mem_001', 'title': 'Test', 'content': '...'}
        ]

        result = await rerank_service._get_from_cache("query", candidates, top_k=10, threshold=0.3)
        assert result is not None
        assert len(result) == 1
        assert result[0]['memory_id'] == 'mem_001'

    @pytest.mark.asyncio
    async def test_cache_miss(self, rerank_service):
        """测试缓存未命中"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        rerank_service._redis = mock_redis

        candidates = [
            {'memory_id': 'mem_001', 'title': 'Test', 'content': '...'}
        ]

        result = await rerank_service._get_from_cache("query", candidates, top_k=10, threshold=0.3)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_write(self, rerank_service):
        """测试缓存写入"""
        # Mock Redis
        mock_redis = AsyncMock()
        rerank_service._redis = mock_redis

        candidates = [
            {'memory_id': 'mem_001', 'title': 'Test', 'content': '...'}
        ]
        reranked = [{'memory_id': 'mem_001', 'rerank_score': 0.9}]

        await rerank_service._save_to_cache("query", candidates, reranked, top_k=10, threshold=0.3)

        # 验证 Redis.setex 被调用
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][2]  # TTL 参数存在

    @pytest.mark.asyncio
    async def test_cache_disabled(self, rerank_service):
        """测试禁用缓存"""
        with patch.object(settings, 'CACHE_ENABLED', False):
            result = await rerank_service._get_from_cache("query", [], 10, 0.3)
            assert result is None

            # 写入时应该静默失败
            await rerank_service._save_to_cache("query", [], [], 10, 0.3)
            # 不会抛出异常


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_reranking_workflow(self):
        """测试完整的重排序流程"""
        # 创建服务
        service = RerankingService(top_k=5, threshold=0.0, cache_ttl=60)

        # 创建候选结果
        candidates = [
            {
                'memory_id': f'mem_{i:03d}',
                'title': f'关于{i}的教程',
                'summary': f'学习{i}',
                'content': f'这是一个关于{i}的详细教程'
            }
            for i in range(50)
        ]

        # Mock CrossEncoder
        with patch.object(service, 'encoder') as mock_encoder:
            # 返回随机分数
            import random
            mock_encoder.predict.return_value = [random.random() for _ in range(50)]

            # 执行重排
            result = await service.rerank("学习", candidates)

            # 验证结果
            assert len(result) == 5  # top_k=5
            assert all('rerank_score' in r for r in result)
            assert all(r['rerank_score'] >= 0 for r in result)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
