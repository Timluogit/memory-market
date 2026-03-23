"""评估指标 - Memory Quality Evaluation Metrics

支持标准信息检索指标:
- Accuracy: 准确率
- Precision: 精确率
- Recall: 召回率
- F1: F1分数
- MRR: Mean Reciprocal Rank
- NDCG: Normalized Discounted Cumulative Gain
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
import math


@dataclass
class MetricResult:
    """单个指标结果"""
    name: str
    value: float
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 6),
            "description": self.description,
            "details": self.details,
        }


class EvaluationMetrics:
    """评估指标计算类"""

    @staticmethod
    def accuracy(predicted: Set[str], expected: Set[str]) -> MetricResult:
        """准确率 = (TP + TN) / (TP + TN + FP + FN)

        对于检索任务: |predicted ∩ expected| / |predicted ∪ expected|
        """
        if not predicted and not expected:
            return MetricResult("accuracy", 1.0, "准确率")

        intersection = predicted & expected
        union = predicted | expected
        value = len(intersection) / len(union) if union else 0.0

        return MetricResult(
            "accuracy", value, "准确率 (Jaccard Index)",
            {"tp": len(intersection), "total": len(union)}
        )

    @staticmethod
    def precision(predicted: Set[str], expected: Set[str]) -> MetricResult:
        """精确率 = TP / (TP + FP) = |predicted ∩ expected| / |predicted|"""
        if not predicted:
            return MetricResult("precision", 0.0, "精确率 (空预测)")

        intersection = predicted & expected
        value = len(intersection) / len(predicted)

        return MetricResult(
            "precision", value, "精确率",
            {"tp": len(intersection), "predicted_total": len(predicted)}
        )

    @staticmethod
    def recall(predicted: Set[str], expected: Set[str]) -> MetricResult:
        """召回率 = TP / (TP + FN) = |predicted ∩ expected| / |expected|"""
        if not expected:
            return MetricResult("recall", 1.0, "召回率 (空期望)")

        intersection = predicted & expected
        value = len(intersection) / len(expected)

        return MetricResult(
            "recall", value, "召回率",
            {"tp": len(intersection), "expected_total": len(expected)}
        )

    @staticmethod
    def f1_score(predicted: Set[str], expected: Set[str]) -> MetricResult:
        """F1分数 = 2 * Precision * Recall / (Precision + Recall)"""
        p_result = EvaluationMetrics.precision(predicted, expected)
        r_result = EvaluationMetrics.recall(predicted, expected)
        p = p_result.value
        r = r_result.value

        if p + r == 0:
            return MetricResult("f1", 0.0, "F1分数")

        f1 = 2 * p * r / (p + r)
        return MetricResult(
            "f1", f1, "F1分数",
            {"precision": p, "recall": r}
        )

    @staticmethod
    def mrr(predicted_ranked: List[str], expected: Set[str], k: Optional[int] = None) -> MetricResult:
        """MRR (Mean Reciprocal Rank)

        计算第一个正确结果的排名的倒数。
        Args:
            predicted_ranked: 排序后的预测结果列表
            expected: 期望的正确结果集合
            k: 仅考虑前k个结果 (可选)
        """
        if not predicted_ranked or not expected:
            return MetricResult("mrr", 0.0, "MRR")

        results = predicted_ranked[:k] if k else predicted_ranked
        for rank, item in enumerate(results, start=1):
            if item in expected:
                return MetricResult(
                    "mrr", 1.0 / rank, "Mean Reciprocal Rank",
                    {"first_relevant_rank": rank}
                )

        return MetricResult("mrr", 0.0, "MRR", {"first_relevant_rank": None})

    @staticmethod
    def ndcg(predicted_ranked: List[str], expected: Set[str], k: Optional[int] = None) -> MetricResult:
        """NDCG (Normalized Discounted Cumulative Gain)

        NDCG@k = DCG@k / IDCG@k
        DCG@k = Σ(rel_i / log2(i+1)) for i=1..k
        """
        if not predicted_ranked or not expected:
            return MetricResult("ndcg", 0.0, "NDCG")

        results = predicted_ranked[:k] if k else predicted_ranked

        # DCG: Discounted Cumulative Gain
        dcg = 0.0
        for rank, item in enumerate(results, start=1):
            relevance = 1.0 if item in expected else 0.0
            dcg += relevance / math.log2(rank + 1)

        # IDCG: Ideal DCG (all relevant items at top)
        n_relevant = sum(1 for item in results if item in expected)
        n_ideal = min(n_relevant, len(expected))
        idcg = 0.0
        for i in range(1, n_ideal + 1):
            idcg += 1.0 / math.log2(i + 1)

        ndcg_value = dcg / idcg if idcg > 0 else 0.0
        k_label = f"@{k}" if k else ""

        return MetricResult(
            "ndcg", ndcg_value, f"NDCG{k_label}",
            {"dcg": round(dcg, 6), "idcg": round(idcg, 6), "k": k}
        )

    @classmethod
    def evaluate_retrieval(
        cls,
        predicted_ranked: List[str],
        expected: Set[str],
        k: Optional[int] = None,
    ) -> Dict[str, MetricResult]:
        """一次性计算所有检索指标"""
        predicted_set = set(predicted_ranked[:k] if k else predicted_ranked)

        results = {
            "accuracy": cls.accuracy(predicted_set, expected),
            "precision": cls.precision(predicted_set, expected),
            "recall": cls.recall(predicted_set, expected),
            "f1": cls.f1_score(predicted_set, expected),
            "mrr": cls.mrr(predicted_ranked, expected, k),
            "ndcg": cls.ndcg(predicted_ranked, expected, k),
        }
        return results

    @staticmethod
    def aggregate_results(metric_list: List[MetricResult]) -> MetricResult:
        """聚合多个同名指标结果（取平均值）"""
        if not metric_list:
            return MetricResult("aggregated", 0.0, "聚合指标")

        name = metric_list[0].name
        avg_value = sum(m.value for m in metric_list) / len(metric_list)

        return MetricResult(
            name, avg_value, f"平均 {metric_list[0].description}",
            {"count": len(metric_list), "min": min(m.value for m in metric_list),
             "max": max(m.value for m in metric_list)}
        )
