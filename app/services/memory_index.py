"""内存索引服务

纯内存索引构建、更新和持久化
无需外部数据库，支持磁盘备份和恢复
"""
import asyncio
import hashlib
import json
import logging
import pickle
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """内存条目"""
    memory_id: str
    title: str
    summary: str
    content: str
    category: str
    tags: List[str]
    price: float
    purchase_count: int
    avg_score: float
    verification_score: float
    created_at: float  # timestamp
    updated_at: float
    is_active: bool
    expiry_time: Optional[float]
    seller_name: str
    seller_reputation: float
    vector: Optional[np.ndarray] = None

    def to_dict(self) -> Dict:
        """转换为可序列化字典"""
        d = asdict(self)
        d.pop('vector', None)  # 向量单独处理
        return d

    @classmethod
    def from_dict(cls, data: Dict, vector: Optional[np.ndarray] = None) -> 'MemoryEntry':
        """从字典创建"""
        return cls(
            memory_id=data['memory_id'],
            title=data.get('title', ''),
            summary=data.get('summary', ''),
            content=data.get('content', ''),
            category=data.get('category', ''),
            tags=data.get('tags', []),
            price=data.get('price', 0.0),
            purchase_count=data.get('purchase_count', 0),
            avg_score=data.get('avg_score', 0.0),
            verification_score=data.get('verification_score', 0.0),
            created_at=data.get('created_at', 0.0),
            updated_at=data.get('updated_at', 0.0),
            is_active=data.get('is_active', True),
            expiry_time=data.get('expiry_time'),
            seller_name=data.get('seller_name', ''),
            seller_reputation=data.get('seller_reputation', 0.0),
            vector=vector
        )


