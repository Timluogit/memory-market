"""缓存键设计

提供缓存键生成、标签管理等功能
"""
import hashlib
import json
from typing import Any, Optional
from datetime import datetime


class CacheKeys:
    """缓存键管理类

    提供统一的缓存键生成策略和标签管理
    """

    # 键前缀
    PREFIX_SEARCH = "search"
    PREFIX_USER = "user"
    PREFIX_TEAM = "team"
    PREFIX_MEMORY = "memory"

    # 缓存标签（用于批量失效）
    TAG_SEARCH_ALL = "search:all"
    TAG_USER_PREFIX = "user:"
    TAG_TEAM_PREFIX = "team:"
    TAG_MEMORY_PREFIX = "memory:"

    @staticmethod
    def search(
        query: str,
        filters: Optional[dict] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None
    ) -> str:
        """生成搜索缓存键

        Args:
            query: 搜索查询
            filters: 过滤条件
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式

        Returns:
            缓存键，格式: search:{hash}
        """
        # 构建缓存键数据
        cache_data = {
            "query": query,
            "filters": filters or {},
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
        }

        # 生成哈希（避免键过长）
        hash_str = CacheKeys._hash_dict(cache_data)
        return f"{CacheKeys.PREFIX_SEARCH}:{hash_str}"

    @staticmethod
    def user_memories(
        user_id: str,
        filters: Optional[dict] = None,
        page: int = 1,
        page_size: int = 20
    ) -> str:
        """生成用户记忆缓存键

        Args:
            user_id: 用户ID
            filters: 过滤条件
            page: 页码
            page_size: 每页大小

        Returns:
            缓存键，格式: user:{user_id}:{hash}
        """
        cache_data = {
            "user_id": user_id,
            "filters": filters or {},
            "page": page,
            "page_size": page_size,
        }

        hash_str = CacheKeys._hash_dict(cache_data)
        return f"{CacheKeys.PREFIX_USER}:{user_id}:{hash_str}"

    @staticmethod
    def team_memories(
        team_id: str,
        filters: Optional[dict] = None,
        page: int = 1,
        page_size: int = 20
    ) -> str:
        """生成团队记忆缓存键

        Args:
            team_id: 团队ID
            filters: 过滤条件
            page: 页码
            page_size: 每页大小

        Returns:
            缓存键，格式: team:{team_id}:{hash}
        """
        cache_data = {
            "team_id": team_id,
            "filters": filters or {},
            "page": page,
            "page_size": page_size,
        }

        hash_str = CacheKeys._hash_dict(cache_data)
        return f"{CacheKeys.PREFIX_TEAM}:{team_id}:{hash_str}"

    @staticmethod
    def memory(memory_id: str) -> str:
        """生成单条记忆缓存键

        Args:
            memory_id: 记忆ID

        Returns:
            缓存键，格式: memory:{memory_id}
        """
        return f"{CacheKeys.PREFIX_MEMORY}:{memory_id}"

    @staticmethod
    def get_tags(key: str) -> list[str]:
        """根据缓存键获取关联标签

        Args:
            key: 缓存键

        Returns:
            标签列表
        """
        tags = []

        # 所有搜索结果共享此标签
        if key.startswith(CacheKeys.PREFIX_SEARCH):
            tags.append(CacheKeys.TAG_SEARCH_ALL)

        # 用户相关缓存
        if key.startswith(CacheKeys.PREFIX_USER):
            # 提取user_id
            parts = key.split(":")
            if len(parts) >= 2:
                user_id = parts[1]
                tags.append(f"{CacheKeys.TAG_USER_PREFIX}{user_id}")

        # 团队相关缓存
        if key.startswith(CacheKeys.PREFIX_TEAM):
            # 提取team_id
            parts = key.split(":")
            if len(parts) >= 2:
                team_id = parts[1]
                tags.append(f"{CacheKeys.TAG_TEAM_PREFIX}{team_id}")

        # 记忆相关缓存
        if key.startswith(CacheKeys.PREFIX_MEMORY):
            # 提取memory_id
            parts = key.split(":")
            if len(parts) >= 2:
                memory_id = parts[1]
                tags.append(f"{CacheKeys.TAG_MEMORY_PREFIX}{memory_id}")

        return tags

    @staticmethod
    def get_invalidation_patterns(
        memory_id: Optional[str] = None,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> list[str]:
        """获取缓存失效模式

        Args:
            memory_id: 记忆ID
            user_id: 用户ID
            team_id: 团队ID

        Returns:
            Redis键模式列表
        """
        patterns = []

        # 失效所有搜索缓存
        patterns.append(f"{CacheKeys.PREFIX_SEARCH}:*")

        # 失效相关用户缓存
        if user_id:
            patterns.append(f"{CacheKeys.PREFIX_USER}:{user_id}:*")

        # 失效相关团队缓存
        if team_id:
            patterns.append(f"{CacheKeys.PREFIX_TEAM}:{team_id}:*")

        # 失效单条记忆缓存
        if memory_id:
            patterns.append(CacheKeys.memory(memory_id))

        return patterns

    @staticmethod
    def _hash_dict(data: dict) -> str:
        """对字典进行哈希（保证相同参数生成相同哈希）

        Args:
            data: 字典数据

        Returns:
            MD5哈希值（32字符）
        """
        # 排序key以保证一致性
        sorted_data = json.dumps(data, sort_keys=True)
        # 生成MD5哈希
        hash_obj = hashlib.md5(sorted_data.encode())
        return hash_obj.hexdigest()

    @staticmethod
    def parse_search_key(key: str) -> Optional[dict]:
        """解析搜索缓存键（用于调试）

        Args:
            key: 搜索缓存键

        Returns:
            解析后的数据（如果哈希可逆则为原始数据，否则返回None）
        """
        # 由于使用哈希，无法反向解析
        # 如果需要调试，可以在值中存储原始参数
        return None

    @staticmethod
    def get_cache_stats_key() -> str:
        """获取缓存统计键"""
        return "cache:stats"

    @staticmethod
    def get_cache_config_key() -> str:
        """获取缓存配置键"""
        return "cache:config"

    @staticmethod
    def get_cache_hit_counter() -> str:
        """获取缓存命中计数器键"""
        return "cache:stats:hits"

    @staticmethod
    def get_cache_miss_counter() -> str:
        """获取缓存未命中计数器键"""
        return "cache:stats:misses"

    @staticmethod
    def get_cache_latency_key() -> str:
        """获取缓存延迟统计键"""
        return "cache:stats:latency"
