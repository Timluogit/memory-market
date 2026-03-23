"""缓存集成示例

展示如何将搜索缓存集成到现有搜索API中
"""
from typing import Dict, Any, Optional
from fastapi import Depends

from app.api.search_cache_middleware import get_search_cache_middleware
from app.services.cache_invalidation_service import get_cache_invalidation_service


# ============ 搜索API集成示例 ============

async def search_memories_with_cache(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: Optional[str] = None,
    search_type: str = "hybrid"
) -> Dict[str, Any]:
    """搜索记忆（带缓存）

    Args:
        query: 搜索查询
        filters: 过滤条件
        page: 页码
        page_size: 每页大小
        sort_by: 排序方式
        search_type: 搜索类型（semantic, keyword, hybrid）

    Returns:
        搜索结果，包含缓存信息
    """
    # 获取缓存中间件
    middleware = await get_search_cache_middleware()

    # 定义实际搜索函数
    async def execute_search(**kwargs):
        from app.search.hybrid_search import HybridSearchEngine
        engine = HybridSearchEngine()
        results = await engine.search(**kwargs)
        return results

    # 执行带缓存的搜索
    result = await middleware.search_with_cache(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        search_func=execute_search,
        search_type=search_type
    )

    return result


# ============ 数据更新API集成示例 ============

async def update_memory_with_cache_invalidation(
    memory_id: str,
    user_id: str,
    team_id: Optional[str] = None,
    data: Dict[str, Any] = None,
    db=None
) -> Dict[str, Any]:
    """更新记忆（带缓存失效）

    Args:
        memory_id: 记忆ID
        user_id: 用户ID
        team_id: 团队ID（可选）
        data: 更新数据
        db: 数据库会话

    Returns:
        更新后的记忆
    """
    # 更新数据库
    # 这里调用实际的更新逻辑
    updated_memory = await _update_memory_in_db(db, memory_id, data)

    # 失效相关缓存
    invalidation_service = await get_cache_invalidation_service()
    await invalidation_service.invalidate_memory(
        memory_id=memory_id,
        user_id=user_id,
        team_id=team_id,
        delay=False  # 立即失效
    )

    return updated_memory


async def _update_memory_in_db(db, memory_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """更新记忆到数据库（内部函数）

    实际实现取决于你的数据库访问层
    """
    # TODO: 实现数据库更新逻辑
    return {"memory_id": memory_id, **data}


async def delete_memory_with_cache_invalidation(
    memory_id: str,
    user_id: str,
    team_id: Optional[str] = None,
    db=None
) -> bool:
    """删除记忆（带缓存失效）

    Args:
        memory_id: 记忆ID
        user_id: 用户ID
        team_id: 团队ID（可选）
        db: 数据库会话

    Returns:
        是否删除成功
    """
    # 从数据库删除
    # 这里调用实际的删除逻辑
    success = await _delete_memory_from_db(db, memory_id)

    if success:
        # 失效相关缓存
        invalidation_service = await get_cache_invalidation_service()
        await invalidation_service.invalidate_memory(
            memory_id=memory_id,
            user_id=user_id,
            team_id=team_id,
            delay=False  # 立即失效
        )

    return success


async def _delete_memory_from_db(db, memory_id: str) -> bool:
    """从数据库删除记忆（内部函数）

    实际实现取决于你的数据库访问层
    """
    # TODO: 实现数据库删除逻辑
    return True


# ============ 批量操作集成示例 ============

async def bulk_update_memories_with_cache_invalidation(
    updates: list[Dict[str, Any]],
    delay: bool = True
) -> int:
    """批量更新记忆（带缓存失效）

    Args:
        updates: 更新列表，每个元素包含 memory_id, user_id, team_id, data
        delay: 是否延迟失效

    Returns:
        更新的数量
    """
    memory_ids = [u["memory_id"] for u in updates]
    user_ids = list({u["user_id"] for u in updates})
    team_ids = list({u["team_id"] for u in updates if u.get("team_id")})

    # 批量更新数据库
    # TODO: 实现批量更新逻辑

    # 批量失效缓存
    invalidation_service = await get_cache_invalidation_service()
    await invalidation_service.invalidate_batch(
        memory_ids=memory_ids,
        user_ids=user_ids,
        team_ids=team_ids,
        delay=delay
    )

    return len(updates)


# ============ 装饰器使用示例 ============

from app.api.search_cache_middleware import cache_search


@cache_search(ttl=1800)  # 缓存30分钟
async def semantic_search_with_cache(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """语义搜索（带缓存装饰器）"""
    from app.search.vector_search import VectorSearchEngine
    engine = VectorSearchEngine()
    results = await engine.search(query, filters, page, page_size)
    return results


# ============ FastAPI路由集成示例 ============

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_agent
from app.models.schemas import MemoryCreate
from app.models.tables import Agent

router = APIRouter()


@router.get("/memories/search")
async def search_memories_endpoint(
    query: str,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """搜索记忆API端点（带缓存）"""
    filters = {}
    if category:
        filters["category"] = category

    result = await search_memories_with_cache(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size
    )

    return {
        "success": True,
        "data": {
            "results": result["results"],
            "total": result["total"],
            "cached": result["cached"],
            "response_time_ms": result["response_time_ms"]
        }
    }


@router.put("/memories/{memory_id}")
async def update_memory_endpoint(
    memory_id: str,
    data: Dict[str, Any],
    agent: Agent = Depends(get_current_agent),
    db = Depends(get_db)
):
    """更新记忆API端点（带缓存失效）"""
    result = await update_memory_with_cache_invalidation(
        memory_id=memory_id,
        user_id=agent.agent_id,
        data=data,
        db=db
    )

    return {
        "success": True,
        "data": result
    }
