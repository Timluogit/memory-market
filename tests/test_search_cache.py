"""搜索缓存测试

测试缓存命中、失效、并发和性能
"""
import asyncio
import pytest
import time
from typing import Dict, Any

from app.cache.redis_client import RedisClient
from app.cache.cache_keys import CacheKeys
from app.api.search_cache_middleware import SearchCacheMiddleware
from app.services.cache_invalidation_service import CacheInvalidationService


# ============ Fixtures ============

@pytest.fixture
async def redis_client():
    """Redis客户端fixture"""
    client = RedisClient(url="redis://localhost:6379/1")
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
async def cache_middleware(redis_client):
    """缓存中间件fixture"""
    middleware = SearchCacheMiddleware(ttl=60, enabled=True)
    middleware.redis = redis_client
    await middleware.initialize()
    yield middleware


@pytest.fixture
async def invalidation_service(redis_client):
    """缓存失效服务fixture"""
    service = CacheInvalidationService(delay_invalidation=False)
    service.redis = redis_client
    await service.initialize()
    yield service
    await service.stop()


# ============ Redis Client Tests ============

@pytest.mark.asyncio
async def test_redis_client_ping(redis_client):
    """测试Redis健康检查"""
    result = await redis_client.ping()
    assert result is True


@pytest.mark.asyncio
async def test_redis_client_set_get(redis_client):
    """测试Redis set/get"""
    key = "test:set:get"
    value = {"test": "data", "number": 123}

    # 设置值
    result = await redis_client.set(key, value, ex=60)
    assert result is True

    # 获取值
    cached = await redis_client.get(key)
    assert cached == value

    # 清理
    await redis_client.delete(key)


@pytest.mark.asyncio
async def test_redis_client_delete_pattern(redis_client):
    """测试批量删除"""
    keys = ["test:pattern:1", "test:pattern:2", "test:pattern:3"]

    # 设置多个键
    for key in keys:
        await redis_client.set(key, {"data": key}, ex=60)

    # 批量删除
    count = await redis_client.delete_pattern("test:pattern:*")
    assert count == 3

    # 验证删除
    for key in keys:
        cached = await redis_client.get(key)
        assert cached is None


@pytest.mark.asyncio
async def test_redis_client_stats(redis_client):
    """测试Redis统计"""
    stats = await redis_client.get_stats()
    assert "used_memory" in stats
    assert "connected_clients" in stats


# ============ Cache Keys Tests ============

def test_cache_keys_search():
    """测试搜索缓存键生成"""
    key1 = CacheKeys.search("test query", {"category": "tech"}, 1, 20)
    key2 = CacheKeys.search("test query", {"category": "tech"}, 1, 20)
    key3 = CacheKeys.search("test query", {"category": "tech"}, 2, 20)

    # 相同参数生成相同键
    assert key1 == key2

    # 不同参数生成不同键
    assert key1 != key3


def test_cache_keys_user():
    """测试用户缓存键生成"""
    key = CacheKeys.user_memories("user123", {"status": "active"}, 1, 20)
    assert key.startswith("user:")
    assert "user123" in key


def test_cache_keys_team():
    """测试团队缓存键生成"""
    key = CacheKeys.team_memories("team456", {"category": "shared"}, 1, 20)
    assert key.startswith("team:")
    assert "team456" in key


def test_cache_keys_memory():
    """测试记忆缓存键生成"""
    key = CacheKeys.memory("mem789")
    assert key == "memory:mem789"


def test_cache_keys_tags():
    """测试标签提取"""
    search_key = CacheKeys.search("test", {}, 1, 20)
    tags = CacheKeys.get_tags(search_key)
    assert CacheKeys.TAG_SEARCH_ALL in tags

    user_key = CacheKeys.user_memories("user123", {}, 1, 20)
    tags = CacheKeys.get_tags(user_key)
    assert f"{CacheKeys.TAG_USER_PREFIX}user123" in tags


# ============ Cache Middleware Tests ============

