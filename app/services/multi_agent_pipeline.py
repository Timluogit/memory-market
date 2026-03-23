"""多Agent并行推理流水线

编排观察者Agent和搜索Agent的并行执行，以及聚合器的结果融合
参考Supermemory ASMR架构：
  Phase 1: 3个观察者Agent并行读取原始数据
  Phase 2: 3个搜索Agent并行搜索
  Phase 3: 聚合器融合结果
"""
from __future__ import annotations

import time
import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_base import (
    BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus,
    get_agent_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """流水线执行结果"""
    session_id: str
    query: str
    status: str  # "completed", "partial", "failed"
    results: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    total_time_ms: float = 0.0

    # 各阶段详情
    observer_results: Dict[str, AgentResult] = field(default_factory=dict)
    searcher_results: Dict[str, AgentResult] = field(default_factory=dict)
    aggregator_result: Optional[AgentResult] = None

    # 性能指标
    observer_time_ms: float = 0.0
    searcher_time_ms: float = 0.0
    aggregator_time_ms: float = 0.0

    # 维度覆盖
    dimension_coverage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "session_id": self.session_id,
            "query": self.query,
            "status": self.status,
            "results": self.results,
            "confidence": self.confidence,
            "total_time_ms": self.total_time_ms,
            "observer_time_ms": self.observer_time_ms,
            "searcher_time_ms": self.searcher_time_ms,
            "aggregator_time_ms": self.aggregator_time_ms,
            "dimension_coverage": self.dimension_coverage,
        }


