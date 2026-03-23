"""
外部数据源服务 - 抽象层和数据源管理
支持Google Drive、Gmail、Notion、OneDrive、GitHub等外部数据源的集成
"""
from typing import Optional, List, Dict, Any, Type
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """数据源类型"""
    GOOGLE_DRIVE = "google_drive"
    GMAIL = "gmail"
    NOTION = "notion"
    ONEDRIVE = "onedrive"
    GITHUB = "github"
    LOCAL_FOLDER = "local_folder"
    CUSTOM = "custom"


class SyncStatus(str, Enum):
    """同步状态"""
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    COMPLETED = "completed"


class DocumentType(str, Enum):
    """文档类型"""
    PDF = "pdf"
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"
    CODE = "code"
    EMAIL = "email"
    NOTE = "note"
    UNKNOWN = "unknown"


class Document:
    """统一文档模型"""
    def __init__(
        self,
        doc_id: str,
        source_type: SourceType,
        title: str,
        content: str,
        doc_type: DocumentType,
        metadata: Dict[str, Any],
        url: Optional[str] = None,
        author: Optional[str] = None,
        created_at: Optional[datetime] = None,
        modified_at: Optional[datetime] = None,
    ):
        self.doc_id = doc_id
        self.source_type = source_type
        self.title = title
        self.content = content
        self.doc_type = doc_type
        self.metadata = metadata
        self.url = url
        self.author = author
        self.created_at = created_at or datetime.utcnow()
        self.modified_at = modified_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "doc_id": self.doc_id,
            "source_type": self.source_type.value,
            "title": self.title,
            "content": self.content,
            "doc_type": self.doc_type.value,
            "metadata": self.metadata,
            "url": self.url,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """从字典创建"""
        return cls(
            doc_id=data["doc_id"],
            source_type=SourceType(data["source_type"]),
            title=data["title"],
            content=data["content"],
            doc_type=DocumentType(data["doc_type"]),
            metadata=data["metadata"],
            url=data.get("url"),
            author=data.get("author"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            modified_at=datetime.fromisoformat(data["modified_at"]) if data.get("modified_at") else None,
        )


class File:
    """统一文件模型"""
    def __init__(
        self,
        file_id: str,
        source_type: SourceType,
        name: str,
        size: int,
        mime_type: str,
        metadata: Dict[str, Any],
        url: Optional[str] = None,
        download_url: Optional[str] = None,
        created_at: Optional[datetime] = None,
        modified_at: Optional[datetime] = None,
    ):
        self.file_id = file_id
        self.source_type = source_type
        self.name = name
        self.size = size
        self.mime_type = mime_type
        self.metadata = metadata
        self.url = url
        self.download_url = download_url
        self.created_at = created_at or datetime.utcnow()
        self.modified_at = modified_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "file_id": self.file_id,
            "source_type": self.source_type.value,
            "name": self.name,
            "size": self.size,
            "mime_type": self.mime_type,
            "metadata": self.metadata,
            "url": self.url,
            "download_url": self.download_url,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


class SourceConnection:
    """数据源连接配置"""
    def __init__(
        self,
        source_id: str,
        source_type: SourceType,
        config: Dict[str, Any],
        enabled: bool = True,
        last_sync: Optional[datetime] = None,
        sync_status: SyncStatus = SyncStatus.IDLE,
    ):
        self.source_id = source_id
        self.source_type = source_type
        self.config = config
        self.enabled = enabled
        self.last_sync = last_sync
        self.sync_status = sync_status

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        safe_config = {k: v for k, v in self.config.items() if k not in ["access_token", "refresh_token", "client_secret"]}
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "config": safe_config,
            "enabled": self.enabled,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_status": self.sync_status.value,
        }


