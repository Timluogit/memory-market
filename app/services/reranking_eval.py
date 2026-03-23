"""重排评估集成模块

集成评估框架，提供：
- MRR / NDCG / MAP / Precision / Recall 评估
- A/B 测试支持（对比不同策略）
- 评估报告生成
- 与现有 eval 框架对接
"""
from __future__ import annotations
import logging
import math
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import uuid

from app.services.smart_reranking import (
    SmartRerankingService,
    RerankingConfig,
    get_smart_reranking_service,
)

logger = logging.getLogger(__name__)


# ── 评估指标 ──

@dataclass
class RankingMetrics:
    """排序评估指标"""
    mrr: float = 0.0                # Mean Reciprocal Rank
    ndcg_at_5: float = 0.0          # NDCG@5
    ndcg_at_10: float = 0.0         # NDCG@10
    ndcg_at_20: float = 0.0         # NDCG@20
    precision_at_5: float = 0.0     # Precision@5
    precision_at_10: float = 0.0    # Precision@10
    map_score: float = 0.0          # Mean Average Precision
    recall_at_10: float = 0.0       # Recall@10
    hit_rate: float = 0.0           # 命中率（Top-K 中至少命中一个）
    num_queries: int = 0            # 评估的查询数

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def composite_score(self) -> float:
        """综合得分（加权平均）"""
        return (
            self.mrr * 0.25
            + self.ndcg_at_10 * 0.30
            + self.precision_at_10 * 0.20
            + self.map_score * 0.15
            + self.hit_rate * 0.10
        )


@dataclass
class QueryEvalResult:
    """单个查询的评估结果"""
    query: str
    expected_ids: List[str]
    ranked_ids: List[str]
    metrics: RankingMetrics
    latency_ms: float = 0.0
    candidate_count: int = 0


