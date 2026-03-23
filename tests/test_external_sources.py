"""
外部数据源集成测试
测试适配器、服务、API端点、搜索集成
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.external_source_service import (
    ExternalSourceService,
    SourceType,
    SyncStatus,
    Document,
    DocumentType,
    File,
    SourceConnection,
    SourceAdapter,
    register_all_adapters,
    external_source_service,
)
from app.adapters.local_folder_adapter import LocalFolderAdapter
from app.services.document_processor import DocumentProcessor, document_processor
from app.services.webhook_service import WebhookService, WebhookEvent, webhook_service
from app.search.external_search import ExternalSearchEngine, external_search_engine


# ============ 数据模型测试 ============

class TestDataModels:
    """数据模型测试"""

    def test_document_to_dict(self):
        """测试Document转字典"""
        doc = Document(
            doc_id="test-1",
            source_type=SourceType.GOOGLE_DRIVE,
            title="Test Doc",
            content="Hello World",
            doc_type=DocumentType.TEXT,
            metadata={"key": "value"},
            url="https://example.com",
            author="test@example.com",
        )

        d = doc.to_dict()
        assert d["doc_id"] == "test-1"
        assert d["source_type"] == "google_drive"
        assert d["title"] == "Test Doc"
        assert d["content"] == "Hello World"
        assert d["doc_type"] == "text"
        assert d["metadata"] == {"key": "value"}

    def test_document_from_dict(self):
        """测试从字典创建Document"""
        data = {
            "doc_id": "test-2",
            "source_type": "gmail",
            "title": "Email",
            "content": "Email body",
            "doc_type": "email",
            "metadata": {"from": "a@b.com"},
            "url": None,
            "author": "sender",
            "created_at": "2024-01-01T00:00:00",
            "modified_at": "2024-01-01T00:00:00",
        }

        doc = Document.from_dict(data)
        assert doc.doc_id == "test-2"
        assert doc.source_type == SourceType.GMAIL
        assert doc.doc_type == DocumentType.EMAIL

    def test_file_to_dict(self):
        """测试File转字典"""
        f = File(
            file_id="file-1",
            source_type=SourceType.ONEDRIVE,
            name="test.pdf",
            size=1024,
            mime_type="application/pdf",
            metadata={},
        )

        d = f.to_dict()
        assert d["file_id"] == "file-1"
        assert d["name"] == "test.pdf"
        assert d["size"] == 1024

    def test_source_connection_to_dict_hides_secrets(self):
        """测试SourceConnection隐藏敏感信息"""
        conn = SourceConnection(
            source_id="src-1",
            source_type=SourceType.GMAIL,
            config={
                "access_token": "secret-token",
                "refresh_token": "secret-refresh",
                "client_secret": "secret-client",
                "client_id": "public-id",
            },
        )

        d = conn.to_dict()
        assert "access_token" not in d["config"]
        assert "refresh_token" not in d["config"]
        assert "client_secret" not in d["config"]
        assert d["config"]["client_id"] == "public-id"


# ============ 本地文件夹适配器测试 ============

class TestLocalFolderAdapter:
    """本地文件夹适配器测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            Path(tmpdir, "test.txt").write_text("Hello World")
            Path(tmpdir, "test.md").write_text("# Markdown")
            Path(tmpdir, "test.py").write_text("print('hello')")

            sub_dir = Path(tmpdir, "subdir")
            sub_dir.mkdir()
            Path(sub_dir, "nested.txt").write_text("Nested content")

            # 创建应被忽略的目录
            ignored = Path(tmpdir, "__pycache__")
            ignored.mkdir()
            Path(ignored, "cache.pyc").write_bytes(b"cache")

            yield tmpdir

    @pytest.mark.asyncio
    async def test_initialize(self, temp_dir):
        """测试初始化"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        result = await adapter.initialize()
        assert result is True
        assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_nonexistent(self):
        """测试初始化不存在的路径"""
        adapter = LocalFolderAdapter({"path": "/nonexistent/path"})
        result = await adapter.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect(self, temp_dir):
        """测试连接"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()
        result = await adapter.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_list_files(self, temp_dir):
        """测试列出文件"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        files = await adapter.list_files(limit=100)
        # 应包含 test.txt, test.md, test.py, subdir/nested.txt
        # 不应包含 __pycache__/cache.pyc
        file_names = [f.name for f in files]
        assert "test.txt" in file_names
        assert "test.md" in file_names
        assert "test.py" in file_names
        assert "nested.txt" in file_names
        assert "cache.pyc" not in file_names

    @pytest.mark.asyncio
    async def test_list_files_with_query(self, temp_dir):
        """测试按查询列出文件"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        files = await adapter.list_files(limit=100, query="test")
        file_names = [f.name for f in files]
        assert "test.txt" in file_names
        assert "test.py" in file_names
        # nested.txt 不包含 "test"
        assert "nested.txt" not in file_names

    @pytest.mark.asyncio
    async def test_get_file(self, temp_dir):
        """测试获取文件"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        file = await adapter.get_file("test.txt")
        assert file is not None
        assert file.name == "test.txt"
        assert file.size > 0
        assert file.source_type == SourceType.CUSTOM

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, temp_dir):
        """测试获取不存在的文件"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        file = await adapter.get_file("nonexistent.txt")
        assert file is None

    @pytest.mark.asyncio
    async def test_download_file(self, temp_dir):
        """测试下载文件"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        content = await adapter.download_file("test.txt")
        assert content == b"Hello World"

    @pytest.mark.asyncio
    async def test_list_documents(self, temp_dir):
        """测试列出文档"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        docs = await adapter.list_documents(limit=100)
        doc_ids = [d.doc_id for d in docs]
        assert "test.txt" in doc_ids
        assert "test.md" in doc_ids
        assert "test.py" in doc_ids

        # 验证文档类型
        for doc in docs:
            if doc.title == "test.txt":
                assert doc.doc_type == DocumentType.TEXT
            elif doc.title == "test.py":
                assert doc.doc_type == DocumentType.CODE

    @pytest.mark.asyncio
    async def test_get_document_with_content(self, temp_dir):
        """测试获取文档（含内容）"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        doc = await adapter.get_document("test.txt")
        assert doc is not None
        assert doc.content == "Hello World"
        assert doc.doc_type == DocumentType.TEXT

    @pytest.mark.asyncio
    async def test_search(self, temp_dir):
        """测试搜索"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        results = await adapter.search("test", limit=10)
        assert len(results) > 0
        names = [r.title for r in results]
        assert any("test" in n.lower() for n in names)

    @pytest.mark.asyncio
    async def test_detect_changes(self, temp_dir):
        """测试变更检测"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()

        # 首次检测：所有文件都是 "created"
        changes = await adapter.detect_changes()
        assert len(changes) > 0
        change_types = [c["change_type"] for c in changes]
        assert all(ct == "created" for ct in change_types)

        # 修改文件后再检测
        Path(temp_dir, "test.txt").write_text("Modified content")
        changes = await adapter.detect_changes()
        modified = [c for c in changes if c["change_type"] == "modified"]
        assert len(modified) > 0

    @pytest.mark.asyncio
    async def test_disconnect(self, temp_dir):
        """测试断开连接"""
        adapter = LocalFolderAdapter({"path": temp_dir})
        await adapter.initialize()
        result = await adapter.disconnect()
        assert result is True
        assert adapter._initialized is False


# ============ 外部数据源服务测试 ============

class TestExternalSourceService:
    """外部数据源服务测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "file.txt").write_text("content")
            yield tmpdir

    @pytest.mark.asyncio
    async def test_register_adapter(self):
        """测试注册适配器"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)
        assert SourceType.LOCAL_FOLDER in service._adapter_classes

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, temp_dir):
        """测试连接和断开数据源"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)

        conn = await service.connect_source(
            source_id="test-local",
            source_type=SourceType.LOCAL_FOLDER,
            config={"path": temp_dir},
        )

        assert conn.source_id == "test-local"
        assert conn.source_type == SourceType.LOCAL_FOLDER
        assert conn.sync_status == SyncStatus.IDLE

        # 断开
        result = await service.disconnect_source("test-local")
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self):
        """测试断开不存在的数据源"""
        service = ExternalSourceService()
        result = await service.disconnect_source("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_sync_source(self, temp_dir):
        """测试同步数据源"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)

        await service.connect_source(
            source_id="test-sync",
            source_type=SourceType.LOCAL_FOLDER,
            config={"path": temp_dir},
        )

        docs = await service.sync_source("test-sync")
        assert len(docs) > 0

        conn = await service.get_source_status("test-sync")
        assert conn.sync_status == SyncStatus.COMPLETED
        assert conn.last_sync is not None

    @pytest.mark.asyncio
    async def test_list_sources(self, temp_dir):
        """测试列出数据源"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)

        await service.connect_source(
            source_id="src-1",
            source_type=SourceType.LOCAL_FOLDER,
            config={"path": temp_dir},
        )

        sources = await service.list_sources()
        assert len(sources) == 1
        assert sources[0].source_id == "src-1"

    @pytest.mark.asyncio
    async def test_list_files(self, temp_dir):
        """测试列出文件"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)

        await service.connect_source(
            source_id="src-files",
            source_type=SourceType.LOCAL_FOLDER,
            config={"path": temp_dir},
        )

        files = await service.list_files("src-files")
        assert len(files) > 0

    @pytest.mark.asyncio
    async def test_search_all_sources(self, temp_dir):
        """测试跨数据源搜索"""
        service = ExternalSourceService()
        service.register_adapter(SourceType.LOCAL_FOLDER, LocalFolderAdapter)

        await service.connect_source(
            source_id="src-search",
            source_type=SourceType.LOCAL_FOLDER,
            config={"path": temp_dir},
        )

        results = await service.search_all_sources("file")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_unsupported_source_type(self):
        """测试不支持的数据源类型"""
        service = ExternalSourceService()
        with pytest.raises(ValueError, match="Unsupported source type"):
            await service.connect_source(
                source_id="bad",
                source_type=SourceType.GMAIL,
                config={},
            )


# ============ 文档处理器测试 ============

class TestDocumentProcessor:
    """文档处理器测试"""

    @pytest.mark.asyncio
    async def test_process_text(self):
        """测试处理文本"""
        processor = DocumentProcessor()
        content = b"Hello World\n\nThis is a test."
        result = await processor.process(content, "text/plain", {})

        assert result["text"] == "Hello World\n\nThis is a test."
        assert result["doc_type"] == "text"
        assert "hash" in result
        assert "processing_time" in result

    @pytest.mark.asyncio
    async def test_process_json(self):
        """测试处理JSON"""
        processor = DocumentProcessor()
        content = b'{"key": "value"}'
        result = await processor.process(content, "application/json", {})

        assert '"key"' in result["text"]
        assert result["doc_type"] == "text"

    @pytest.mark.asyncio
    async def test_process_code_python(self):
        """测试处理Python代码"""
        processor = DocumentProcessor()
        code = b"""
def hello():
    '''Say hello'''
    print("Hello")

class MyClass:
    pass
"""
        result = await processor.process(code, "text/x-python", {})

        assert result["doc_type"] == "code" or result["doc_type"] == "text"
        assert "def hello" in result["text"]

    @pytest.mark.asyncio
    async def test_chunk_text(self):
        """测试文本分块"""
        processor = DocumentProcessor()
        long_text = "\n\n".join([f"Paragraph {i} with some content." for i in range(50)])
        chunks = processor._chunk_text(long_text, max_chars=200)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["char_count"] <= 250  # 允许一些余量

    @pytest.mark.asyncio
    async def test_process_image_without_pil(self):
        """测试处理图片（无PIL）"""
        processor = DocumentProcessor()
        # 伪造的图片数据
        content = b"\x89PNG\r\n\x1a\n"
        result = await processor.process(content, "image/png", {})

        # 无PIL时应返回空文本
        assert result["doc_type"] == "image"


# ============ Webhook服务测试 ============

class TestWebhookService:
    """Webhook服务测试"""

    @pytest.mark.asyncio
    async def test_webhook_event_to_dict(self):
        """测试WebhookEvent转字典"""
        event = WebhookEvent(
            event_id="evt-1",
            source_id="src-1",
            event_type="file.updated",
            payload={"file_id": "123"},
            received_at=datetime.utcnow(),
        )

        d = event.to_dict()
        assert d["event_id"] == "evt-1"
        assert d["source_id"] == "src-1"
        assert d["event_type"] == "file.updated"
        assert d["status"] == "pending"

    def test_webhook_stats(self):
        """测试Webhook统计"""
        service = WebhookService()
        stats = service.get_stats()

        assert stats["pending_count"] == 0
        assert stats["processing_count"] == 0
        assert stats["total_count"] == 0


# ============ 搜索引擎测试 ============

class TestExternalSearchEngine:
    """外部搜索引擎测试"""

    @pytest.mark.asyncio
    async def test_calculate_score_title_match(self):
        """测试标题匹配计分"""
        engine = ExternalSearchEngine()
        doc = Document(
            doc_id="test",
            source_type=SourceType.CUSTOM,
            title="Python Tutorial",
            content="Learn Python programming",
            doc_type=DocumentType.TEXT,
            metadata={"tags": ["python"]},
            author="author",
        )

        score = engine._calculate_score("python", doc)
        assert score > 0

    @pytest.mark.asyncio
    async def test_calculate_score_no_match(self):
        """测试无匹配计分"""
        engine = ExternalSearchEngine()
        doc = Document(
            doc_id="test",
            source_type=SourceType.CUSTOM,
            title="Unrelated Doc",
            content="Nothing here",
            doc_type=DocumentType.TEXT,
            metadata={},
        )

        score = engine._calculate_score("xyz123", doc)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_cache(self):
        """测试缓存机制"""
        engine = ExternalSearchEngine()

        assert engine._is_cache_valid("test") is False

        engine._cache["test"] = []
        engine._cache_timestamps["test"] = datetime.utcnow()

        assert engine._is_cache_valid("test") is True

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """测试清理缓存"""
        engine = ExternalSearchEngine()
        engine._cache["test"] = []
        engine._cache_timestamps["test"] = datetime.utcnow()

        await engine.clear_cache("test")
        assert "test" not in engine._cache

    def test_cache_stats(self):
        """测试缓存统计"""
        engine = ExternalSearchEngine()
        stats = engine.get_cache_stats()
        assert stats["cached_queries"] == 0
        assert stats["cache_ttl_seconds"] == 300


# ============ 适配器注册测试 ============

class TestAdapterRegistration:
    """适配器注册测试"""

    def test_register_all_adapters(self):
        """测试注册所有适配器"""
        register_all_adapters()

        registered_types = set(external_source_service._adapter_classes.keys())
        expected = {
            SourceType.GOOGLE_DRIVE,
            SourceType.GMAIL,
            SourceType.NOTION,
            SourceType.ONEDRIVE,
            SourceType.GITHUB,
            SourceType.LOCAL_FOLDER,
        }
        assert expected.issubset(registered_types)


# ============ API端点测试 ============

class TestExternalSourcesAPI:
    """外部数据源API测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_list_sources_empty(self, client):
        """测试列出空数据源"""
        response = client.get("/api/external-sources")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0

    def test_connect_invalid_source_type(self, client):
        """测试连接无效数据源类型"""
        response = client.post("/api/external-sources/connect", json={
            "source_type": "invalid_type",
            "config": {},
        })
        assert response.status_code == 400

    def test_disconnect_nonexistent(self, client):
        """测试断开不存在的数据源"""
        response = client.delete("/api/external-sources/nonexistent/disconnect")
        assert response.status_code == 404
