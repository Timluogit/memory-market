"""
Qdrant 客户端单元测试

测试 Qdrant 向量搜索引擎的核心功能，包括：
- Collection 管理（创建、删除、检查）
- 向量化操作（insert、update、delete）
- 搜索功能（search、filter）
- 性能和稳定性
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.search.qdrant_engine import QdrantVectorEngine, get_qdrant_engine


class TestQdrantVectorEngine:
    """Qdrant 向量搜索引擎测试"""

    @pytest.fixture
    def qdrant_engine(self):
        """创建 Qdrant 引擎实例（用于测试，不连接真实服务）"""
        return QdrantVectorEngine(
            qdrant_url="http://localhost:6333",
            model_name="BAAI/bge-small-zh-v1.5",
            device="cpu"
        )

    def test_initialization(self, qdrant_engine):
        """测试初始化"""
        assert qdrant_engine.qdrant_url == "http://localhost:6333"
        assert qdrant_engine.model_name == "BAAI/bge-small-zh-v1.5"
        assert qdrant_engine.VECTOR_DIM == 512
        assert qdrant_engine.COLLECTION_NAME == "memories"

    def test_index_config(self, qdrant_engine):
        """测试索引配置"""
        config = qdrant_engine.index_config

        assert "hnsw_config" in config
        assert config["hnsw_config"]["m"] == 16
        assert config["hnsw_config"]["ef_construct"] == 100

        assert "optimizers_config" in config
        assert config["optimizers_config"]["indexing_threshold"] == 20000

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_create_collection_new(self, mock_qdrant_client, qdrant_engine):
        """测试创建新的 Collection"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟 collections 列表为空
        mock_client.get_collections.return_value.collections = []

        # 执行创建
        result = qdrant_engine.create_collection(recreate=False)

        # 验证调用
        assert result is True
        mock_client.create_collection.assert_called_once()
        mock_client.get_collections.assert_called_once()

        # 验证参数
        call_args = mock_client.create_collection.call_args
        assert call_args[1]["collection_name"] == "memories"
        assert call_args[1]["vectors_config"].size == 512
        assert call_args[1]["vectors_config"].distance == Distance.COSINE

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_create_collection_exists(self, mock_qdrant_client, qdrant_engine):
        """测试 Collection 已存在的情况"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟 collection 已存在
        from qdrant_client.http.models import CollectionDescription
        mock_client.get_collections.return_value.collections = [
            CollectionDescription(name="memories")
        ]

        # 执行创建
        result = qdrant_engine.create_collection(recreate=False)

        # 验证不调用创建
        assert result is True
        mock_client.create_collection.assert_not_called()

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_create_collection_recreate(self, mock_qdrant_client, qdrant_engine):
        """测试重建 Collection"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟 collection 已存在
        from qdrant_client.http.models import CollectionDescription
        mock_client.get_collections.return_value.collections = [
            CollectionDescription(name="memories")
        ]

        # 执行重建
        result = qdrant_engine.create_collection(recreate=True)

        # 验证先删除后创建
        assert result is True
        mock_client.delete_collection.assert_called_once_with("memories")
        mock_client.create_collection.assert_called_once()

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_health_check_success(self, mock_qdrant_client, qdrant_engine):
        """测试健康检查成功"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟成功响应
        mock_client.get_collections.return_value = MagicMock()

        # 执行健康检查
        result = qdrant_engine.health_check()

        # 验证
        assert result is True
        mock_client.get_collections.assert_called_once()

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_health_check_failure(self, mock_qdrant_client, qdrant_engine):
        """测试健康检查失败"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟失败响应
        mock_client.get_collections.side_effect = Exception("Connection error")

        # 执行健康检查
        result = qdrant_engine.health_check()

        # 验证
        assert result is False

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_index_memories_empty(self, mock_qdrant_client, qdrant_engine):
        """测试索引空记忆列表"""
        result = qdrant_engine.index_memories([])
        assert result == 0

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_index_memories_success(self, mock_transformer, mock_qdrant_client, qdrant_engine):
        """测试成功索引记忆"""
        # 模拟嵌入模型
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [0.1] * 512
        mock_transformer.return_value = mock_encoder

        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 准备测试数据
        memories = [
            {
                "id": "test_001",
                "title": "测试记忆1",
                "summary": "测试摘要1",
                "category": "测试/分类",
                "tags": ["测试"],
                "price": 100,
                "purchase_count": 10,
                "avg_score": 4.5,
                "created_at": "2024-01-01"
            }
        ]

        # 执行索引
        result = qdrant_engine.index_memories(memories, batch_size=10)

        # 验证
        assert result == 1
        mock_encoder.encode.assert_called_once()
        mock_client.upsert.assert_called_once()

        # 验证插入的数据
        call_args = mock_client.upsert.call_args
        assert call_args[1]["collection_name"] == "memories"
        points = call_args[1]["points"]
        assert len(points) == 1
        assert points[0].id == "test_001"
        assert points[0].payload["title"] == "测试记忆1"
        assert points[0].payload["price"] == 100

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_index_memories_batch(self, mock_transformer, mock_qdrant_client, qdrant_engine):
        """测试批量索引"""
        # 模拟嵌入模型
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [0.1] * 512
        mock_transformer.return_value = mock_encoder

        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 准备测试数据（20 条，批量大小 10）
        memories = [
            {
                "id": f"test_{i:03d}",
                "title": f"测试记忆{i}",
                "summary": f"测试摘要{i}",
                "category": "测试/分类",
                "tags": ["测试"],
                "price": 100,
                "purchase_count": 10,
                "avg_score": 4.5,
                "created_at": "2024-01-01"
            }
            for i in range(1, 21)
        ]

        # 执行索引
        result = qdrant_engine.index_memories(memories, batch_size=10)

        # 验证
        assert result == 20
        assert mock_client.upsert.call_count == 2  # 2 批

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_search_empty_query(self, mock_transformer, mock_qdrant_client, qdrant_engine):
        """测试空查询"""
        result = qdrant_engine.search("")
        assert result == []

        result = qdrant_engine.search("   ")
        assert result == []

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_search_success(self, mock_transformer, mock_qdrant_client, qdrant_engine):
        """测试成功搜索"""
        # 模拟嵌入模型
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [0.1] * 512
        mock_transformer.return_value = mock_encoder

        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟搜索结果
        from qdrant_client.http.models import ScoredPoint
        mock_search_result = ScoredPoint(
            id="test_001",
            version=1,
            score=0.85,
            payload={
                "title": "测试记忆1",
                "summary": "测试摘要1",
                "category": "测试/分类",
                "tags": ["测试"],
                "price": 100
            }
        )
        mock_client.search.return_value = [mock_search_result]

        # 执行搜索
        result = qdrant_engine.search("测试查询", top_k=10)

        # 验证
        assert len(result) == 1
        memory_id, score, payload = result[0]
        assert memory_id == "test_001"
        assert score == 0.85
        assert payload["title"] == "测试记忆1"

        # 验证调用
        mock_encoder.encode.assert_called_once()
        mock_client.search.assert_called_once()

        # 验证搜索参数
        call_args = mock_client.search.call_args
        assert call_args[1]["collection_name"] == "memories"
        assert call_args[1]["limit"] == 10
        assert call_args[1]["score_threshold"] == 0.1

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_search_with_filters(self, mock_transformer, mock_qdrant_client, qdrant_engine):
        """测试带过滤条件的搜索"""
        # 模拟嵌入模型
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [0.1] * 512
        mock_transformer.return_value = mock_encoder

        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟搜索结果为空
        mock_client.search.return_value = []

        # 执行搜索（带过滤）
        result = qdrant_engine.search(
            "测试查询",
            filters={"category": "抖音/爆款"}
        )

        # 验证
        assert result == []

        # 验证搜索调用包含过滤器
        call_args = mock_client.search.call_args
        assert "query_filter" in call_args[1]
        assert call_args[1]["query_filter"] is not None

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_delete_memory_success(self, mock_qdrant_client, qdrant_engine):
        """测试成功删除记忆"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 执行删除
        result = qdrant_engine.delete_memory("test_001")

        # 验证
        assert result is True
        mock_client.delete.assert_called_once()

        # 验证删除参数
        call_args = mock_client.delete.call_args
        assert call_args[1]["collection_name"] == "memories"
        from qdrant_client.http.models import PointIdsList
        assert isinstance(call_args[1]["points_selector"], PointIdsList)
        assert call_args[1]["points_selector"].points == ["test_001"]

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_delete_memory_failure(self, mock_qdrant_client, qdrant_engine):
        """测试删除记忆失败"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟删除失败
        mock_client.delete.side_effect = Exception("Delete failed")

        # 执行删除
        result = qdrant_engine.delete_memory("test_001")

        # 验证
        assert result is False

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_delete_collection_success(self, mock_qdrant_client, qdrant_engine):
        """测试成功删除 Collection"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 执行删除
        result = qdrant_engine.delete_collection()

        # 验证
        assert result is True
        mock_client.delete_collection.assert_called_once_with("memories")

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_get_collection_info_success(self, mock_qdrant_client, qdrant_engine):
        """测试成功获取 Collection 信息"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟 Collection 信息
        mock_collection = MagicMock()
        mock_collection.config.params.vectors.size = 512
        mock_collection.points_count = 1000
        mock_collection.segments_count = 5
        mock_collection.status = "green"
        mock_collection.optimizer_status = "ok"
        mock_client.get_collection.return_value = mock_collection

        # 执行获取信息
        result = qdrant_engine.get_collection_info()

        # 验证
        assert result is not None
        assert result["name"] == 512
        assert result["points_count"] == 1000
        assert result["segments_count"] == 5
        assert result["status"] == "green"
        assert result["optimizer_status"] == "ok"

    @patch('app.search.qdrant_engine.QdrantClient')
    def test_get_collection_info_failure(self, mock_qdrant_client, qdrant_engine):
        """测试获取 Collection 信息失败"""
        # 模拟 Qdrant 客户端
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        qdrant_engine.client = mock_client

        # 模拟失败
        mock_client.get_collection.side_effect = Exception("Not found")

        # 执行获取信息
        result = qdrant_engine.get_collection_info()

        # 验证
        assert result is None