@dataclass
class EvalReport:
    """评估报告"""
    eval_id: str = field(default_factory=lambda: f"eval_{uuid.uuid4().hex[:8]}")
    strategy: str = "balanced"
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: RankingMetrics = field(default_factory=RankingMetrics)
    query_results: List[QueryEvalResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "strategy": self.strategy,
            "config": self.config,
            "metrics": self.metrics.to_dict(),
            "num_queries": len(self.query_results),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class RerankingEvaluator:
    """重排评估器

    对重排结果进行全面评估
    """

    def __init__(self, service: Optional[SmartRerankingService] = None):
        self.service = service or get_smart_reranking_service()

    async def evaluate(
        self,
        test_cases: List[Dict[str, Any]],
        strategy: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> EvalReport:
        """运行评估

        Args:
            test_cases: 测试用例列表，每项需包含:
                - query: str
                - candidates: List[Dict]
                - expected_ids: List[str]（正确的记忆ID，按相关性排序）
            strategy: 重排策略名称
            config_override: 配置覆盖
            user_profile: 用户画像

        Returns:
            EvalReport
        """
        strategy = strategy or self.service.config.strategy
        query_results: List[QueryEvalResult] = []

        for tc in test_cases:
            query = tc["query"]
            candidates = tc["candidates"]
            expected_ids = tc["expected_ids"]

            import time
            start = time.monotonic()

            # 运行重排
            reranked = await self.service.rerank(
                query=query,
                candidates=candidates,
                user_profile=user_profile,
                strategy=strategy,
            )

            elapsed_ms = (time.monotonic() - start) * 1000

            ranked_ids = [r.get("memory_id", "") for r in reranked]

            # 计算指标
            metrics = self._compute_metrics(ranked_ids, expected_ids)

            query_results.append(QueryEvalResult(
                query=query,
                expected_ids=expected_ids,
                ranked_ids=ranked_ids,
                metrics=metrics,
                latency_ms=elapsed_ms,
                candidate_count=len(candidates),
            ))

        # 聚合指标
        agg = self._aggregate_metrics([qr.metrics for qr in query_results])

        return EvalReport(
            strategy=strategy,
            config=config_override or self.service.config.to_dict(),
            metrics=agg,
            query_results=query_results,
            metadata={
                "total_latency_ms": sum(qr.latency_ms for qr in query_results),
                "avg_candidates": (
                    sum(qr.candidate_count for qr in query_results)
                    / max(len(query_results), 1)
                ),
            },
        )

    def _compute_metrics(
        self,
        ranked_ids: List[str],
        expected_ids: List[str],
    ) -> RankingMetrics:
        """计算单个查询的评估指标"""
        expected_set = set(expected_ids)

        mrr = self._mrr(ranked_ids, expected_set)
        ndcg5 = self._ndcg(ranked_ids, expected_ids, k=5)
        ndcg10 = self._ndcg(ranked_ids, expected_ids, k=10)
        ndcg20 = self._ndcg(ranked_ids, expected_ids, k=20)
        prec5 = self._precision_at_k(ranked_ids, expected_set, k=5)
        prec10 = self._precision_at_k(ranked_ids, expected_set, k=10)
        map_score = self._average_precision(ranked_ids, expected_set)
        recall10 = self._recall_at_k(ranked_ids, expected_set, k=10)
        hit_rate = 1.0 if any(rid in expected_set for rid in ranked_ids[:10]) else 0.0

        return RankingMetrics(
            mrr=mrr,
            ndcg_at_5=ndcg5,
            ndcg_at_10=ndcg10,
            ndcg_at_20=ndcg20,
            precision_at_5=prec5,
            precision_at_10=prec10,
            map_score=map_score,
            recall_at_10=recall10,
            hit_rate=hit_rate,
            num_queries=1,
        )

    def _aggregate_metrics(self, metrics_list: List[RankingMetrics]) -> RankingMetrics:
        """聚合多个查询的指标"""
        n = len(metrics_list)
        if n == 0:
            return RankingMetrics()

        def avg(field_name: str) -> float:
            return sum(getattr(m, field_name) for m in metrics_list) / n

        return RankingMetrics(
            mrr=avg("mrr"),
            ndcg_at_5=avg("ndcg_at_5"),
            ndcg_at_10=avg("ndcg_at_10"),
            ndcg_at_20=avg("ndcg_at_20"),
            precision_at_5=avg("precision_at_5"),
            precision_at_10=avg("precision_at_10"),
            map_score=avg("map_score"),
            recall_at_10=avg("recall_at_10"),
            hit_rate=avg("hit_rate"),
            num_queries=n,
        )

    @staticmethod
    def _mrr(ranked_ids: List[str], expected_set: set) -> float:
        """Mean Reciprocal Rank"""
        for i, rid in enumerate(ranked_ids):
            if rid in expected_set:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def _ndcg(ranked_ids: List[str], expected_ids: List[str], k: int = 10) -> float:
        """Normalized Discounted Cumulative Gain @K"""
        if not expected_ids:
            return 0.0

        # DCG
        dcg = 0.0
        for i in range(min(k, len(ranked_ids))):
            if ranked_ids[i] in expected_ids:
                # 如果有排序信息，可以用位置作为增益
                rank_in_expected = expected_ids.index(ranked_ids[i]) if ranked_ids[i] in expected_ids else 0
                gain = 1.0 / (1.0 + rank_in_expected) if ranked_ids[i] in expected_ids else 0.0
                dcg += gain / math.log2(i + 2)

        # IDCG
        idcg = 0.0
        for i in range(min(k, len(expected_ids))):
            idcg += 1.0 / (1.0 + i) / math.log2(i + 2)

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def _precision_at_k(ranked_ids: List[str], expected_set: set, k: int = 10) -> float:
        """Precision@K"""
        top_k = ranked_ids[:k]
        if not top_k:
            return 0.0
        return sum(1 for rid in top_k if rid in expected_set) / len(top_k)

    @staticmethod
    def _average_precision(ranked_ids: List[str], expected_set: set) -> float:
        """Average Precision"""
        if not expected_set:
            return 0.0

        hits = 0
        sum_precision = 0.0
        for i, rid in enumerate(ranked_ids):
            if rid in expected_set:
                hits += 1
                sum_precision += hits / (i + 1)

        return sum_precision / len(expected_set) if expected_set else 0.0

    @staticmethod
    def _recall_at_k(ranked_ids: List[str], expected_set: set, k: int = 10) -> float:
        """Recall@K"""
        if not expected_set:
            return 0.0
        top_k = ranked_ids[:k]
        return sum(1 for rid in top_k if rid in expected_set) / len(expected_set)


# ── A/B 测试 ──

@dataclass
class ABTestResult:
    """A/B 测试结果"""
    test_id: str = field(default_factory=lambda: f"ab_{uuid.uuid4().hex[:8]}")
    strategy_a: str = ""
    strategy_b: str = ""
    report_a: EvalReport = field(default_factory=EvalReport)
    report_b: EvalReport = field(default_factory=EvalReport)
    winner: str = ""  # "A" | "B" | "tie"
    improvement: float = 0.0  # B 相对 A 的提升百分比
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "strategy_a": self.strategy_a,
            "strategy_b": self.strategy_b,
            "report_a": self.report_a.to_dict(),
            "report_b": self.report_b.to_dict(),
            "winner": self.winner,
            "improvement_pct": round(self.improvement * 100, 2),
            "timestamp": self.timestamp,
        }


class ABTester:
    """A/B 测试器

    对比两个重排策略的效果
    """

    def __init__(self, service: Optional[SmartRerankingService] = None):
        self.evaluator_a = RerankingEvaluator(service)
        self.evaluator_b = RerankingEvaluator(service)

    async def run_test(
        self,
        test_cases: List[Dict[str, Any]],
        strategy_a: str = "balanced",
        strategy_b: str = "semantic_heavy",
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> ABTestResult:
        """运行 A/B 测试

        Args:
            test_cases: 测试用例
            strategy_a: 策略 A 名称
            strategy_b: 策略 B 名称
            user_profile: 用户画像

        Returns:
            ABTestResult
        """
        # 分别用两个策略运行评估
        report_a = await self.evaluator_a.evaluate(
            test_cases, strategy=strategy_a, user_profile=user_profile
        )
        report_b = await self.evaluator_b.evaluate(
            test_cases, strategy=strategy_b, user_profile=user_profile
        )

        # 比较
        score_a = report_a.metrics.composite_score
        score_b = report_b.metrics.composite_score
        improvement = (score_b - score_a) / max(score_a, 0.001)

        if improvement > 0.02:  # >2% 提升视为 B 胜出
            winner = "B"
        elif improvement < -0.02:
            winner = "A"
        else:
            winner = "tie"

        return ABTestResult(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            report_a=report_a,
            report_b=report_b,
            winner=winner,
            improvement=improvement,
        )


# ── 评估历史管理 ──

class EvalHistory:
    """评估历史管理

    保存和查询历史评估结果
    """

    def __init__(self):
        self._history: List[EvalReport] = []
        self._ab_tests: List[ABTestResult] = []

    def add_report(self, report: EvalReport):
        self._history.append(report)

    def add_ab_test(self, result: ABTestResult):
        self._ab_tests.append(result)

    def get_report(self, eval_id: str) -> Optional[EvalReport]:
        for r in self._history:
            if r.eval_id == eval_id:
                return r
        return None

    def list_reports(
        self,
        strategy: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        reports = self._history
        if strategy:
            reports = [r for r in reports if r.strategy == strategy]
        return [r.to_dict() for r in reports[-limit:]]

    def list_ab_tests(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._ab_tests[-limit:]]

    def compare_reports(self, eval_ids: List[str]) -> Dict[str, Any]:
        """对比多个评估结果"""
        reports = [self.get_report(eid) for eid in eval_ids]
        reports = [r for r in reports if r is not None]

        if len(reports) < 2:
            return {"error": "至少需要2个有效评估结果"}

        comparison = {}
        for r in reports:
            comparison[r.eval_id] = {
                "strategy": r.strategy,
                "metrics": r.metrics.to_dict(),
                "composite_score": r.metrics.composite_score,
                "timestamp": r.timestamp,
            }

        # 排名
        sorted_ids = sorted(
            comparison.keys(),
            key=lambda eid: comparison[eid]["composite_score"],
            reverse=True,
        )
        for rank, eid in enumerate(sorted_ids, 1):
            comparison[eid]["rank"] = rank

        return comparison


# 全局单例
_eval_history: Optional[EvalHistory] = None


def get_eval_history() -> EvalHistory:
    global _eval_history
    if _eval_history is None:
        _eval_history = EvalHistory()
    return _eval_history


def reset_eval_history():
    global _eval_history
    _eval_history = None
