"""智能重排序服务 - 多维度加权融合

对标 Supermemory 99% 准确率，实现：
1. 多维度评分（语义、关键词、时效性、相关性、质量）
2. 加权融合算法（可配置权重）
3. 动态权重调整（基于查询类型和用户画像自动调整）
4. Cross-Encoder 增强（语义深度理解）
5. 缓存优化（结果缓存 + 特征缓存）
"""
from __future__ import annotations
import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from app.services.reranking_features import (
    FeatureExtractor,
    FeatureVector,
    get_feature_extractor,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── 重排策略配置 ──

@dataclass
class RerankingWeights:
    """重排特征权重配置"""
    # 语义维度
    semantic_score: float = 0.30        # Cross-Encoder 语义分数
    embedding_similarity: float = 0.10  # 向量余弦相似度
    # 关键词维度
    keyword_exact_match: float = 0.08   # 精确关键词匹配
    keyword_bm25: float = 0.07          # BM25 风格得分
    keyword_title_match: float = 0.05   # 标题命中
    keyword_tag_match: float = 0.03     # 标签匹配
    # 时效性维度
    recency: float = 0.06               # 时效性
    freshness: float = 0.04             # 新鲜度
    # 用户偏好维度
    user_interest: float = 0.05         # 兴趣匹配
    user_history: float = 0.04          # 历史偏好
    user_category: float = 0.03         # 分类亲和度
    # 记忆质量维度
    quality_signal: float = 0.05        # 综合信号质量
    popularity: float = 0.04            # 购买热度
    rating: float = 0.03                # 评分
    verification: float = 0.03          # 验证强度

    def validate(self) -> bool:
        """验证权重和是否接近 1.0"""
        total = sum(asdict(self).values())
        return abs(total - 1.0) < 0.01

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "RerankingWeights":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# 预设策略
PRESET_STRATEGIES: Dict[str, RerankingWeights] = {
    "balanced": RerankingWeights(),
    "semantic_heavy": RerankingWeights(
        semantic_score=0.45,
        embedding_similarity=0.15,
        keyword_exact_match=0.05,
        keyword_bm25=0.05,
        keyword_title_match=0.03,
        keyword_tag_match=0.02,
        recency=0.05,
        freshness=0.03,
        user_interest=0.05,
        user_history=0.04,
        user_category=0.03,
        quality_signal=0.02,
        popularity=0.01,
        rating=0.01,
        verification=0.01,
    ),
    "keyword_heavy": RerankingWeights(
        semantic_score=0.15,
        embedding_similarity=0.05,
        keyword_exact_match=0.20,
        keyword_bm25=0.15,
        keyword_title_match=0.10,
        keyword_tag_match=0.08,
        recency=0.05,
        freshness=0.03,
        user_interest=0.04,
        user_history=0.03,
        user_category=0.02,
        quality_signal=0.04,
        popularity=0.03,
        rating=0.02,
        verification=0.01,
    ),
    "freshness_first": RerankingWeights(
        semantic_score=0.20,
        embedding_similarity=0.08,
        keyword_exact_match=0.07,
        keyword_bm25=0.06,
        keyword_title_match=0.04,
        keyword_tag_match=0.03,
        recency=0.15,
        freshness=0.12,
        user_interest=0.05,
        user_history=0.04,
        user_category=0.03,
        quality_signal=0.05,
        popularity=0.04,
        rating=0.02,
        verification=0.02,
    ),
    "quality_first": RerankingWeights(
        semantic_score=0.22,
        embedding_similarity=0.08,
        keyword_exact_match=0.06,
        keyword_bm25=0.05,
        keyword_title_match=0.04,
        keyword_tag_match=0.03,
        recency=0.05,
        freshness=0.03,
        user_interest=0.04,
        user_history=0.03,
        user_category=0.02,
        quality_signal=0.12,
        popularity=0.08,
        rating=0.08,
        verification=0.07,
    ),
    "personalized": RerankingWeights(
        semantic_score=0.20,
        embedding_similarity=0.08,
        keyword_exact_match=0.06,
        keyword_bm25=0.05,
        keyword_title_match=0.03,
        keyword_tag_match=0.02,
        recency=0.05,
        freshness=0.03,
        user_interest=0.12,
        user_history=0.10,
        user_category=0.08,
        quality_signal=0.06,
        popularity=0.05,
        rating=0.04,
        verification=0.03,
    ),
}


@dataclass
class RerankingConfig:
    """完整重排配置"""
    strategy: str = "balanced"                  # 策略名称
    weights: RerankingWeights = field(default_factory=RerankingWeights)
    use_cross_encoder: bool = True              # 是否使用 Cross-Encoder
    cross_encoder_weight: float = 0.70          # Cross-Encoder 分数权重（在融合中）
    enable_dynamic_weights: bool = True         # 动态权重调整
    enable_caching: bool = True                 # 结果缓存
    cache_ttl: int = 3600                       # 缓存 TTL（秒）
    top_k: int = 20                             # 最终返回 Top-K
    threshold: float = 0.0                      # 最低分数阈值
    min_candidates_for_rerank: int = 5          # 少于此数量不重排

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "weights": self.weights.to_dict(),
            "use_cross_encoder": self.use_cross_encoder,
            "cross_encoder_weight": self.cross_encoder_weight,
            "enable_dynamic_weights": self.enable_dynamic_weights,
            "enable_caching": self.enable_caching,
            "cache_ttl": self.cache_ttl,
            "top_k": self.top_k,
            "threshold": self.threshold,
            "min_candidates_for_rerank": self.min_candidates_for_rerank,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RerankingConfig":
        weights = d.get("weights", {})
        if isinstance(weights, dict):
            weights = RerankingWeights.from_dict(weights)
        return cls(
            strategy=d.get("strategy", "balanced"),
            weights=weights,
            use_cross_encoder=d.get("use_cross_encoder", True),
            cross_encoder_weight=d.get("cross_encoder_weight", 0.70),
            enable_dynamic_weights=d.get("enable_dynamic_weights", True),
            enable_caching=d.get("enable_caching", True),
            cache_ttl=d.get("cache_ttl", 3600),
            top_k=d.get("top_k", 20),
            threshold=d.get("threshold", 0.0),
            min_candidates_for_rerank=d.get("min_candidates_for_rerank", 5),
        )


class SmartRerankingService:
    """智能重排序服务

    多维度加权融合 + Cross-Encoder 增强 + 动态权重调整
    """

    def __init__(self, config: Optional[RerankingConfig] = None):
        self.config = config or RerankingConfig()
        self.feature_extractor = get_feature_extractor()
        self._cross_encoder = None
        self._redis = None

        # 统计
        self._stats = {
            "total_reranks": 0,
            "cache_hits": 0,
            "cross_encoder_calls": 0,
            "avg_candidates": 0.0,
            "avg_latency_ms": 0.0,
        }

    @property
    def cross_encoder(self):
        """延迟加载 Cross-Encoder"""
        if self._cross_encoder is None and self.config.use_cross_encoder:
            try:
                from sentence_transformers import CrossEncoder
                from app.services.model_manager import get_model_manager
                manager = get_model_manager()
                self._cross_encoder = manager.get_cross_encoder(
                    getattr(settings, "RERANK_MODEL", "BAAI/bge-reranker-large")
                )
                logger.info("Cross-Encoder loaded for smart reranking")
            except Exception as e:
                logger.warning(f"Cross-Encoder load failed: {e}")
                self._cross_encoder = None
        return self._cross_encoder

    @property
    def redis(self):
        """延迟加载 Redis"""
        if self._redis is None:
            try:
                from app.cache.redis_client import get_redis_client
                self._redis = get_redis_client()
            except Exception:
                self._redis = None
        return self._redis

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        strategy: Optional[str] = None,
        override_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """智能重排主入口

        Args:
            query: 搜索查询
            candidates: 候选列表（每个 dict 需包含 memory_id, title, summary 等）
            user_profile: 用户画像（可选）
            top_k: 返回数量（覆盖配置）
            strategy: 策略名称（覆盖配置）
            override_weights: 权重覆盖（覆盖配置）

        Returns:
            重排后的候选列表（按 final_score 降序）
        """
        import time
        start_time = time.monotonic()

        top_k = top_k or self.config.top_k
        strategy = strategy or self.config.strategy

        if not candidates:
            return []

        # 候选太少，跳过重排
        if len(candidates) < self.config.min_candidates_for_rerank:
            logger.debug(f"Too few candidates ({len(candidates)}), skipping rerank")
            return candidates[:top_k]

        # 确定权重
        weights = self._resolve_weights(strategy, override_weights)

        # 检查缓存
        cache_key = self._make_cache_key(query, candidates, weights, top_k)
        if self.config.enable_caching:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                self._stats["cache_hits"] += 1
                logger.debug("Smart rerank cache hit")
                return cached

        # ── Step 1: Cross-Encoder 语义评分 ──
        semantic_scores = await self._cross_encoder_score(query, candidates)

        # ── Step 2: 向量相似度（从候选中提取） ──
        embedding_sims = [
            float(c.get("embedding_similarity", c.get("score", 0.0)) or 0.0)
            for c in candidates
        ]

        # ── Step 3: 特征提取 ──
        feature_vectors = self.feature_extractor.extract_batch(
            query=query,
            candidates=candidates,
            semantic_scores=semantic_scores,
            embedding_similarities=embedding_sims,
            user_profile=user_profile,
        )

        # ── Step 4: 动态权重调整 ──
        if self.config.enable_dynamic_weights:
            weights = self._adjust_weights(weights, query, feature_vectors, user_profile)

        # ── Step 5: 加权融合 ──
        for fv in feature_vectors:
            fv.final_score = self._weighted_fusion(fv, weights)

        # ── Step 6: 排序 + 截断 ──
        feature_vectors.sort(key=lambda fv: fv.final_score, reverse=True)

        # 阈值过滤
        if self.config.threshold > 0:
            feature_vectors = [
                fv for fv in feature_vectors
                if fv.final_score >= self.config.threshold
            ]

        # Top-K
        top_vectors = feature_vectors[:top_k]

        # ── Step 7: 组装结果 ──
        results = []
        for fv in top_vectors:
            item = fv.raw_data.copy()
            item["final_score"] = round(fv.final_score, 6)
            item["semantic_score"] = round(fv.semantic_score, 6)
            item["keyword_score"] = round(fv.keyword_exact_match, 4)
            item["recency_score"] = round(fv.recency_score, 4)
            item["quality_score"] = round(fv.quality_signal, 4)
            item["feature_vector"] = {
                "semantic": fv.semantic_score,
                "embedding_sim": fv.embedding_similarity,
                "kw_exact": fv.keyword_exact_match,
                "kw_bm25": fv.keyword_bm25_score,
                "kw_title": fv.keyword_title_match,
                "kw_tag": fv.keyword_tag_match,
                "recency": fv.recency_score,
                "freshness": fv.freshness_score,
                "user_interest": fv.user_interest_match,
                "user_history": fv.user_history_match,
                "user_category": fv.user_category_affinity,
                "quality": fv.quality_signal,
                "popularity": fv.purchase_popularity,
                "rating": fv.rating_score,
                "verification": fv.verification_strength,
            }
            results.append(item)

        # 缓存
        if self.config.enable_caching:
            await self._set_cache(cache_key, results)

        # 统计
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self._update_stats(len(candidates), elapsed_ms)

        logger.info(
            f"Smart rerank: {len(candidates)} -> {len(results)} candidates "
            f"({elapsed_ms:.1f}ms, strategy={strategy})"
        )
        return results

    # ── 加权融合 ──

    def _weighted_fusion(self, fv: FeatureVector, w: RerankingWeights) -> float:
        """加权融合计算最终分数"""
        score = (
            w.semantic_score * fv.semantic_score
            + w.embedding_similarity * fv.embedding_similarity
            + w.keyword_exact_match * fv.keyword_exact_match
            + w.keyword_bm25 * fv.keyword_bm25_score
            + w.keyword_title_match * fv.keyword_title_match
            + w.keyword_tag_match * fv.keyword_tag_match
            + w.recency * fv.recency_score
            + w.freshness * fv.freshness_score
            + w.user_interest * fv.user_interest_match
            + w.user_history * fv.user_history_match
            + w.user_category * fv.user_category_affinity
            + w.quality_signal * fv.quality_signal
            + w.popularity * fv.purchase_popularity
            + w.rating * fv.rating_score
            + w.verification * fv.verification_strength
        )
        return max(0.0, min(score, 1.0))

    # ── 动态权重调整 ──

    def _adjust_weights(
        self,
        base_weights: RerankingWeights,
        query: str,
        features: List[FeatureVector],
        user_profile: Optional[Dict[str, Any]],
    ) -> RerankingWeights:
        """基于查询特征和候选分布动态调整权重

        规则:
        1. 短查询（≤3词）→ 提高关键词权重
        2. 长查询（>10词）→ 提高语义权重
        3. 有用户画像 → 提高个性化权重
        4. 候选多样性低 → 提高质量权重
        """
        import copy
        w = copy.deepcopy(base_weights)

        query_terms = self.feature_extractor._tokenize(query)
        n_terms = len(query_terms)

        # 短查询：提升关键词权重
        if n_terms <= 3:
            boost = 0.05
            w.keyword_exact_match += boost * 0.4
            w.keyword_bm25 += boost * 0.3
            w.keyword_title_match += boost * 0.2
            w.keyword_tag_match += boost * 0.1
            w.semantic_score -= boost * 0.5
            w.embedding_similarity -= boost * 0.5

        # 长查询：提升语义权重
        elif n_terms > 10:
            boost = 0.08
            w.semantic_score += boost * 0.6
            w.embedding_similarity += boost * 0.4
            w.keyword_exact_match -= boost * 0.4
            w.keyword_bm25 -= boost * 0.3
            w.keyword_title_match -= boost * 0.2
            w.keyword_tag_match -= boost * 0.1

        # 有用户画像 → 提升个性化权重
        if user_profile:
            has_interests = bool(
                user_profile.get("interests")
                or user_profile.get("research_areas")
                or user_profile.get("tech_stack")
            )
            if has_interests:
                boost = 0.04
                w.user_interest += boost * 0.5
                w.user_history += boost * 0.3
                w.user_category += boost * 0.2
                # 从质量维度扣减
                w.quality_signal -= boost * 0.4
                w.popularity -= boost * 0.3
                w.rating -= boost * 0.2
                w.verification -= boost * 0.1

        # 候选多样性低（分数集中）→ 提高质量权重来区分
        if features:
            scores = [fv.semantic_score for fv in features]
            if len(scores) > 1:
                import statistics
                std = statistics.stdev(scores) if len(scores) > 1 else 0
                if std < 0.1:  # 分数非常集中
                    boost = 0.03
                    w.quality_signal += boost * 0.5
                    w.popularity += boost * 0.3
                    w.rating += boost * 0.2
                    w.semantic_score -= boost

        # 归一化：确保权重和为 1.0
        total = sum(w.to_dict().values())
        if total > 0:
            factor = 1.0 / total
            for attr in w.to_dict():
                setattr(w, attr, getattr(w, attr) * factor)

        return w

    # ── Cross-Encoder 评分 ──

    async def _cross_encoder_score(
        self, query: str, candidates: List[Dict]
    ) -> List[float]:
        """使用 Cross-Encoder 对每个候选进行语义评分"""
        encoder = self.cross_encoder
        if encoder is None:
            return [0.0] * len(candidates)

        try:
            pairs = []
            for c in candidates:
                text = c.get("content_text") or c.get("content") or c.get("summary", "")
                if isinstance(text, dict):
                    text = json.dumps(text, ensure_ascii=False)
                elif not isinstance(text, str):
                    text = str(text)
                pairs.append([query, text[:512]])  # 截断以避免超长

            scores = encoder.predict(pairs, show_progress_bar=False)
            self._stats["cross_encoder_calls"] += 1
            # 归一化到 0-1（Cross-Encoder 输出可能是任意范围）
            min_s, max_s = float(min(scores)), float(max(scores))
            if max_s - min_s > 0:
                return [(float(s) - min_s) / (max_s - min_s) for s in scores]
            else:
                return [0.5] * len(scores)
        except Exception as e:
            logger.warning(f"Cross-Encoder scoring failed: {e}")
            return [0.0] * len(candidates)

    # ── 权重解析 ──

    def _resolve_weights(
        self,
        strategy: str,
        override: Optional[Dict[str, float]] = None,
    ) -> RerankingWeights:
        """解析权重：优先级 override > preset > config"""
        if override:
            return RerankingWeights.from_dict(override)
        if strategy in PRESET_STRATEGIES:
            return PRESET_STRATEGIES[strategy]
        return self.config.weights

    # ── 缓存 ──

    def _make_cache_key(
        self,
        query: str,
        candidates: List[Dict],
        weights: RerankingWeights,
        top_k: int,
    ) -> str:
        ids = sorted(c.get("memory_id", "") for c in candidates)
        content = f"{query}:{','.join(ids)}:{weights.to_dict()}:{top_k}"
        return f"smart_rerank:{hashlib.md5(content.encode()).hexdigest()}"

    async def _get_cache(self, key: str) -> Optional[List[Dict]]:
        if self.redis is None:
            return None
        try:
            raw = await self.redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, data: List[Dict]):
        if self.redis is None:
            return
        try:
            await self.redis.setex(
                key,
                self.config.cache_ttl,
                json.dumps(data, ensure_ascii=False),
            )
        except Exception:
            pass

    # ── 统计 ──

    def _update_stats(self, n_candidates: int, elapsed_ms: float):
        n = self._stats["total_reranks"]
        self._stats["total_reranks"] = n + 1
        self._stats["avg_candidates"] = (
            (self._stats["avg_candidates"] * n + n_candidates) / (n + 1)
        )
        self._stats["avg_latency_ms"] = (
            (self._stats["avg_latency_ms"] * n + elapsed_ms) / (n + 1)
        )

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    def update_config(self, config: RerankingConfig):
        """热更新配置"""
        self.config = config
        logger.info(f"Smart reranking config updated: strategy={config.strategy}")


# ── 全局单例 ──
_service: Optional[SmartRerankingService] = None


def get_smart_reranking_service(
    config: Optional[RerankingConfig] = None,
) -> SmartRerankingService:
    """获取智能重排服务单例"""
    global _service
    if _service is None:
        _service = SmartRerankingService(config=config)
    return _service


def reset_smart_reranking_service():
    """重置（用于测试）"""
    global _service
    _service = None