class MultiAgentPipeline:
    """多Agent并行推理流水线

    三阶段执行：
    1. 观察阶段：3个观察者Agent并行提取6大维度
    2. 搜索阶段：3个搜索Agent并行搜索
    3. 聚合阶段：聚合器融合和重排
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        observer_timeout: float = 15.0,
        searcher_timeout: float = 20.0,
        aggregator_timeout: float = 10.0,
        max_retries: int = 1,
    ):
        self.db = db
        self.observer_timeout = observer_timeout
        self.searcher_timeout = searcher_timeout
        self.aggregator_timeout = aggregator_timeout
        self.max_retries = max_retries
        self.manager = get_agent_manager()

    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        observations: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """运行完整流水线

        Args:
            query: 搜索查询
            user_id: 用户ID
            raw_data: 原始数据
            observations: 预置观察数据

        Returns:
            PipelineResult
        """
        start_time = time.monotonic()

        # 创建上下文
        context = AgentContext(
            query=query,
            user_id=user_id,
            raw_data=raw_data or {},
            observations=observations or {},
        )

        result = PipelineResult(
            session_id=context.session_id,
            query=query,
            status="running",
        )

        try:
            # Phase 1: 观察者Agent并行
            logger.info(f"[Pipeline] Phase 1: Observers starting for session {context.session_id}")
            obs_start = time.monotonic()
            observer_results = await self._run_observers(context)
            result.observer_time_ms = (time.monotonic() - obs_start) * 1000
            result.observer_results = observer_results
            logger.info(
                f"[Pipeline] Phase 1 done: {len(observer_results)} observers, "
                f"{result.observer_time_ms:.0f}ms"
            )

            # Phase 2: 搜索Agent并行
            logger.info(f"[Pipeline] Phase 2: Searchers starting")
            srch_start = time.monotonic()
            searcher_results = await self._run_searchers(context)
            result.searcher_time_ms = (time.monotonic() - srch_start) * 1000
            result.searcher_results = searcher_results
            logger.info(
                f"[Pipeline] Phase 2 done: {len(searcher_results)} searchers, "
                f"{result.searcher_time_ms:.0f}ms"
            )

            # 将搜索结果存入context
            for role_key, sr in searcher_results.items():
                if sr.is_success:
                    context.search_results[role_key] = sr.data

            # Phase 3: 聚合
            logger.info(f"[Pipeline] Phase 3: Aggregator starting")
            agg_start = time.monotonic()
            agg_result = await self._run_aggregator(context)
            result.aggregator_time_ms = (time.monotonic() - agg_start) * 1000
            result.aggregator_result = agg_result
            logger.info(
                f"[Pipeline] Phase 3 done: confidence={agg_result.confidence:.2f}, "
                f"{result.aggregator_time_ms:.0f}ms"
            )

            # 提取最终结果
            if agg_result.is_success:
                result.results = agg_result.data.get("results", [])
                result.confidence = agg_result.confidence
                result.dimension_coverage = agg_result.data.get("dimension_coverage", {})
                result.status = "completed"
            else:
                result.status = "partial"
                # 降级：使用最佳搜索Agent的结果
                result.results = self._fallback_results(searcher_results)
                result.confidence = 0.3

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            result.status = "failed"
            result.results = []

        result.total_time_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            f"[Pipeline] Complete: status={result.status}, "
            f"results={len(result.results)}, "
            f"confidence={result.confidence:.2f}, "
            f"total={result.total_time_ms:.0f}ms"
        )
        return result

    async def _run_observers(self, context: AgentContext) -> Dict[str, AgentResult]:
        """并行运行观察者Agent"""
        observer_roles = [
            AgentRole.OBSERVER_USER_INFO,
            AgentRole.OBSERVER_TEMPORAL,
            AgentRole.OBSERVER_GENERAL,
        ]

        agents = []
        for role in observer_roles:
            agent = self.manager.create(role, timeout_seconds=self.observer_timeout)
            agents.append(agent)

        # 并行执行
        tasks = [agent.run(context) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        output = {}
        for agent, res in zip(agents, results):
            if isinstance(res, Exception):
                logger.error(f"Observer {agent.agent_id} exception: {res}")
                output[agent.role.value] = AgentResult(
                    agent_id=agent.agent_id,
                    role=agent.role,
                    status=AgentStatus.FAILED,
                    error=str(res),
                )
            else:
                output[agent.role.value] = res

        return output

    async def _run_searchers(self, context: AgentContext) -> Dict[str, AgentResult]:
        """并行运行搜索Agent"""
        searcher_roles = [
            AgentRole.SEARCHER_DIRECT,
            AgentRole.SEARCHER_CONTEXT,
            AgentRole.SEARCHER_TIMELINE,
        ]

        agents = []
        for role in searcher_roles:
            agent = self.manager.create(
                role, db=self.db, timeout_seconds=self.searcher_timeout
            )
            agents.append(agent)

        # 并行执行
        tasks = [agent.run(context) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        output = {}
        role_keys = {
            AgentRole.SEARCHER_DIRECT: "direct",
            AgentRole.SEARCHER_CONTEXT: "context",
            AgentRole.SEARCHER_TIMELINE: "timeline",
        }
        for agent, res in zip(agents, results):
            key = role_keys.get(agent.role, agent.role.value)
            if isinstance(res, Exception):
                logger.error(f"Searcher {agent.agent_id} exception: {res}")
                output[key] = AgentResult(
                    agent_id=agent.agent_id,
                    role=agent.role,
                    status=AgentStatus.FAILED,
                    error=str(res),
                )
            else:
                output[key] = res

        return output

    async def _run_aggregator(self, context: AgentContext) -> AgentResult:
        """运行聚合器"""
        agent = self.manager.create(
            AgentRole.AGGREGATOR, timeout_seconds=self.aggregator_timeout
        )
        return await agent.run(context)

    def _fallback_results(
        self, searcher_results: Dict[str, AgentResult]
    ) -> List[Dict[str, Any]]:
        """降级策略：返回最佳搜索Agent的结果"""
        best_score = -1
        best_results = []

        for key, sr in searcher_results.items():
            if sr.is_success and sr.data.get("results"):
                score = sr.confidence * len(sr.data["results"])
                if score > best_score:
                    best_score = score
                    best_results = sr.data["results"]

        return best_results


# 便捷函数
async def run_multi_agent_search(
    query: str,
    db: Optional[AsyncSession] = None,
    user_id: Optional[str] = None,
    raw_data: Optional[Dict[str, Any]] = None,
    observations: Optional[Dict[str, Any]] = None,
) -> PipelineResult:
    """运行多Agent搜索（便捷入口）

    Args:
        query: 搜索查询
        db: 数据库会话
        user_id: 用户ID
        raw_data: 原始数据
        observations: 预置观察数据

    Returns:
        PipelineResult
    """
    pipeline = MultiAgentPipeline(db=db)
    return await pipeline.run(
        query=query,
        user_id=user_id,
        raw_data=raw_data,
        observations=observations,
    )
