"""Qdrant 向量搜索引擎

使用 Qdrant 向量数据库 + sentence-transformers 实现高性能语义搜索
"""
from typing import List, Dict, Tuple, Optional, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class QdrantVectorEngine:
    """Qdrant 向量搜索引擎

    使用 BAAI/bge-small-zh-v1.5 嵌入模型 + Qdrant 向量数据库
    """

    # Collection 名称
    COLLECTION_NAME = "memories"

    # 向量维度（bge-small-zh-v1.5 为 512 维）
    VECTOR_DIM = 512

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu"
    ):
        """初始化 Qdrant 搜索引擎

        Args:
            qdrant_url: Qdrant 服务地址
            qdrant_api_key: Qdrant API 密钥（可选）
            model_name: 嵌入模型名称
            device: 运行设备 (cpu/cuda/mps)
        """
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.model_name = model_name
        self.device = device

        # 初始化 Qdrant 客户端
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        # 延迟加载嵌入模型（避免初始化时阻塞）
        self._encoder = None

        # 向量索引结构配置
        self.index_config = {
            "hnsw_config": {
                "m": 16,  # 连接数
                "ef_construct": 100,  # 构建时的搜索范围
            },
            "optimizers_config": {
                "indexing_threshold": 20000,  # 当文档数超过阈值时开始索引
            },
            "quantization_config": models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=False
                )
            )
        }

    def _get_encoder(self):
        """获取嵌入模型（延迟加载）"""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._encoder = SentenceTransformer(self.model_name, device=self.device)
            logger.info("Embedding model loaded successfully")
        return self._encoder

    def create_collection(self, recreate: bool = False) -> bool:
        """创建 Qdrant Collection

        Args:
            recreate: 是否重建（删除后创建）

        Returns:
            是否成功
        """
        try:
            # 检查 collection 是否存在
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.COLLECTION_NAME in collection_names:
                if recreate:
                    logger.info(f"Recreating collection: {self.COLLECTION_NAME}")
                    self.client.delete_collection(self.COLLECTION_NAME)
                else:
                    logger.info(f"Collection already exists: {self.COLLECTION_NAME}")
                    return True

            # 创建 collection
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_DIM,
                    distance=Distance.COSINE,
                    **self.index_config
                ),
                optimizers_config=self.index_config.get("optimizers_config"),
                quantization_config=self.index_config.get("quantization_config")
            )

            logger.info(f"Collection created: {self.COLLECTION_NAME}")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def index_memories(self, memories: List[Dict], batch_size: int = 100) -> int:
        """批量索引记忆

        Args:
            memories: 记忆列表，每个包含 id, title, summary, category, tags, price 等
            batch_size: 批量插入大小

        Returns:
            成功索引的记忆数量
        """
        if not memories:
            return 0

        encoder = self._get_encoder()

        # 准备文本和点
        points = []
        for idx, memory in enumerate(memories):
            # 构建搜索文本：标题 + 摘要 + 分类 + 标签
            text_parts = [
                memory.get('title', ''),
                memory.get('summary', ''),
                memory.get('category', ''),
                ' '.join(memory.get('tags', []))
            ]
            text = ' '.join(filter(None, text_parts))

            # 生成向量
            vector = encoder.encode(text, convert_to_numpy=True)

            # 构建 point
            point = PointStruct(
                id=memory['id'],
                vector=vector.tolist(),
                payload={
                    "title": memory.get('title', ''),
                    "summary": memory.get('summary', ''),
                    "category": memory.get('category', ''),
                    "tags": memory.get('tags', []),
                    "price": memory.get('price', 0),
                    "purchase_count": memory.get('purchase_count', 0),
                    "avg_score": memory.get('avg_score', 0),
                    "created_at": memory.get('created_at', ''),
                }
            )
            points.append(point)

        # 批量插入
        success_count = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            try:
                self.client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=batch,
                    wait=True
                )
                success_count += len(batch)
                logger.debug(f"Upserted batch {i//batch_size + 1}: {len(batch)} points")
            except Exception as e:
                logger.error(f"Failed to upsert batch {i//batch_size + 1}: {e}")

        logger.info(f"Indexed {success_count}/{len(memories)} memories")
        return success_count

    def search(
        self,
        query: str,
        top_k: int = 50,
        min_score: float = 0.1,
        filters: Optional[Dict[str, Any]] = None,
        payload_filter: Optional[Filter] = None
    ) -> List[Tuple[str, float, Dict]]:
        """向量搜索

        Args:
            query: 搜索查询
            top_k: 返回前 k 个结果
            min_score: 最小相似度阈值
            filters: 字段过滤（可选），如 {"category": "抖音/爆款"}
            payload_filter: Qdrant Filter 对象（高级过滤）

        Returns:
            [(memory_id, score, payload), ...] 按相似度降序排序
        """
        if not query.strip():
            return []

        encoder = self._get_encoder()

        # 查询向量化
        query_vector = encoder.encode(query, convert_to_numpy=True)

        # 构建过滤器
        search_filter = None
        if payload_filter:
            search_filter = payload_filter
        elif filters:
            # 简单的字段过滤
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            if conditions:
                search_filter = Filter(must=conditions)

        # 执行搜索
        try:
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector.tolist(),
                query_filter=search_filter,
                limit=top_k,
                score_threshold=min_score,
                with_payload=True
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        # 转换结果
        formatted_results = []
        for result in results:
            formatted_results.append((
                str(result.id),
                result.score,
                result.payload
            ))

        return formatted_results

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆向量

        Args:
            memory_id: 记忆 ID

        Returns:
            是否成功
        """
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.PointIdsList(points=[memory_id])
            )
            logger.debug(f"Deleted vector for memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector for {memory_id}: {e}")
            return False

    def delete_collection(self) -> bool:
        """删除整个 Collection（清空所有向量）

        Returns:
            是否成功
        """
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
            logger.info(f"Collection deleted: {self.COLLECTION_NAME}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    def get_collection_info(self) -> Optional[Dict]:
        """获取 Collection 信息

        Returns:
            Collection 信息字典
        """
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "name": info.config.params.vectors.size,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "status": info.status,
                "optimizer_status": info.optimizer_status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None

    def health_check(self) -> bool:
        """健康检查

        Returns:
            Qdrant 服务是否可用
        """
        try:
            # 尝试获取 collections 列表
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# 全局单例
_qdrant_engine: Optional[QdrantVectorEngine] = None


def get_qdrant_engine(
    qdrant_url: str = "http://localhost:6333",
    qdrant_api_key: Optional[str] = None,
    model_name: str = "BAAI/bge-small-zh-v1.5",
    device: str = "cpu"
) -> QdrantVectorEngine:
    """获取 Qdrant 搜索引擎单例

    Args:
        qdrant_url: Qdrant 服务地址
        qdrant_api_key: Qdrant API 密钥（可选）
        model_name: 嵌入模型名称
        device: 运行设备

    Returns:
        Qdrant 向量搜索引擎实例
    """
    global _qdrant_engine
    if _qdrant_engine is None:
        _qdrant_engine = QdrantVectorEngine(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            model_name=model_name,
            device=device
        )
    return _qdrant_engine