class TestQdrantEngineSingleton:
    """测试 Qdrant 引擎单例模式"""

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_get_qdrant_engine_singleton(self, mock_transformer, mock_qdrant_client):
        """测试获取单例实例"""
        # 清除全局单例
        import app.search.qdrant_engine as qdrant_engine_module
        qdrant_engine_module._qdrant_engine = None

        # 第一次获取
        engine1 = get_qdrant_engine()

        # 第二次获取
        engine2 = get_qdrant_engine()

        # 验证是同一个实例
        assert engine1 is engine2

    @patch('app.search.qdrant_engine.QdrantClient')
    @patch('app.search.qdrant_engine.SentenceTransformer')
    def test_get_qdrant_engine_different_params(self, mock_transformer, mock_qdrant_client):
        """测试不同参数时的行为"""
        # 清除全局单例
        import app.search.qdrant_engine as qdrant_engine_module
        qdrant_engine_module._qdrant_engine = None

        # 使用默认参数
        engine1 = get_qdrant_engine()
        assert engine1.qdrant_url == "http://localhost:6333"

        # 使用自定义参数（应该返回同一个实例）
        engine2 = get_qdrant_engine(qdrant_url="http://custom:6333")
        assert engine1 is engine2
        # 注意：单例模式不会更新参数，这是预期行为
