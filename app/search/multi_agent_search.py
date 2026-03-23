"""多Agent搜索集成层

提供对外统一搜索入口，集成多Agent并行推理与单Agent降级策略
"""
from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.multi_agent_pipeline import MultiAgentPipeline, PipelineResult, run_multi_agent_search
from app.services.agent_base import AgentContext, AgentStatus
from app.models.schemas import MemoryList, MemoryResponse

logger = logging.getLogger(__name__)


class MultiAgentSearchEngine:
    """多Agent搜索引擎

    对外提供统一的搜索接口，内部使用多Agent并行推理
    支持降级策略：多Agent失败时回退到单Agent搜索
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        enable_multi_agent: bool = True,
        fallback_to_hybrid: bool = True,
        min_confidence: float = 0.2,
    ):
        self.db = db
        self.enable_multi_agent = enable_multi_agent
        self.fallback_to_hybrid = fallback_to_hybrid
        self.min_confidence = min_confidence
        self._pipeline: Optional[MultiAgentPipeline] = None

    def _get_pipeline(self) -> MultiAgentPipeline:
        """获取流水线实例"""
        if self._pipeline is None:
            self._pipeline = MultiAgentPipeline(db=self.db)
        return self._pipeline

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "relevance",
    ) -> Dict[str, Any]:
        """多Agent搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            raw_data: 原始数据
            page: 页码
            page_size: 每页数量
            sort_by: 排序方式

        Returns:
            搜索结果字典
        """
        start_time = time.monotonic()

        if self.enable_multi_agent:
            try:
                pipeline_result = await self._multi_agent_search(
                    query, user_id, raw_data
                )

                # 检查结果质量
                if pipeline_result.confidence >= self.min_confidence:
                    return self._format_result(pipeline_result, page, page_size, start_time)

                # 置信度不足，尝试降级
                logger.info(
                    f"Multi-agent confidence {pipeline_result.confidence:.2f} "
                    f"< threshold {self.min_confidence}, trying fallback"
                )

            except Exception as e:
                logger.error(f"Multi-agent search failed: {e}", exc_info=True)

        # 降级到单Agent搜索
        if self.fallback_to_hybrid:
            return await self._fallback_search(query, user_id, page, page_size, start_time)

        return {
            "results": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "confidence": 0.0,
            "search_type": "multi_agent_failed",
            "time_ms": (time.monotonic() - start_time) * 1000,
        }

    async def _multi_agent_search(
        self,
        query: str,
        user_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """执行多Agent搜索"""
        pipeline = self._get_pipeline()
        return await pipeline.run(
            query=query,
            user_id=user_id,
            raw_data=raw_data,
        )

    async def _fallback_search(
        self,
        query: str,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        start_time: float = 0.0,
    ) -> Dict[str, Any]:
        """降级搜索：使用混合搜索引擎"""
        try:
            from app.search.hybrid_search import get_hybrid_engine
            from app.models.tables import Memory
            from sqlalchemy import select, and_

            engine = get_hybrid_engine()

            # 构建基础查询
            stmt = select(Memory).where(Memory.is_active == True)

            results = await engine.search(
                db=self.db,
                query=query,
                base_stmt=stmt,
                search_type="hybrid",
                page=page,
                page_size=page_size,
                sort_by="relevance",
            )

            # 转换为字典格式
            items = []
            if hasattr(results, "items"):
                for item in results.items:
                    if hasattr(item, "__dict__"):
                        items.append({
                            "memory_id": getattr(item, "memory_id", ""),
                            "title": getattr(item, "title", ""),
                            "summary": getattr(item, "summary", ""),
                            "category": getattr(item, "category", ""),
                            "tags": getattr(item, "tags", []),
                            "price": getattr(item, "price", 0),
                            "relevance_score": getattr(item, "final_score", 0.5),
                            "source": "hybrid_fallback",
                        })

            return {
                "results": items,
                "total": getattr(results, "total", len(items)),
                "page": page,
                "page_size": page_size,
                "confidence": 0.5,
                "search_type": "hybrid_fallback",
                "time_ms": (time.monotonic() - start_time) * 1000,
            }

        except Exception as e:
            logger.error(f"Fallback search also failed: {e}", exc_info=True)
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "confidence": 0.0,
                "search_type": "all_failed",
                "time_ms": (time.monotonic() - start_time) * 1000,
            }

    def _format_result(
        self,
        pipeline_result: PipelineResult,
        page: int,
        page_size: int,
        start_time: float,
    ) -> Dict[str, Any]:
        """格式化流水线结果"""
        all_results = pipeline_result.results

        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged = all_results[start_idx:end_idx]

        return {
            "results": paged,
            "total": len(all_results),
            "page": page,
            "page_size": page_size,
            "confidence": pipeline_result.confidence,
            "search_type": "multi_agent",
            "time_ms": (time.monotonic() - start_time) * 1000,
            "pipeline_detail": {
                "session_id": pipeline_result.session_id,
                "observer_time_ms": pipeline_result.observer_time_ms,
                "searcher_time_ms": pipeline_result.searcher_time_ms,
                "aggregator_time_ms": pipeline_result.aggregator_time_ms,
                "dimension_coverage": pipeline_result.dimension_coverage,
            },
        }


# 全局搜索引擎实例
_engine: Optional[MultiAgentSearchEngine] = None


def get_multi_agent_engine(
    db: Optional[AsyncSession] = None,
    **kwargs,
) -> MultiAgentSearchEngine:
    """获取多Agent搜索引擎单例"""
    global _engine
    if _engine is None or db is not None:
        _engine = MultiAgentSearchEngine(db=db, **kwargs)
    return _engine
