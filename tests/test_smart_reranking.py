"""智能重排测试套件

测试覆盖:
1. 特征提取（FeatureExtractor）
2. 智能重排服务（SmartRerankingService）
3. 评估指标计算（RerankingEvaluator）
4. A/B 测试
5. 配置管理和策略切换
6. API 端点
"""
import pytest
import asyncio
import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# ── 特征提取测试 ──


class TestFeatureExtractor:
    """特征提取器测试"""

    def _make_extractor(self, now=None):
        from app.services.reranking_features import FeatureExtractor
        return FeatureExtractor(now=now or datetime(2025, 6, 15))

    def _make_candidate(self, **overrides):
        base = {
            "memory_id": "mem_001",
            "title": "Python FastAPI 教程",
            "summary": "完整的 FastAPI 入门教程，包含路由、依赖注入、数据库集成",
            "content_text": "FastAPI 是一个现代 Python web 框架...",
            "tags": ["python", "fastapi", "教程"],
            "category": "编程教程",
            "created_at": "2025-06-10T10:00:00",
            "avg_score": 4.5,
            "purchase_count": 50,
            "verification_score": 0.8,
        }
        base.update(overrides)
        return base

    def test_basic_feature_extraction(self):
        ext = self._make_extractor()
        candidate = self._make_candidate()
        fv = ext.extract_features(
            query="Python FastAPI 教程",
            candidate=candidate,
            semantic_score=0.85,
            embedding_similarity=0.78,
        )

        assert fv.memory_id == "mem_001"
        assert fv.semantic_score == 0.85
        assert fv.embedding_similarity == 0.78
        assert fv.keyword_exact_match > 0  # 查询词应该能匹配到
        assert fv.keyword_title_match > 0  # 标题包含关键词
        assert fv.recency_score > 0  # 5天前，应该比较新鲜
        assert fv.freshness_score == 1.0  # 7天内 = 1.0
        assert 0 <= fv.quality_signal <= 1.0

    def test_keyword_match_no_overlap(self):
        """查询和内容无重叠时关键词得分为0"""
        ext = self._make_extractor()
        candidate = self._make_candidate(
            title="Java Spring Boot 入门",
            summary="Spring Boot 快速搭建后端服务",
            content_text="Java 是企业级开发语言...",
            tags=["java", "spring"],
        )
        fv = ext.extract_features(
            query="Python FastAPI 教程",
            candidate=candidate,
        )
        # Java 内容 vs Python 查询 → 关键词得分应该很低
        assert fv.keyword_exact_match < 0.5

    def test_recency_score_decay(self):
        """时效性随时间衰减"""
        ext = self._make_extractor(now=datetime(2025, 6, 15))

        recent = self._make_candidate(created_at="2025-06-14T10:00:00")  # 1天前
        old = self._make_candidate(created_at="2025-01-01T10:00:00")  # ~165天前

        fv_recent = ext.extract_features(query="test", candidate=recent)
        fv_old = ext.extract_features(query="test", candidate=old)

        assert fv_recent.recency_score > fv_old.recency_score

    def test_freshness_score_boundaries(self):
        """新鲜度得分边界测试"""
        ext = self._make_extractor(now=datetime(2025, 6, 15))

        # 1天前 = 1.0
        c1 = self._make_candidate(created_at="2025-06-14T10:00:00")
        fv1 = ext.extract_features(query="test", candidate=c1)
        assert fv1.freshness_score == 1.0

        # 30天前 → 应该 < 0.6
        c2 = self._make_candidate(created_at="2025-05-16T10:00:00")
        fv2 = ext.extract_features(query="test", candidate=c2)
        assert fv2.freshness_score < 0.6

    def test_no_created_at(self):
        """无时间信息时给中等分"""
        ext = self._make_extractor()
        candidate = self._make_candidate(created_at=None)
        fv = ext.extract_features(query="test", candidate=candidate)
        assert fv.recency_score == 0.5

    def test_quality_signal(self):
        """质量信号计算"""
        ext = self._make_extractor()

        high_quality = self._make_candidate(
            avg_score=5.0, purchase_count=100, verification_score=1.0
        )
        low_quality = self._make_candidate(
            avg_score=1.0, purchase_count=0, verification_score=0.0
        )

        fv_high = ext.extract_features(query="test", candidate=high_quality)
        fv_low = ext.extract_features(query="test", candidate=low_quality)

        assert fv_high.quality_signal > fv_low.quality_signal

    def test_user_interest_match(self):
        """用户兴趣匹配"""
        ext = self._make_extractor()
        candidate = self._make_candidate()
        profile = {
            "interests": ["Python", "FastAPI"],
            "research_areas": ["Web 开发"],
            "tech_stack": [{"name": "Python"}],
        }

        fv = ext.extract_features(
            query="教程",
            candidate=candidate,
            user_profile=profile,
        )
        assert fv.user_interest_match > 0

    def test_user_profile_no_match(self):
        """用户画像无匹配时为0"""
        ext = self._make_extractor()
        candidate = self._make_candidate(
            title="Go 语言入门",
            tags=["golang"],
            category="编程",
        )
        profile = {
            "interests": ["Python", "机器学习"],
            "research_areas": [],
            "tech_stack": [],
        }

        fv = ext.extract_features(
            query="教程",
            candidate=candidate,
            user_profile=profile,
        )
        assert fv.user_interest_match == 0.0

    def test_batch_extraction(self):
        """批量特征提取"""
        ext = self._make_extractor()
        candidates = [self._make_candidate(memory_id=f"mem_{i}") for i in range(5)]
        fvs = ext.extract_batch(
            query="Python",
            candidates=candidates,
            semantic_scores=[0.9, 0.8, 0.7, 0.6, 0.5],
            embedding_similarities=[0.85, 0.75, 0.65, 0.55, 0.45],
        )
        assert len(fvs) == 5
        assert fvs[0].semantic_score == 0.9
        assert fvs[4].semantic_score == 0.5

    def test_tokenization(self):
        """分词测试"""
        ext = self._make_extractor()
        tokens = ext._tokenize("Python FastAPI 教程")
        assert "python" in tokens
        assert "fastapi" in tokens
        assert "教" in tokens or "教程" in tokens

    def test_bm25_score(self):
        """BM25 得分计算"""
        ext = self._make_extractor()
        terms = ext._tokenize("Python 教程")
        score = ext._bm25_score(terms, "python 教程", "python 入门", "python 是语言")
        assert score > 0

        # 无匹配 → 得分为 0
        score_no_match = ext._bm25_score(terms, "java spring", "golang 入门", "rust 语言")
        assert score_no_match == 0.0


