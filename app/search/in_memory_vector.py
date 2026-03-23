"""内存向量搜索引擎

纯内存向量搜索，无需外部数据库
支持余弦相似度和欧氏距离
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.services.memory_index import MemoryIndex, get_memory_index

logger = logging.getLogger(__name__)


class InMemoryVectorEngine:
    """内存向量搜索引擎

    使用 numpy 矩阵运算实现高性能向量搜索
    支持余弦相似度和欧氏距离
    """

    def __init__(
        self,
        index: Optional[MemoryIndex] = None,
        similarity_metric: str = "cosine",
        batch_size: int = 1000
    ):
        """初始化内存向量搜索引擎

        Args:
            index: 内存索引实例
            similarity_metric: 相似度算法 (cosine / euclidean)
            batch_size: 批量搜索时每批大小
        """
        self.index = index or get_memory_index()
        self.similarity_metric = similarity_metric
        self.batch_size = batch_size

        # 统计
        self.stats = {
            'total_searches': 0,
            'total_search_time': 0.0,
            'avg_search_time': 0.0,
            'cache_hits': 0,
        }

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 50,
        min_score: float = 0.1,
        filter_ids: Optional[set] = None
    ) -> List[Tuple[str, float]]:
        """向量搜索

        Args:
            query_vector: 查询向量
            top_k: 返回前 k 个结果
            min_score: 最小相似度阈值
            filter_ids: 限定搜索范围的 ID 集合

        Returns:
            [(memory_id, score), ...] 按相似度降序
        """
        start_time = time.time()

        vectors, vector_ids = self.index.get_vectors()
        if vectors is None or len(vector_ids) == 0:
            return []

        # 确保 query_vector 是 1D
        if query_vector.ndim > 1:
            query_vector = query_vector.flatten()

        # 计算相似度
        if self.similarity_metric == "cosine":
            scores = self._cosine_similarity_batch(query_vector, vectors)
        elif self.similarity_metric == "euclidean":
            scores = self._euclidean_distance_batch(query_vector, vectors)
        else:
            raise ValueError(f"Unknown similarity metric: {self.similarity_metric}")

        # 构建结果
        results = []
        for i, mid in enumerate(vector_ids):
            if filter_ids is not None and mid not in filter_ids:
                continue
            score = float(scores[i])
            if score >= min_score:
                results.append((mid, score))

        # 排序并截断
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:top_k]

        elapsed = time.time() - start_time
        self.stats['total_searches'] += 1
        self.stats['total_search_time'] += elapsed
        self.stats['avg_search_time'] = self.stats['total_search_time'] / self.stats['total_searches']

        return results

    def batch_search(
        self,
        query_vectors: List[np.ndarray],
        top_k: int = 50,
        min_score: float = 0.1
    ) -> List[List[Tuple[str, float]]]:
        """批量向量搜索

        Args:
            query_vectors: 查询向量列表
            top_k: 每个查询返回的结果数
            min_score: 最小分数阈值

        Returns:
            List of [(memory_id, score), ...] for each query
        """
        vectors, vector_ids = self.index.get_vectors()
        if vectors is None or len(vector_ids) == 0:
            return [[] for _ in query_vectors]

        all_results = []

        # 分批处理查询
        for i in range(0, len(query_vectors), self.batch_size):
            batch_queries = query_vectors[i:i + self.batch_size]

            # 批量计算相似度矩阵: (batch_size, num_vectors)
            query_matrix = np.array([q.flatten() for q in batch_queries], dtype=np.float32)

            if self.similarity_metric == "cosine":
                # 归一化
                query_norms = np.linalg.norm(query_matrix, axis=1, keepdims=True)
                query_norms = np.where(query_norms == 0, 1, query_norms)
                query_normalized = query_matrix / query_norms

                vector_norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                vector_norms = np.where(vector_norms == 0, 1, vector_norms)
                vectors_normalized = vectors / vector_norms

                similarity_matrix = query_normalized @ vectors_normalized.T
            else:
                # 欧氏距离 -> 相似度
                diff = query_matrix[:, np.newaxis, :] - vectors[np.newaxis, :, :]
                distances = np.linalg.norm(diff, axis=2)
                similarity_matrix = 1.0 / (1.0 + distances)

            # 对每个查询取 top_k
            for j in range(len(batch_queries)):
                scores = similarity_matrix[j]
                top_indices = np.argsort(scores)[::-1][:top_k]

                query_results = []
                for idx in top_indices:
                    score = float(scores[idx])
                    if score >= min_score:
                        query_results.append((vector_ids[idx], score))

                all_results.append(query_results)

        return all_results

    def search_by_text(
        self,
        query_embedding: np.ndarray,
        top_k: int = 50,
        min_score: float = 0.1,
        filter_ids: Optional[set] = None
    ) -> List[Tuple[str, float]]:
        """通过文本嵌入向量搜索（接口兼容）

        等同于 search()，用于与 Qdrant 引擎接口兼容
        """
        return self.search(query_embedding, top_k, min_score, filter_ids)

    @staticmethod
    def _cosine_similarity_batch(
        query: np.ndarray,
        vectors: np.ndarray
    ) -> np.ndarray:
        """批量余弦相似度计算

        Args:
            query: 查询向量 (dim,)
            vectors: 向量矩阵 (N, dim)

        Returns:
            相似度数组 (N,)
        """
        # 归一化
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return np.zeros(len(vectors))
        query_normalized = query / query_norm

        vector_norms = np.linalg.norm(vectors, axis=1)
        vector_norms = np.where(vector_norms == 0, 1, vector_norms)
        vectors_normalized = vectors / vector_norms[:, np.newaxis]

        # 点积 = 余弦相似度
        return vectors_normalized @ query_normalized

    @staticmethod
    def _euclidean_distance_batch(
        query: np.ndarray,
        vectors: np.ndarray
    ) -> np.ndarray:
        """批量欧氏距离 -> 相似度

        转换公式: similarity = 1 / (1 + distance)
        """
        diff = vectors - query
        distances = np.linalg.norm(diff, axis=1)
        return 1.0 / (1.0 + distances)

    def get_stats(self) -> Dict:
        """获取搜索统计"""
        return {
            **self.stats,
            'vector_count': self.index.get_vector_count(),
            'similarity_metric': self.similarity_metric,
        }

    def clear_stats(self):
        """清除统计"""
        self.stats = {
            'total_searches': 0,
            'total_search_time': 0.0,
            'avg_search_time': 0.0,
            'cache_hits': 0,
        }


# 全局单例
_engine: Optional[InMemoryVectorEngine] = None


def get_in_memory_vector_engine(
    index: Optional[MemoryIndex] = None,
    similarity_metric: str = "cosine",
    batch_size: int = 1000
) -> InMemoryVectorEngine:
    """获取内存向量搜索引擎单例"""
    global _engine
    if _engine is None:
        _engine = InMemoryVectorEngine(
            index=index,
            similarity_metric=similarity_metric,
            batch_size=batch_size
        )
    return _engine