class MemoryIndex:
    """内存索引服务

    Features:
    - 纯内存倒排索引（关键词 -> memory_id 集合）
    - 向量矩阵存储（numpy array）
    - 磁盘持久化（pickle / JSON）
    - 增量更新支持
    - 线程安全
    """

    def __init__(
        self,
        persist_dir: str = "./data/memory_index",
        max_vectors: int = 100000,
        auto_persist: bool = True,
        persist_interval: int = 300  # 5分钟自动持久化
    ):
        """初始化内存索引

        Args:
            persist_dir: 持久化目录
            max_vectors: 最大向量数量
            auto_persist: 是否自动持久化
            persist_interval: 自动持久化间隔（秒）
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.max_vectors = max_vectors
        self.auto_persist = auto_persist
        self.persist_interval = persist_interval

        # 内存存储
        self._entries: Dict[str, MemoryEntry] = {}
        self._vectors: Optional[np.ndarray] = None
        self._vector_ids: List[str] = []

        # 倒排索引: keyword -> set of memory_ids
        self._inverted_index: Dict[str, Set[str]] = defaultdict(set)
        # 前缀索引: prefix -> set of keywords (用于前缀搜索)
        self._prefix_index: Dict[str, Set[str]] = defaultdict(set)

        # 元数据索引
        self._category_index: Dict[str, Set[str]] = defaultdict(set)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._seller_index: Dict[str, Set[str]] = defaultdict(set)

        # 状态
        self._is_loaded = False
        self._dirty = False
        self._last_persist_time = 0.0
        self._lock = threading.RLock()

        # 后台持久化线程
        self._persist_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 统计
        self.stats = {
            'total_entries': 0,
            'total_vectors': 0,
            'index_builds': 0,
            'last_build_time': 0.0,
            'persist_count': 0,
            'load_count': 0,
        }

    # ===== 索引构建 =====

    def build_index(
        self,
        memories: List[Dict],
        vectors: Optional[List[np.ndarray]] = None,
        force_rebuild: bool = False
    ) -> int:
        """构建完整索引

        Args:
            memories: 记忆列表
            vectors: 对应的向量列表（可选）
            force_rebuild: 是否强制重建

        Returns:
            索引的记忆数量
        """
        start_time = time.time()

        with self._lock:
            if not force_rebuild and self._is_loaded:
                logger.info("Index already loaded, use add/update for incremental changes")
                return len(self._entries)

            # 清空旧索引
            self._entries.clear()
            self._inverted_index.clear()
            self._prefix_index.clear()
            self._category_index.clear()
            self._tag_index.clear()
            self._seller_index.clear()
            self._vectors = None
            self._vector_ids = []

            # 构建索引
            vector_list = []
            for i, mem in enumerate(memories):
                entry = self._add_entry(mem, vectors[i] if vectors and i < len(vectors) else None)
                if entry.vector is not None:
                    vector_list.append(entry.vector)
                    self._vector_ids.append(entry.memory_id)

            # 构建向量矩阵
            if vector_list:
                self._vectors = np.array(vector_list, dtype=np.float32)

            self._is_loaded = True
            self._dirty = True
            build_time = time.time() - start_time

            # 更新统计
            self.stats['total_entries'] = len(self._entries)
            self.stats['total_vectors'] = len(self._vector_ids)
            self.stats['index_builds'] += 1
            self.stats['last_build_time'] = build_time

            logger.info(
                f"Index built: {len(self._entries)} entries, "
                f"{len(self._vector_ids)} vectors, {build_time:.2f}s"
            )

            # 自动持久化
            if self.auto_persist:
                self._start_auto_persist()

            return len(self._entries)

    def _add_entry(self, mem: Dict, vector: Optional[np.ndarray] = None) -> MemoryEntry:
        """添加单条记忆到索引"""
        entry = MemoryEntry.from_dict(mem, vector)
        mid = entry.memory_id

        # 存储条目
        self._entries[mid] = entry

        # 构建倒排索引
        self._index_text(mid, entry.title)
        self._index_text(mid, entry.summary)
        self._index_text(mid, entry.content)

        # 构建元数据索引
        if entry.category:
            self._category_index[entry.category.lower()].add(mid)
        for tag in entry.tags:
            self._tag_index[tag.lower()].add(mid)
        if entry.seller_name:
            self._seller_index[entry.seller_name.lower()].add(mid)

        return entry

    def _index_text(self, memory_id: str, text: str):
        """文本分词并加入倒排索引"""
        if not text:
            return

        # 中文字符级 + 英文词级分词
        tokens = self._tokenize(text)
        for token in tokens:
            self._inverted_index[token].add(memory_id)
            # 前缀索引（最多4字符前缀）
            for length in range(1, min(len(token) + 1, 5)):
                prefix = token[:length]
                self._prefix_index[prefix].add(token)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """简易分词器

        支持中英文混合分词：
        - 中文：字符级 unigram + bigram
        - 英文：空格分词 + lowercasing
        - 数字：保留
        """
        tokens = []
        current_word = []

        for char in text.lower():
            if '\u4e00' <= char <= '\u9fff':
                # 中文字符
                if current_word:
                    word = ''.join(current_word)
                    tokens.append(word)
                    current_word = []
                tokens.append(char)
            elif char.isalnum() or char == '_':
                current_word.append(char)
            else:
                if current_word:
                    tokens.append(''.join(current_word))
                    current_word = []

        if current_word:
            tokens.append(''.join(current_word))

        # 添加 bigram（中文相邻字符组合）
        chinese_chars = [t for t in tokens if len(t) == 1 and '\u4e00' <= t[0] <= '\u9fff']
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])

        return list(set(tokens))  # 去重

    # ===== 增量更新 =====

    def add_memory(self, memory: Dict, vector: Optional[np.ndarray] = None):
        """添加单条记忆"""
        with self._lock:
            mid = memory.get('memory_id') or memory.get('id')
            if mid in self._entries:
                self.update_memory(memory, vector)
                return

            entry = self._add_entry(memory, vector)

            # 更新向量矩阵
            if vector is not None:
                self._vector_ids.append(mid)
                if self._vectors is None:
                    self._vectors = np.array([vector], dtype=np.float32)
                else:
                    self._vectors = np.vstack([self._vectors, vector.reshape(1, -1)])

            self._dirty = True
            self.stats['total_entries'] = len(self._entries)
            self.stats['total_vectors'] = len(self._vector_ids)

    def update_memory(self, memory: Dict, vector: Optional[np.ndarray] = None):
        """更新已有记忆"""
        with self._lock:
            mid = memory.get('memory_id') or memory.get('id')
            if mid not in self._entries:
                self.add_memory(memory, vector)
                return

            # 先删除旧索引
            self._remove_from_indexes(mid)

            # 重新添加
            old_entry = self._entries[mid]
            entry = self._add_entry(memory, vector or old_entry.vector)

            # 更新向量
            if vector is not None and mid in self._vector_ids:
                idx = self._vector_ids.index(mid)
                if self._vectors is not None:
                    self._vectors[idx] = vector

            self._dirty = True

    def remove_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        with self._lock:
            if memory_id not in self._entries:
                return False

            self._remove_from_indexes(memory_id)
            del self._entries[memory_id]

            # 移除向量
            if memory_id in self._vector_ids:
                idx = self._vector_ids.index(memory_id)
                self._vector_ids.pop(idx)
                if self._vectors is not None:
                    self._vectors = np.delete(self._vectors, idx, axis=0)

            self._dirty = True
            self.stats['total_entries'] = len(self._entries)
            self.stats['total_vectors'] = len(self._vector_ids)
            return True

    def _remove_from_indexes(self, memory_id: str):
        """从所有索引中移除记忆"""
        # 倒排索引
        for token_ids in self._inverted_index.values():
            token_ids.discard(memory_id)

        # 元数据索引
        for cat_ids in self._category_index.values():
            cat_ids.discard(memory_id)
        for tag_ids in self._tag_index.values():
            tag_ids.discard(memory_id)
        for seller_ids in self._seller_index.values():
            seller_ids.discard(memory_id)

    # ===== 查询 =====

    def get_entry(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        return self._entries.get(memory_id)

    def get_all_entries(self) -> Dict[str, MemoryEntry]:
        """获取所有条目"""
        return dict(self._entries)

    def get_vectors(self) -> Tuple[Optional[np.ndarray], List[str]]:
        """获取向量矩阵和对应ID列表"""
        return self._vectors, list(self._vector_ids)

    def keyword_search(self, query: str, top_k: int = 50) -> List[Tuple[str, float]]:
        """关键词搜索（倒排索引）

        Returns:
            [(memory_id, score), ...] 按匹配度降序
        """
        tokens = self._tokenize(query)
        if not tokens:
            return []

        # 统计每个记忆的匹配 token 数
        scores: Dict[str, int] = defaultdict(int)
        for token in tokens:
            # 精确匹配
            if token in self._inverted_index:
                for mid in self._inverted_index[token]:
                    scores[mid] += 2  # 精确匹配权重更高

            # 前缀匹配
            if token in self._prefix_index:
                for matched_token in self._prefix_index[token]:
                    if matched_token in self._inverted_index:
                        for mid in self._inverted_index[matched_token]:
                            scores[mid] += 1

        if not scores:
            return []

        # 归一化并排序
        max_score = max(scores.values())
        results = [
            (mid, score / max_score)
            for mid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ]

        return results[:top_k]

    def filter_by_category(self, category: str) -> Set[str]:
        """按分类过滤"""
        return set(self._category_index.get(category.lower(), set()))

    def filter_by_tag(self, tag: str) -> Set[str]:
        """按标签过滤"""
        return set(self._tag_index.get(tag.lower(), set()))

    def filter_by_seller(self, seller: str) -> Set[str]:
        """按卖家过滤"""
        return set(self._seller_index.get(seller.lower(), set()))

    def get_entry_count(self) -> int:
        """获取条目数量"""
        return len(self._entries)

    def get_vector_count(self) -> int:
        """获取向量数量"""
        return len(self._vector_ids)

    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._entries) == 0

    # ===== 持久化 =====

    def persist(self) -> bool:
        """持久化索引到磁盘"""
        with self._lock:
            if not self._dirty:
                return True

            try:
                # 1. 保存向量矩阵
                vectors_path = self.persist_dir / "vectors.npy"
                if self._vectors is not None:
                    np.save(str(vectors_path), self._vectors)

                # 2. 保存条目数据（不含向量）
                entries_data = {
                    mid: entry.to_dict()
                    for mid, entry in self._entries.items()
                }

                entries_path = self.persist_dir / "entries.json"
                with open(entries_path, 'w', encoding='utf-8') as f:
                    json.dump(entries_data, f, ensure_ascii=False, indent=None)

                # 3. 保存向量ID列表
                ids_path = self.persist_dir / "vector_ids.json"
                with open(ids_path, 'w', encoding='utf-8') as f:
                    json.dump(self._vector_ids, f)

                # 4. 保存索引元数据
                meta = {
                    'version': 1,
                    'total_entries': len(self._entries),
                    'total_vectors': len(self._vector_ids),
                    'persisted_at': time.time(),
                    'data_hash': self._compute_data_hash(),
                }
                meta_path = self.persist_dir / "meta.json"
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=2)

                self._dirty = False
                self._last_persist_time = time.time()
                self.stats['persist_count'] += 1

                logger.info(f"Index persisted: {len(self._entries)} entries to {self.persist_dir}")
                return True

            except Exception as e:
                logger.error(f"Failed to persist index: {e}")
                return False

    def load(self) -> bool:
        """从磁盘加载索引"""
        with self._lock:
            try:
                meta_path = self.persist_dir / "meta.json"
                if not meta_path.exists():
                    logger.info("No persisted index found")
                    return False

                # 检查数据完整性
                with open(meta_path, 'r') as f:
                    meta = json.load(f)

                saved_hash = meta.get('data_hash', '')

                # 1. 加载条目
                entries_path = self.persist_dir / "entries.json"
                with open(entries_path, 'r', encoding='utf-8') as f:
                    entries_data = json.load(f)

                # 2. 加载向量
                vectors_path = self.persist_dir / "vectors.npy"
                if vectors_path.exists():
                    self._vectors = np.load(str(vectors_path))
                else:
                    self._vectors = None

                # 3. 加载向量ID
                ids_path = self.persist_dir / "vector_ids.json"
                with open(ids_path, 'r') as f:
                    self._vector_ids = json.load(f)

                # 4. 重建内存条目和索引
                self._entries.clear()
                self._inverted_index.clear()
                self._prefix_index.clear()
                self._category_index.clear()
                self._tag_index.clear()
                self._seller_index.clear()

                for mid, entry_data in entries_data.items():
                    vector = None
                    if self._vectors is not None and mid in self._vector_ids:
                        idx = self._vector_ids.index(mid)
                        vector = self._vectors[idx]

                    entry = MemoryEntry.from_dict(entry_data, vector)
                    self._entries[mid] = entry

                    # 重建索引
                    self._index_text(mid, entry.title)
                    self._index_text(mid, entry.summary)
                    self._index_text(mid, entry.content)
                    if entry.category:
                        self._category_index[entry.category.lower()].add(mid)
                    for tag in entry.tags:
                        self._tag_index[tag.lower()].add(mid)
                    if entry.seller_name:
                        self._seller_index[entry.seller_name.lower()].add(mid)

                self._is_loaded = True
                self._dirty = False
                self.stats['total_entries'] = len(self._entries)
                self.stats['total_vectors'] = len(self._vector_ids)
                self.stats['load_count'] += 1

                logger.info(f"Index loaded: {len(self._entries)} entries from {self.persist_dir}")
                return True

            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                return False

    def _compute_data_hash(self) -> str:
        """计算数据哈希"""
        content = '|'.join(sorted(self._entries.keys()))
        return hashlib.md5(content.encode()).hexdigest()

    def _start_auto_persist(self):
        """启动自动持久化线程"""
        if self._persist_thread and self._persist_thread.is_alive():
            return

        self._stop_event.clear()
        self._persist_thread = threading.Thread(
            target=self._auto_persist_loop,
            daemon=True,
            name="memory-index-persist"
        )
        self._persist_thread.start()

    def _auto_persist_loop(self):
        """自动持久化循环"""
        while not self._stop_event.wait(self.persist_interval):
            if self._dirty:
                self.persist()

    def stop(self):
        """停止索引服务"""
        self._stop_event.set()
        if self._persist_thread:
            self._persist_thread.join(timeout=5)
        # 最后一次持久化
        if self._dirty:
            self.persist()

    def clear(self):
        """清空索引"""
        with self._lock:
            self._entries.clear()
            self._inverted_index.clear()
            self._prefix_index.clear()
            self._category_index.clear()
            self._tag_index.clear()
            self._seller_index.clear()
            self._vectors = None
            self._vector_ids = []
            self._is_loaded = False
            self._dirty = False
            self.stats['total_entries'] = 0
            self.stats['total_vectors'] = 0


# 全局单例
_index: Optional[MemoryIndex] = None


def get_memory_index(
    persist_dir: str = "./data/memory_index",
    max_vectors: int = 100000,
    auto_persist: bool = True,
    persist_interval: int = 300
) -> MemoryIndex:
    """获取内存索引单例"""
    global _index
    if _index is None:
        _index = MemoryIndex(
            persist_dir=persist_dir,
            max_vectors=max_vectors,
            auto_persist=auto_persist,
            persist_interval=persist_interval
        )
    return _index
