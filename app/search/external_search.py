"""
外部数据源搜索集成
统一搜索接口，跨所有数据源搜索
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import asyncio

from ..services.external_source_service import (
    external_source_service,
    Document,
    SourceType,
)

logger = logging.getLogger(__name__)


class SearchResult:
    """搜索结果"""

    def __init__(
        self,
        document: Document,
        score: float,
        source_info: Dict[str, Any],
    ):
        self.document = document
        self.score = score
        self.source_info = source_info

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "score": self.score,
            "source_info": self.source_info,
        }


class ExternalSearchEngine:
    """外部数据源搜索引擎"""

    def __init__(self):
        self._cache: Dict[str, List[SearchResult]] = {}
        self._cache_ttl = 300  # 5分钟缓存
        self._cache_timestamps: Dict[str, datetime] = {}

    async def search(
        self,
        query: str,
        source_ids: Optional[List[str]] = None,
        limit: int = 10,
        min_score: float = 0.0,
        use_cache: bool = True,
    ) -> List[SearchResult]:
        """
        跨数据源搜索

        Args:
            query: 搜索查询
            source_ids: 数据源ID列表（可选，None表示搜索所有）
            limit: 返回数量限制
            min_score: 最小分数阈值
            use_cache: 是否使用缓存

        Returns:
            搜索结果列表
        """
        # 检查缓存
        if use_cache and self._is_cache_valid(query):
            logger.info(f"Using cached results for query: {query}")
            cached_results = self._cache.get(query, [])
            return [r for r in cached_results if r.score >= min_score][:limit]

        # 执行搜索
        all_results: List[SearchResult] = []

        # 确定要搜索的数据源
        if source_ids:
            sources_to_search = source_ids
        else:
            connections = await external_source_service.list_sources()
            sources_to_search = [c.source_id for c in connections if c.enabled]

        # 并行搜索所有数据源
        search_tasks = []
        for source_id in sources_to_search:
            search_tasks.append(self._search_source(source_id, query))

        if search_tasks:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Search failed: {result}")

        # 排序（按分数降序）
        all_results.sort(key=lambda r: r.score, reverse=True)

        # 过滤和限制
        filtered_results = [r for r in all_results if r.score >= min_score][:limit]

        # 更新缓存
        if use_cache:
            self._cache[query] = filtered_results
            self._cache_timestamps[query] = datetime.utcnow()

        logger.info(f"Search completed: {len(filtered_results)} results from {len(sources_to_search)} sources")
        return filtered_results

    async def _search_source(self, source_id: str, query: str) -> List[SearchResult]:
        """搜索单个数据源"""
        try:
            from ..services.external_source_service import external_source_service

            # 获取数据源信息
            connection = await external_source_service.get_source_status(source_id)

            if not connection or not connection.enabled:
                return []

            # 搜索文档
            documents = await external_source_service._adapters[source_id].search(query, limit=50)

            # 计算分数
            results = []
            for doc in documents:
                score = self._calculate_score(query, doc)

                if score > 0:
                    results.append(SearchResult(
                        document=doc,
                        score=score,
                        source_info={
                            "source_id": source_id,
                            "source_type": connection.source_type.value,
                        },
                    ))

            return results

        except Exception as e:
            logger.error(f"Failed to search source {source_id}: {e}")
            return []

    def _calculate_score(self, query: str, document: Document) -> float:
        """
        计算搜索分数

        简单的基于关键词匹配的分数计算
        可以替换为更复杂的算法（如BM25、TF-IDF等）
        """
        query_lower = query.lower()
        score = 0.0

        # 标题匹配（权重更高）
        if query_lower in document.title.lower():
            score += 1.0

        # 内容匹配
        if query_lower in document.content.lower():
            # 计算出现次数
            count = document.content.lower().count(query_lower)
            score += min(count * 0.1, 0.5)

        # 标签匹配
        for tag in document.metadata.get("tags", []):
            if query_lower in tag.lower():
                score += 0.2

        # 作者匹配
        if document.author and query_lower in document.author.lower():
            score += 0.3

        return min(score, 1.0)

    def _is_cache_valid(self, query: str) -> bool:
        """检查缓存是否有效"""
        if query not in self._cache:
            return False

        timestamp = self._cache_timestamps.get(query)
        if not timestamp:
            return False

        age = (datetime.utcnow() - timestamp).total_seconds()
        return age < self._cache_ttl

    async def clear_cache(self, query: Optional[str] = None):
        """清理缓存"""
        if query:
            if query in self._cache:
                del self._cache[query]
            if query in self._cache_timestamps:
                del self._cache_timestamps[query]
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

        logger.info(f"Cleared cache for query: {query or 'all'}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "cached_queries": len(self._cache),
            "cache_ttl_seconds": self._cache_ttl,
        }


class UnifiedSearchResponse:
    """统一搜索响应"""

    def __init__(
        self,
        results: List[SearchResult],
        query: str,
        total_results: int,
        sources_searched: List[str],
        search_time_ms: int,
    ):
        self.results = results
        self.query = query
        self.total_results = total_results
        self.sources_searched = sources_searched
        self.search_time_ms = search_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "query": self.query,
            "total_results": self.total_results,
            "sources_searched": self.sources_searched,
            "search_time_ms": self.search_time_ms,
        }


async def search_external_sources(
    query: str,
    source_ids: Optional[List[str]] = None,
    limit: int = 10,
    min_score: float = 0.0,
) -> UnifiedSearchResponse:
    """
    搜索外部数据源的便捷函数

    Args:
        query: 搜索查询
        source_ids: 数据源ID列表（可选）
        limit: 返回数量限制
        min_score: 最小分数阈值

    Returns:
        统一搜索响应
    """
    engine = ExternalSearchEngine()
    start_time = datetime.utcnow()

    results = await engine.search(
        query=query,
        source_ids=source_ids,
        limit=limit,
        min_score=min_score,
    )

    end_time = datetime.utcnow()

    # 获取搜索的数据源
    if source_ids:
        sources_searched = source_ids
    else:
        connections = await external_source_service.list_sources()
        sources_searched = [c.source_id for c in connections if c.enabled]

    return UnifiedSearchResponse(
        results=results,
        query=query,
        total_results=len(results),
        sources_searched=sources_searched,
        search_time_ms=int((end_time - start_time).total_seconds() * 1000),
    )


# 全局搜索引擎实例
external_search_engine = ExternalSearchEngine()