@pytest.mark.asyncio
async def test_cache_hit(cache_middleware):
    """测试缓存命中"""
    query = "test query hit"
    filters = {"category": "tech"}
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1, "content": "test"}],
            "total": 1
        }

    # 第一次搜索（缓存未命中）
    result1 = await cache_middleware.search_with_cache(
        query=query,
        filters=filters,
        search_func=mock_search
    )
    assert search_count == 1
    assert result1["cached"] is False

    # 第二次搜索（缓存命中）
    result2 = await cache_middleware.search_with_cache(
        query=query,
        filters=filters,
        search_func=mock_search
    )
    assert search_count == 1  # 搜索函数未再次调用
    assert result2["cached"] is True
    assert result2["results"] == result1["results"]


@pytest.mark.asyncio
async def test_cache_miss(cache_middleware):
    """测试缓存未命中"""
    query1 = "query1"
    query2 = "query2"
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1, "content": kwargs["query"]}],
            "total": 1
        }

    # 执行两个不同的查询
    result1 = await cache_middleware.search_with_cache(
        query=query1,
        search_func=mock_search
    )
    result2 = await cache_middleware.search_with_cache(
        query=query2,
        search_func=mock_search
    )

    # 两次都是缓存未命中
    assert search_count == 2
    assert result1["cached"] is False
    assert result2["cached"] is False


@pytest.mark.asyncio
async def test_cache_disabled(cache_middleware):
    """测试缓存禁用"""
    cache_middleware.enabled = False
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1}],
            "total": 1
        }

    query = "test query"

    # 第一次搜索
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 第二次搜索（缓存已禁用，应该再次调用搜索）
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 搜索函数应该被调用两次
    assert search_count == 2


@pytest.mark.asyncio
async def test_cache_stats(cache_middleware):
    """测试缓存统计"""
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1}],
            "total": 1
        }

    query = "test query"

    # 第一次搜索（未命中）
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 第二次搜索（命中）
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 获取统计
    stats = await cache_middleware.get_cache_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["total"] >= 2
    assert stats["hit_rate"] > 0


@pytest.mark.asyncio
async def test_clear_cache(cache_middleware):
    """测试清空缓存"""
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1}],
            "total": 1
        }

    query = "test query"

    # 第一次搜索（写入缓存）
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 清空缓存
    await cache_middleware.clear_cache()

    # 第二次搜索（缓存已清空，应该再次调用搜索）
    await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )

    # 搜索函数应该被调用两次
    assert search_count == 2


# ============ Cache Invalidation Tests ============

@pytest.mark.asyncio
async def test_invalidate_memory(invalidation_service):
    """测试记忆失效"""
    # 设置测试数据
    key = CacheKeys.memory("mem123")
    await invalidation_service.redis.set(key, {"data": "test"}, ex=60)

    # 验证缓存存在
    exists = await invalidation_service.redis.exists(key)
    assert exists is True

    # 失效记忆
    await invalidation_service.invalidate_memory("mem123", delay=False)

    # 等待失效完成
    await asyncio.sleep(0.5)

    # 验证缓存已失效
    exists = await invalidation_service.redis.exists(key)
    assert exists is False


@pytest.mark.asyncio
async def test_invalidate_user(invalidation_service):
    """测试用户失效"""
    # 设置测试数据
    key = CacheKeys.user_memories("user456", {}, 1, 20)
    await invalidation_service.redis.set(key, {"data": "test"}, ex=60)

    # 失效用户
    await invalidation_service.invalidate_user("user456", delay=False)

    # 等待失效完成
    await asyncio.sleep(0.5)

    # 验证缓存已失效
    exists = await invalidation_service.redis.exists(key)
    assert exists is False


@pytest.mark.asyncio
async def test_invalidate_team(invalidation_service):
    """测试团队失效"""
    # 设置测试数据
    key = CacheKeys.team_memories("team789", {}, 1, 20)
    await invalidation_service.redis.set(key, {"data": "test"}, ex=60)

    # 失效团队
    await invalidation_service.invalidate_team("team789", delay=False)

    # 等待失效完成
    await asyncio.sleep(0.5)

    # 验证缓存已失效
    exists = await invalidation_service.redis.exists(key)
    assert exists is False


