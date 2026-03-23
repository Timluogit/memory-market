"""聚合器Agent - 结果聚合、重排、置信度计算

将多个搜索Agent的结果聚合、去重、重排并计算最终置信度
对应Supermemory ASMR的结果融合层
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.services.agent_base import (
    BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoredResult:
    """带分数的搜索结果"""
    item: Dict[str, Any]
    direct_score: float = 0.0
    context_score: float = 0.0
    timeline_score: float = 0.0
    fused_score: float = 0.0
    source_agents: List[str] = field(default_factory=list)
    dimension_coverage: int = 0


class AggregatorAgent(BaseAgent):
    """聚合器Agent

    职责：
    1. 聚合多个搜索Agent的结果
    2. 去重和合并
    3. 加权重排
    4. 计算最终置信度

    权重策略（类似Supermemory ASMR）：
    - 直接事实搜索：40%
    - 上下文搜索：35%
    - 时间线搜索：25%
    """

    # 可配置权重
    WEIGHT_DIRECT = 0.40
    WEIGHT_CONTEXT = 0.35
    WEIGHT_TIMELINE = 0.25

    def __init__(
        self,
        weight_direct: float = 0.40,
        weight_context: float = 0.35,
        weight_timeline: float = 0.25,
        **kwargs,
    ):
        kwargs.setdefault("role", AgentRole.AGGREGATOR)
        super().__init__(**kwargs)
        self.WEIGHT_DIRECT = weight_direct
        self.WEIGHT_CONTEXT = weight_context
        self.WEIGHT_TIMELINE = weight_timeline

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行结果聚合"""
        # 从context.search_results中获取各Agent结果
        direct_data = context.search_results.get("direct", {})
        context_data = context.search_results.get("context", {})
        timeline_data = context.search_results.get("timeline", {})

        direct_results = direct_data.get("results", [])
        context_results = context_data.get("results", [])
        timeline_results = timeline_data.get("results", [])

        # 1. 聚合和去重
        scored = self._merge_results(direct_results, context_results, timeline_results)

        # 2. 重排
        ranked = self._rerank(scored, context)

        # 3. 提取最终结果列表
        final_results = [r.item for r in ranked[:10]]

        # 4. 计算总体置信度
        overall_confidence = self._calc_overall_confidence(
            ranked, direct_data, context_data, timeline_data
        )

        # 5. 维度覆盖分析
        dimension_coverage = self._analyze_dimension_coverage(context)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "results": final_results,
                "total_merged": len(scored),
                "final_count": len(final_results),
                "dimension_coverage": dimension_coverage,
                "weights": {
                    "direct": self.WEIGHT_DIRECT,
                    "context": self.WEIGHT_CONTEXT,
                    "timeline": self.WEIGHT_TIMELINE,
                },
            },
            confidence=overall_confidence,
        )

    def _merge_results(
        self,
        direct: List[Dict],
        context: List[Dict],
        timeline: List[Dict],
    ) -> List[ScoredResult]:
        """合并去重"""
        merged: Dict[str, ScoredResult] = {}

        # 处理直接搜索结果
        for item in direct:
            key = self._make_key(item)
            if key not in merged:
                merged[key] = ScoredResult(item=item)
            sr = merged[key]
            sr.direct_score = max(sr.direct_score, item.get("relevance_score", 0))
            sr.source_agents.append("direct")

        # 处理上下文搜索结果
        for item in context:
            key = self._make_key(item)
            if key not in merged:
                merged[key] = ScoredResult(item=item)
            sr = merged[key]
            sr.context_score = max(sr.context_score, item.get("context_score", 0))
            if "context" not in sr.source_agents:
                sr.source_agents.append("context")

        # 处理时间线搜索结果
        for item in timeline:
            key = self._make_key(item)
            if key not in merged:
                merged[key] = ScoredResult(item=item)
            sr = merged[key]
            sr.timeline_score = max(sr.timeline_score, item.get("timeline_score", 0.5))
            if "timeline" not in sr.source_agents:
                sr.source_agents.append("timeline")

        # 计算维度覆盖
        for sr in merged.values():
            sr.dimension_coverage = len(sr.source_agents)

        return list(merged.values())

    def _rerank(
        self, scored: List[ScoredResult], context: AgentContext
    ) -> List[ScoredResult]:
        """加权重排"""
        for sr in scored:
            # 基础加权融合
            base_score = (
                sr.direct_score * self.WEIGHT_DIRECT
                + sr.context_score * self.WEIGHT_CONTEXT
                + sr.timeline_score * self.WEIGHT_TIMELINE
            )

            # 多Agent交叉验证加成（越多Agent确认，分数越高）
            cross_bonus = (sr.dimension_coverage - 1) * 0.1

            # 维度覆盖加成
            dim_bonus = 0.0
            item = sr.item
            if item.get("category"):
                dim_bonus += 0.05
            if item.get("tags"):
                dim_bonus += 0.05
            if item.get("avg_score"):
                dim_bonus += 0.05

            sr.fused_score = min(base_score + cross_bonus + dim_bonus, 2.0)

        # 按融合分数降序排列
        scored.sort(key=lambda x: x.fused_score, reverse=True)
        return scored

    def _make_key(self, item: Dict) -> str:
        """生成结果的唯一键"""
        # 优先使用memory_id
        if "memory_id" in item:
            return f"mem:{item['memory_id']}"
        # 使用source
        if "source" in item:
            return f"src:{item['source']}"
        # 使用标题hash
        title = item.get("title", "")
        return f"title:{hash(title)}"

    def _calc_overall_confidence(
        self,
        ranked: List[ScoredResult],
        direct_data: Dict,
        context_data: Dict,
        timeline_data: Dict,
    ) -> float:
        """计算总体置信度"""
        if not ranked:
            return 0.0

        # Agent置信度加权平均
        agent_confidences = []
        weights = []

        if direct_data:
            agent_confidences.append(direct_data.get("confidence", 0))
            weights.append(self.WEIGHT_DIRECT)
        if context_data:
            agent_confidences.append(context_data.get("confidence", 0))
            weights.append(self.WEIGHT_CONTEXT)
        if timeline_data:
            agent_confidences.append(timeline_data.get("confidence", 0))
            weights.append(self.WEIGHT_TIMELINE)

        if not agent_confidences:
            return 0.0

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        weighted_avg = sum(c * w for c, w in zip(agent_confidences, weights)) / total_weight

        # 结果数量加成
        count_bonus = min(len(ranked) * 0.05, 0.2)

        # 交叉验证加成
        cross_validated = sum(1 for r in ranked if r.dimension_coverage >= 2)
        cross_bonus = min(cross_validated * 0.05, 0.15)

        return min(weighted_avg + count_bonus + cross_bonus, 1.0)

    def _analyze_dimension_coverage(self, context: AgentContext) -> Dict[str, Any]:
        """分析维度覆盖情况"""
        dimensions = ("user_info", "preferences", "events", "temporal", "updates", "assistant")
        coverage = {}
        filled = 0

        for dim in dimensions:
            data = context.get_dimension(dim)
            has_data = bool(data)
            if has_data:
                filled += 1
            coverage[dim] = has_data

        return {
            "dimensions": coverage,
            "filled_count": filled,
            "total_count": len(dimensions),
            "coverage_ratio": filled / len(dimensions),
        }