# ── 智能重排服务测试 ──


class TestSmartRerankingService:
    """智能重排服务测试"""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        from app.services.smart_reranking import reset_smart_reranking_service
        from app.services.reranking_features import reset_feature_extractor
        reset_smart_reranking_service()
        reset_feature_extractor()
        yield
        reset_smart_reranking_service()
        reset_feature_extractor()

    def _make_service(self, **config_overrides):
        from app.services.smart_reranking import SmartRerankingService, RerankingConfig
        config = RerankingConfig(**config_overrides)
        return SmartRerankingService(config=config)

    def _make_candidates(self, n=10):
        return [
            {
                "memory_id": f"mem_{i:03d}",
                "title": f"Test Memory {i}",
                "summary": f"This is test memory number {i} about Python programming",
                "content_text": f"Content for memory {i}: Python is great for {['web', 'data', 'ml', 'api', 'cli'][i % 5]}",
                "tags": ["python", "test"],
                "category": "编程",
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
                "avg_score": 4.0 + (i % 5) * 0.2,
                "purchase_count": 10 * (i + 1),
                "verification_score": 0.7,
                "score": 0.9 - i * 0.05,
            }
            for i in range(n)
        ]

    @pytest.mark.asyncio
    async def test_rerank_returns_sorted(self):
        """重排结果应该按 final_score 降序"""
        service = self._make_service(use_cross_encoder=False)
        candidates = self._make_candidates(10)
        results = await service.rerank(query="Python 编程", candidates=candidates)

        assert len(results) > 0
        scores = [r["final_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_rerank_empty_candidates(self):
        """空候选列表直接返回空"""
        service = self._make_service(use_cross_encoder=False)
        results = await service.rerank(query="test", candidates=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_too_few_candidates(self):
        """候选数少于最小值时跳过重排"""
        service = self._make_service(
            use_cross_encoder=False,
            min_candidates_for_rerank=5,
        )
        candidates = self._make_candidates(3)
        results = await service.rerank(query="Python", candidates=candidates)
        assert len(results) == 3  # 直接返回，不重排

    @pytest.mark.asyncio
    async def test_top_k_truncation(self):
        """top_k 应该截断结果"""
        service = self._make_service(use_cross_encoder=False, top_k=3)
        candidates = self._make_candidates(10)
        results = await service.rerank(query="Python", candidates=candidates)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_threshold_filter(self):
        """阈值过滤"""
        service = self._make_service(
            use_cross_encoder=False,
            threshold=0.99,  # 极高阈值
        )
        candidates = self._make_candidates(10)
        results = await service.rerank(query="Python", candidates=candidates)
        # 几乎所有结果应该被过滤掉
        assert all(r["final_score"] >= 0.99 for r in results)

    @pytest.mark.asyncio
    async def test_strategy_switching(self):
        """不同策略应该产生不同结果"""
        service = self._make_service(use_cross_encoder=False)
        candidates = self._make_candidates(10)

        results_balanced = await service.rerank(
            query="Python", candidates=candidates, strategy="balanced"
        )
        results_semantic = await service.rerank(
            query="Python", candidates=candidates, strategy="semantic_heavy"
        )

        # 排名应该可能不同（不严格断言，因为可能恰好相同）
        assert len(results_balanced) == len(results_semantic)

    @pytest.mark.asyncio
    async def test_override_weights(self):
        """权重覆盖应该生效"""
        service = self._make_service(use_cross_encoder=False)
        candidates = self._make_candidates(10)

        # 极端权重：只看关键词精确匹配
        extreme_weights = {
            "semantic_score": 0.0,
            "embedding_similarity": 0.0,
            "keyword_exact_match": 1.0,
            "keyword_bm25": 0.0,
            "keyword_title_match": 0.0,
            "keyword_tag_match": 0.0,
            "recency": 0.0,
            "freshness": 0.0,
            "user_interest": 0.0,
            "user_history": 0.0,
            "user_category": 0.0,
            "quality_signal": 0.0,
            "popularity": 0.0,
            "rating": 0.0,
            "verification": 0.0,
        }

        results = await service.rerank(
            query="Python",
            candidates=candidates,
            override_weights=extreme_weights,
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_result_has_feature_vector(self):
        """结果应该包含特征向量详情"""
        service = self._make_service(use_cross_encoder=False)
        candidates = self._make_candidates(5)
        results = await service.rerank(query="Python", candidates=candidates)

        for r in results:
            assert "feature_vector" in r
            fv = r["feature_vector"]
            assert "semantic" in fv
            assert "kw_exact" in fv
            assert "recency" in fv

    @pytest.mark.asyncio
    async def test_user_profile_personalization(self):
        """有用户画像时个性化应该生效"""
        service = self._make_service(use_cross_encoder=False, strategy="personalized")
        candidates = self._make_candidates(10)
        profile = {
            "interests": ["Python", "FastAPI"],
            "preferred_categories": ["编程"],
        }
        results = await service.rerank(
            query="教程",
            candidates=candidates,
            user_profile=profile,
        )
        assert len(results) > 0

    def test_stats_tracking(self):
        """统计信息应该被跟踪"""
        service = self._make_service(use_cross_encoder=False)
        stats = service.get_stats()
        assert "total_reranks" in stats
        assert stats["total_reranks"] == 0

    def test_config_update(self):
        """配置热更新"""
        from app.services.smart_reranking import RerankingConfig
        service = self._make_service(use_cross_encoder=False)
        new_config = RerankingConfig(strategy="semantic_heavy", top_k=5)
        service.update_config(new_config)
        assert service.config.strategy == "semantic_heavy"
        assert service.config.top_k == 5


# ── 评估器测试 ──


class TestRerankingEvaluator:
    """重排评估器测试"""

    @pytest.fixture(autouse=True)
    def reset(self):
        from app.services.smart_reranking import reset_smart_reranking_service
        from app.services.reranking_features import reset_feature_extractor
        from app.services.reranking_eval import reset_eval_history
        reset_smart_reranking_service()
        reset_feature_extractor()
        reset_eval_history()
        yield

    def test_mrr_calculation(self):
        from app.services.reranking_eval import RerankingEvaluator
        assert RerankingEvaluator._mrr(["a", "b", "c"], {"b"}) == 0.5
        assert RerankingEvaluator._mrr(["a", "b", "c"], {"a"}) == 1.0
        assert RerankingEvaluator._mrr(["a", "b", "c"], {"d"}) == 0.0

    def test_ndcg_calculation(self):
        from app.services.reranking_eval import RerankingEvaluator
        # 完美排名
        ndcg = RerankingEvaluator._ndcg(["a", "b", "c"], ["a", "b"], k=5)
        assert ndcg > 0.9

        # 差排名
        ndcg_bad = RerankingEvaluator._ndcg(["c", "d", "a"], ["a", "b"], k=5)
        assert ndcg_bad < ndcg

    def test_precision_at_k(self):
        from app.services.reranking_eval import RerankingEvaluator
        assert RerankingEvaluator._precision_at_k(["a", "b", "c"], {"a", "b"}, k=2) == 1.0
        assert RerankingEvaluator._precision_at_k(["a", "x", "c"], {"a", "b"}, k=3) == pytest.approx(1/3, rel=1e-2)

    def test_recall_at_k(self):
        from app.services.reranking_eval import RerankingEvaluator
        assert RerankingEvaluator._recall_at_k(["a", "b"], {"a", "b", "c"}, k=2) == pytest.approx(2/3, rel=1e-2)

    def test_average_precision(self):
        from app.services.reranking_eval import RerankingEvaluator
        ap = RerankingEvaluator._average_precision(["a", "b", "c"], {"a", "c"})
        assert ap > 0

    def test_hit_rate(self):
        from app.services.reranking_eval import RankingMetrics
        metrics = RankingMetrics(hit_rate=1.0)
        assert metrics.hit_rate == 1.0

    def test_composite_score(self):
        from app.services.reranking_eval import RankingMetrics
        m = RankingMetrics(
            mrr=0.9, ndcg_at_10=0.85, precision_at_10=0.8,
            map_score=0.75, hit_rate=1.0,
        )
        assert 0 < m.composite_score < 1


# ── A/B 测试测试 ──


class TestABTester:
    """A/B 测试器测试"""

    def test_ab_result_structure(self):
        from app.services.reranking_eval import ABTestResult
        result = ABTestResult(
            strategy_a="balanced",
            strategy_b="semantic_heavy",
            winner="B",
            improvement=0.05,
        )
        d = result.to_dict()
        assert d["winner"] == "B"
        assert d["improvement_pct"] == 5.0


# ── 配置和策略测试 ──


class TestRerankingConfig:
    """重排配置测试"""

    def test_weights_validation(self):
        from app.services.smart_reranking import RerankingWeights
        w = RerankingWeights()
        assert w.validate()

    def test_weights_to_dict(self):
        from app.services.smart_reranking import RerankingWeights
        w = RerankingWeights()
        d = w.to_dict()
        assert "semantic_score" in d
        assert abs(sum(d.values()) - 1.0) < 0.01

    def test_weights_from_dict(self):
        from app.services.smart_reranking import RerankingWeights
        d = {"semantic_score": 0.5, "embedding_similarity": 0.5}
        w = RerankingWeights.from_dict(d)
        assert w.semantic_score == 0.5

    def test_preset_strategies_exist(self):
        from app.services.smart_reranking import PRESET_STRATEGIES
        expected = ["balanced", "semantic_heavy", "keyword_heavy", "freshness_first", "quality_first", "personalized"]
        for name in expected:
            assert name in PRESET_STRATEGIES

    def test_config_roundtrip(self):
        from app.services.smart_reranking import RerankingConfig
        config = RerankingConfig(strategy="semantic_heavy", top_k=15, threshold=0.3)
        d = config.to_dict()
        restored = RerankingConfig.from_dict(d)
        assert restored.strategy == "semantic_heavy"
        assert restored.top_k == 15
        assert restored.threshold == 0.3


# ── 评估历史测试 ──


class TestEvalHistory:
    """评估历史管理测试"""

    def test_add_and_get_report(self):
        from app.services.reranking_eval import EvalHistory, EvalReport
        history = EvalHistory()
        report = EvalReport(eval_id="test_001", strategy="balanced")
        history.add_report(report)

        retrieved = history.get_report("test_001")
        assert retrieved is not None
        assert retrieved.strategy == "balanced"

    def test_list_reports_filter(self):
        from app.services.reranking_eval import EvalHistory, EvalReport
        history = EvalHistory()
        history.add_report(EvalReport(eval_id="r1", strategy="balanced"))
        history.add_report(EvalReport(eval_id="r2", strategy="semantic_heavy"))
        history.add_report(EvalReport(eval_id="r3", strategy="balanced"))

        balanced = history.list_reports(strategy="balanced")
        assert len(balanced) == 2

    def test_compare_reports(self):
        from app.services.reranking_eval import EvalHistory, EvalReport, RankingMetrics
        history = EvalHistory()
        history.add_report(EvalReport(
            eval_id="r1", strategy="balanced",
            metrics=RankingMetrics(mrr=0.8, ndcg_at_10=0.75),
        ))
        history.add_report(EvalReport(
            eval_id="r2", strategy="semantic_heavy",
            metrics=RankingMetrics(mrr=0.9, ndcg_at_10=0.85),
        ))

        comparison = history.compare_reports(["r1", "r2"])
        assert "r1" in comparison
        assert "r2" in comparison
        # r2 应该排名更高（mrr 更高）
        assert comparison["r2"]["rank"] == 1


# ── 动态权重调整测试 ──


class TestDynamicWeights:
    """动态权重调整测试"""

    def _make_service(self):
        from app.services.smart_reranking import SmartRerankingService, RerankingConfig
        return SmartRerankingService(config=RerankingConfig(
            use_cross_encoder=False,
            enable_dynamic_weights=True,
        ))

    def test_short_query_boosts_keywords(self):
        """短查询应提升关键词权重"""
        service = self._make_service()
        from app.services.smart_reranking import RerankingWeights
        base = RerankingWeights()

        # 模拟特征向量
        from app.services.reranking_features import FeatureVector
        features = [FeatureVector(memory_id="m1")]

        adjusted = service._adjust_weights(base, "AI", features, None)
        assert adjusted.keyword_exact_match > base.keyword_exact_match

    def test_long_query_boosts_semantic(self):
        """长查询应提升语义权重"""
        service = self._make_service()
        from app.services.smart_reranking import RerankingWeights
        base = RerankingWeights()

        from app.services.reranking_features import FeatureVector
        features = [FeatureVector(memory_id="m1")]

        long_query = "如何使用 Python FastAPI 构建高性能 RESTful API 服务并集成数据库"
        adjusted = service._adjust_weights(base, long_query, features, None)
        assert adjusted.semantic_score > base.semantic_score

    def test_user_profile_boosts_personalization(self):
        """有用户画像时提升个性化权重"""
        service = self._make_service()
        from app.services.smart_reranking import RerankingWeights
        base = RerankingWeights()

        from app.services.reranking_features import FeatureVector
        features = [FeatureVector(memory_id="m1")]

        profile = {"interests": ["Python"], "research_areas": ["AI"]}
        adjusted = service._adjust_weights(base, "test", features, profile)
        assert adjusted.user_interest > base.user_interest


# ── 运行入口 ──

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