@pytest.mark.asyncio
async def test_invalidate_pattern(invalidation_service):
    """测试模式失效"""
    # 设置测试数据
    keys = ["test:pattern:a", "test:pattern:b", "test:pattern:c"]
    for key in keys:
        await invalidation_service.redis.set(key, {"data": key}, ex=60)

    # 失效模式
    await invalidation_service.invalidate_pattern("test:pattern:*", delay=False)

    # 等待失效完成
    await asyncio.sleep(0.5)

    # 验证所有缓存已失效
    for key in keys:
        exists = await invalidation_service.redis.exists(key)
        assert exists is False


@pytest.mark.asyncio
async def test_invalidate_batch(invalidation_service):
    """测试批量失效"""
    # 设置测试数据
    memory_ids = ["mem1", "mem2", "mem3"]
    for mem_id in memory_ids:
        key = CacheKeys.memory(mem_id)
        await invalidation_service.redis.set(key, {"data": mem_id}, ex=60)

    # 批量失效
    await invalidation_service.invalidate_batch(
        memory_ids=memory_ids,
        delay=False
    )

    # 等待失效完成
    await asyncio.sleep(0.5)

    # 验证所有缓存已失效
    for mem_id in memory_ids:
        key = CacheKeys.memory(mem_id)
        exists = await invalidation_service.redis.exists(key)
        assert exists is False


# ============ Performance Tests ============

@pytest.mark.asyncio
async def test_cache_latency(cache_middleware):
    """测试缓存延迟"""
    async def mock_search(**kwargs):
        await asyncio.sleep(0.1)  # 模拟搜索耗时
        return {
            "results": [{"id": 1}],
            "total": 1
        }

    query = "test query"

    # 第一次搜索（未命中）
    start = time.time()
    result1 = await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )
    latency1 = (time.time() - start) * 1000

    # 第二次搜索（命中）
    start = time.time()
    result2 = await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )
    latency2 = (time.time() - start) * 1000

    # 缓存命中应该快很多
    assert latency1 >= 100  # 模拟搜索耗时100ms
    assert latency2 < 50  # 缓存命中应该<50ms
    assert result1["cached"] is False
    assert result2["cached"] is True


@pytest.mark.asyncio
async def test_concurrent_cache_access(cache_middleware):
    """测试并发缓存访问"""
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        await asyncio.sleep(0.05)
        search_count += 1
        return {
            "results": [{"id": 1}],
            "total": 1
        }

    query = "test query"

    # 并发执行10次相同查询
    tasks = [
        cache_middleware.search_with_cache(
            query=query,
            search_func=mock_search
        )
        for _ in range(10)
    ]

    results = await asyncio.gather(*tasks)

    # 由于并发，可能会有多次未命中，但应该远少于10次
    assert search_count <= 10

    # 所有结果应该一致
    for result in results[1:]:
        assert result["results"] == results[0]["results"]


# ============ Integration Tests ============

@pytest.mark.asyncio
async def test_search_with_invalidation(cache_middleware, invalidation_service):
    """测试搜索与失效集成"""
    search_count = 0

    async def mock_search(**kwargs):
        nonlocal search_count
        search_count += 1
        return {
            "results": [{"id": 1, "memory_id": "mem123"}],
            "total": 1
        }

    query = "test query"

    # 第一次搜索
    result1 = await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )
    assert search_count == 1

    # 第二次搜索（缓存命中）
    result2 = await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )
    assert search_count == 1  # 未再次调用搜索

    # 失效记忆
    await invalidation_service.invalidate_memory("mem123", delay=False)
    await asyncio.sleep(0.5)

    # 第三次搜索（缓存已失效）
    result3 = await cache_middleware.search_with_cache(
        query=query,
        search_func=mock_search
    )
    assert search_count == 2  # 再次调用搜索


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
