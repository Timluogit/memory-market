"""缓存统计API

提供缓存统计、配置管理和缓存清除功能
"""
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.search_cache_middleware import get_search_cache_middleware
from app.cache.redis_client import get_redis_client
from app.cache.cache_keys import CacheKeys

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


# ============ Models ============

class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    hits: int
    misses: int
    total: int
    hit_rate: float
    redis_stats: Optional[Dict[str, Any]] = None
    ttl: int
    enabled: bool


class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool
    ttl: int = Field(..., description="缓存过期时间（秒）")
    cache_on_miss: bool = Field(default=True, description="缓存未命中时是否写入")


class CacheConfigResponse(BaseModel):
    """缓存配置响应"""
    enabled: bool
    ttl: int
    cache_on_miss: bool


class CacheClearResponse(BaseModel):
    """缓存清除响应"""
    success: bool
    message: str
    cleared_keys: int


# ============ API Endpoints ============

@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """获取缓存统计

    Returns:
        缓存统计信息，包括命中率、延迟等
    """
    try:
        middleware = await get_search_cache_middleware()
        stats = await middleware.get_cache_stats()
        return CacheStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@router.get("/config", response_model=CacheConfigResponse)
async def get_cache_config():
    """获取缓存配置

    Returns:
        当前缓存配置
    """
    try:
        middleware = await get_search_cache_middleware()
        redis = await get_redis_client()

        # 从Redis获取持久化配置（如果存在）
        config = await redis.get(CacheKeys.get_cache_config_key())
        if config:
            return CacheConfigResponse(**config)
        else:
            # 返回默认配置
            return CacheConfigResponse(
                enabled=middleware.enabled,
                ttl=middleware.ttl,
                cache_on_miss=middleware.cache_on_miss
            )
    except Exception as e:
        logger.error(f"Failed to get cache config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache config: {str(e)}"
        )


@router.put("/config", response_model=CacheConfigResponse)
async def update_cache_config(config: CacheConfig):
    """更新缓存配置

    Args:
        config: 新的缓存配置

    Returns:
        更新后的缓存配置
    """
    try:
        middleware = await get_search_cache_middleware()
        redis = await get_redis_client()

        # 更新中间件配置
        middleware.enabled = config.enabled
        middleware.ttl = config.ttl
        middleware.cache_on_miss = config.cache_on_miss

        # 持久化配置到Redis
        config_dict = config.dict()
        await redis.set(
            CacheKeys.get_cache_config_key(),
            config_dict,
            ex=86400  # 配置保存24小时
        )

        logger.info(f"Cache config updated: {config_dict}")

        return CacheConfigResponse(
            enabled=config.enabled,
            ttl=config.ttl,
            cache_on_miss=config.cache_on_miss
        )
    except Exception as e:
        logger.error(f"Failed to update cache config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cache config: {str(e)}"
        )


@router.delete("/clear", response_model=CacheClearResponse)
async def clear_cache(pattern: Optional[str] = None):
    """清空缓存

    Args:
        pattern: 键模式（如 "search:*"），如果为None则清空所有缓存

    Returns:
        清除结果
    """
    try:
        middleware = await get_search_cache_middleware()
        redis = await get_redis_client()

        if pattern:
            # 清空匹配模式的缓存
            count = await redis.delete_pattern(pattern)
            message = f"Cleared {count} keys matching pattern: {pattern}"
        else:
            # 清空所有缓存相关的键
            patterns = [
                f"{CacheKeys.PREFIX_SEARCH}:*",
                f"{CacheKeys.PREFIX_USER}:*",
                f"{CacheKeys.PREFIX_TEAM}:*",
                f"{CacheKeys.PREFIX_MEMORY}:*",
            ]
            total = 0
            for p in patterns:
                count = await redis.delete_pattern(p)
                total += count

            # 重置统计计数器
            await redis.delete(CacheKeys.get_cache_hit_counter())
            await redis.delete(CacheKeys.get_cache_miss_counter())

            message = f"Cleared {total} cache keys and reset stats"

        logger.info(message)

        return CacheClearResponse(
            success=True,
            message=message,
            cleared_keys=0 if pattern is None else 0  # Redis不返回确切数量
        )
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/health")
async def cache_health():
    """缓存健康检查

    Returns:
        健康状态
    """
    try:
        redis = await get_redis_client()
        is_healthy = await redis.ping()

        if not is_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is not responding"
            )

        return {
            "status": "healthy",
            "redis_connected": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cache health check failed: {str(e)}"
        )


@router.get("/info")
async def cache_info():
    """获取缓存详细信息

    Returns:
        缓存详细信息
    """
    try:
        middleware = await get_search_cache_middleware()
        redis = await get_redis_client()

        # 获取Redis信息
        redis_info = await redis.get_stats()

        # 获取缓存统计
        cache_stats = await middleware.get_cache_stats()

        return {
            "middleware": {
                "enabled": middleware.enabled,
                "ttl": middleware.ttl,
                "cache_on_miss": middleware.cache_on_miss
            },
            "stats": cache_stats,
            "redis": redis_info,
            "keys": {
                "search_prefix": CacheKeys.PREFIX_SEARCH,
                "user_prefix": CacheKeys.PREFIX_USER,
                "team_prefix": CacheKeys.PREFIX_TEAM,
                "memory_prefix": CacheKeys.PREFIX_MEMORY
            }
        }
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache info: {str(e)}"
        )