class SourceAdapter:
    """数据源适配器抽象基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化适配器"""
        raise NotImplementedError

    async def connect(self) -> bool:
        """连接到数据源"""
        raise NotImplementedError

    async def disconnect(self) -> bool:
        """断开连接"""
        raise NotImplementedError

    async def list_files(self, folder_id: Optional[str] = None, limit: int = 100) -> List[File]:
        """列出文件"""
        raise NotImplementedError

    async def get_file(self, file_id: str) -> Optional[File]:
        """获取文件信息"""
        raise NotImplementedError

    async def download_file(self, file_id: str) -> bytes:
        """下载文件内容"""
        raise NotImplementedError

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出文档"""
        raise NotImplementedError

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        raise NotImplementedError

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索文档"""
        raise NotImplementedError

    async def get_webhook_url(self) -> str:
        """获取Webhook URL"""
        raise NotImplementedError

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证Webhook签名"""
        raise NotImplementedError

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """处理Webhook事件，返回受影响的文档"""
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._initialized


class ExternalSourceService:
    """外部数据源服务"""

    def __init__(self):
        self._adapters: Dict[str, SourceAdapter] = {}
        self._connections: Dict[str, SourceConnection] = {}
        self._adapter_classes: Dict[SourceType, Type[SourceAdapter]] = {}

    def register_adapter(self, source_type: SourceType, adapter_class: Type[SourceAdapter]):
        """注册适配器类"""
        self._adapter_classes[source_type] = adapter_class
        logger.info(f"Registered adapter for {source_type.value}")

    async def connect_source(self, source_id: str, source_type: SourceType, config: Dict[str, Any]) -> SourceConnection:
        """连接数据源"""
        if source_type not in self._adapter_classes:
            raise ValueError(f"Unsupported source type: {source_type.value}")

        adapter_class = self._adapter_classes[source_type]
        adapter = adapter_class(config)

        await adapter.initialize()
        await adapter.connect()

        connection = SourceConnection(
            source_id=source_id,
            source_type=source_type,
            config=config,
            enabled=True,
            sync_status=SyncStatus.IDLE,
        )

        self._adapters[source_id] = adapter
        self._connections[source_id] = connection

        logger.info(f"Connected to source {source_id} ({source_type.value})")
        return connection

    async def disconnect_source(self, source_id: str) -> bool:
        """断开数据源"""
        if source_id not in self._adapters:
            return False

        adapter = self._adapters[source_id]
        await adapter.disconnect()

        del self._adapters[source_id]
        del self._connections[source_id]

        logger.info(f"Disconnected from source {source_id}")
        return True

    async def sync_source(self, source_id: str, force: bool = False) -> List[Document]:
        """同步数据源"""
        if source_id not in self._adapters:
            raise ValueError(f"Source not connected: {source_id}")

        connection = self._connections[source_id]

        if connection.sync_status == SyncStatus.SYNCING and not force:
            raise ValueError(f"Source is already syncing: {source_id}")

        connection.sync_status = SyncStatus.SYNCING

        try:
            adapter = self._adapters[source_id]
            documents = await adapter.list_documents(limit=1000)

            connection.last_sync = datetime.utcnow()
            connection.sync_status = SyncStatus.COMPLETED

            logger.info(f"Synced {len(documents)} documents from {source_id}")
            return documents

        except Exception as e:
            connection.sync_status = SyncStatus.ERROR
            logger.error(f"Failed to sync source {source_id}: {e}")
            raise

    async def list_sources(self) -> List[SourceConnection]:
        """列出所有数据源"""
        return list(self._connections.values())

    async def get_source_status(self, source_id: str) -> Optional[SourceConnection]:
        """获取数据源状态"""
        return self._connections.get(source_id)

    async def search_all_sources(self, query: str, limit: int = 10) -> List[Document]:
        """跨所有数据源搜索"""
        all_results: List[Document] = []

        tasks = []
        for source_id, adapter in self._adapters.items():
            if self._connections[source_id].enabled:
                tasks.append(adapter.search(query, limit))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Search failed: {result}")

        return all_results[:limit]

    async def handle_webhook(self, source_id: str, payload: Dict[str, Any], signature: str) -> List[Document]:
        """处理Webhook"""
        if source_id not in self._adapters:
            raise ValueError(f"Source not connected: {source_id}")

        adapter = self._adapters[source_id]

        if not await adapter.validate_webhook(payload, signature):
            raise ValueError("Invalid webhook signature")

        return await adapter.handle_webhook(payload)

    async def list_files(self, source_id: str, folder_id: Optional[str] = None, limit: int = 100) -> List[File]:
        """列出文件"""
        if source_id not in self._adapters:
            raise ValueError(f"Source not connected: {source_id}")

        adapter = self._adapters[source_id]
        return await adapter.list_files(folder_id=folder_id, limit=limit)

    async def download_file(self, source_id: str, file_id: str) -> bytes:
        """下载文件"""
        if source_id not in self._adapters:
            raise ValueError(f"Source not connected: {source_id}")

        adapter = self._adapters[source_id]
        return await adapter.download_file(file_id)


# 全局服务实例
external_source_service = ExternalSourceService()


def register_all_adapters():
    """注册所有内置适配器（容错：单个适配器导入失败不影响其他）"""
    adapters_to_register = [
        (SourceType.GOOGLE_DRIVE, "app.adapters.google_drive_adapter", "GoogleDriveAdapter"),
        (SourceType.GMAIL, "app.adapters.gmail_adapter", "GmailAdapter"),
        (SourceType.NOTION, "app.adapters.notion_adapter", "NotionAdapter"),
        (SourceType.ONEDRIVE, "app.adapters.onedrive_adapter", "OneDriveAdapter"),
        (SourceType.GITHUB, "app.adapters.github_adapter", "GitHubAdapter"),
        (SourceType.LOCAL_FOLDER, "app.adapters.local_folder_adapter", "LocalFolderAdapter"),
    ]

    registered = 0
    for source_type, module_path, class_name in adapters_to_register:
        try:
            import importlib
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            external_source_service.register_adapter(source_type, adapter_class)
            registered += 1
        except Exception as e:
            logger.warning(f"Failed to register adapter {class_name}: {e}")

    logger.info(f"Registered {registered}/{len(adapters_to_register)} external source adapters")
