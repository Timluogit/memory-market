"""
本地文件夹适配器
支持本地文件系统遍历、文件读取、变更检测
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import logging
import os
import mimetypes
import hashlib

from ..services.external_source_service import (
    SourceAdapter,
    SourceType,
    File,
    Document,
    DocumentType,
)

logger = logging.getLogger(__name__)


# 支持的文件扩展名映射
EXTENSION_TO_DOC_TYPE = {
    ".pdf": DocumentType.PDF,
    ".doc": DocumentType.TEXT,
    ".docx": DocumentType.TEXT,
    ".txt": DocumentType.TEXT,
    ".md": DocumentType.TEXT,
    ".csv": DocumentType.TEXT,
    ".json": DocumentType.TEXT,
    ".xml": DocumentType.TEXT,
    ".yaml": DocumentType.TEXT,
    ".yml": DocumentType.TEXT,
    ".html": DocumentType.TEXT,
    ".htm": DocumentType.TEXT,
    ".jpg": DocumentType.IMAGE,
    ".jpeg": DocumentType.IMAGE,
    ".png": DocumentType.IMAGE,
    ".gif": DocumentType.IMAGE,
    ".webp": DocumentType.IMAGE,
    ".bmp": DocumentType.IMAGE,
    ".mp4": DocumentType.VIDEO,
    ".mov": DocumentType.VIDEO,
    ".avi": DocumentType.VIDEO,
    ".mkv": DocumentType.VIDEO,
    ".py": DocumentType.CODE,
    ".js": DocumentType.CODE,
    ".ts": DocumentType.CODE,
    ".jsx": DocumentType.CODE,
    ".tsx": DocumentType.CODE,
    ".java": DocumentType.CODE,
    ".c": DocumentType.CODE,
    ".cpp": DocumentType.CODE,
    ".h": DocumentType.CODE,
    ".go": DocumentType.CODE,
    ".rs": DocumentType.CODE,
    ".rb": DocumentType.CODE,
    ".php": DocumentType.CODE,
    ".swift": DocumentType.CODE,
    ".kt": DocumentType.CODE,
    ".scala": DocumentType.CODE,
    ".cs": DocumentType.CODE,
    ".sh": DocumentType.CODE,
    ".sql": DocumentType.CODE,
}


class LocalFolderAdapter(SourceAdapter):
    """本地文件夹适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.root_path = Path(config.get("path", ""))
        self.ignore_patterns = set(config.get("ignore_patterns", [
            "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv",
            ".idea", ".vscode", ".DS_Store", "*.pyc", "*.pyo",
        ]))
        self.max_file_size = config.get("max_file_size", 50 * 1024 * 1024)  # 50MB
        self._file_hashes: Dict[str, str] = {}

    async def initialize(self) -> bool:
        """初始化适配器"""
        try:
            if not self.root_path.exists():
                raise ValueError(f"Path does not exist: {self.root_path}")
            if not self.root_path.is_dir():
                raise ValueError(f"Path is not a directory: {self.root_path}")

            self._initialized = True
            logger.info(f"Local folder adapter initialized: {self.root_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize local folder adapter: {e}")
            return False

    async def connect(self) -> bool:
        """连接到本地文件夹"""
        try:
            # 验证目录可读
            list(self.root_path.iterdir())
            logger.info(f"Connected to local folder: {self.root_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to local folder: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        self._initialized = False
        self._file_hashes.clear()
        logger.info("Disconnected from local folder")
        return True

    def _should_ignore(self, path: Path) -> bool:
        """检查路径是否应该被忽略"""
        for part in path.parts:
            if part in self.ignore_patterns:
                return True
            # 通配符匹配
            for pattern in self.ignore_patterns:
                if pattern.startswith("*") and part.endswith(pattern[1:]):
                    return True
        return False

    def _get_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def _get_doc_type(self, file_path: Path) -> DocumentType:
        """根据扩展名获取文档类型"""
        suffix = file_path.suffix.lower()
        return EXTENSION_TO_DOC_TYPE.get(suffix, DocumentType.UNKNOWN)

    async def _walk_directory(
        self,
        directory: Path,
        limit: int,
        current_count: int = 0,
    ) -> List[Dict[str, Any]]:
        """递归遍历目录"""
        items = []

        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
            return items

        for entry in entries:
            if current_count + len(items) >= limit:
                break

            if self._should_ignore(entry):
                continue

            if entry.is_dir():
                sub_items = await self._walk_directory(entry, limit, current_count + len(items))
                items.extend(sub_items)
            elif entry.is_file():
                try:
                    stat = entry.stat()
                    if stat.st_size > self.max_file_size:
                        continue

                    items.append({
                        "path": entry,
                        "stat": stat,
                    })
                except (OSError, PermissionError):
                    continue

        return items

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        limit: int = 100,
        query: Optional[str] = None,
    ) -> List[File]:
        """列出文件"""
        try:
            target_dir = self.root_path
            if folder_id:
                target_dir = Path(folder_id)
                if not target_dir.is_absolute():
                    target_dir = self.root_path / folder_id

            if not target_dir.exists():
                return []

            raw_items = await self._walk_directory(target_dir, limit)

            files = []
            for item in raw_items:
                path = item["path"]
                stat = item["stat"]

                # 查询过滤
                if query and query.lower() not in path.name.lower():
                    continue

                mime_type, _ = mimetypes.guess_type(str(path))
                rel_path = str(path.relative_to(self.root_path))

                files.append(File(
                    file_id=rel_path,
                    source_type=SourceType.CUSTOM,
                    name=path.name,
                    size=stat.st_size,
                    mime_type=mime_type or "application/octet-stream",
                    metadata={
                        "absolute_path": str(path),
                        "relative_path": rel_path,
                        "extension": path.suffix,
                        "parent": str(path.parent.relative_to(self.root_path)),
                    },
                    url=f"file://{path}",
                    created_at=datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_ctime),
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                ))

            logger.info(f"Listed {len(files)} files from local folder")
            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    async def get_file(self, file_id: str) -> Optional[File]:
        """获取文件信息"""
        try:
            file_path = self.root_path / file_id
            if not file_path.exists() or not file_path.is_file():
                return None

            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))

            return File(
                file_id=file_id,
                source_type=SourceType.CUSTOM,
                name=file_path.name,
                size=stat.st_size,
                mime_type=mime_type or "application/octet-stream",
                metadata={
                    "absolute_path": str(file_path),
                    "relative_path": file_id,
                    "extension": file_path.suffix,
                },
                url=f"file://{file_path}",
                created_at=datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )

        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            return None

    async def download_file(self, file_id: str) -> bytes:
        """下载文件内容"""
        try:
            file_path = self.root_path / file_id
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_id}")

            return file_path.read_bytes()

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出文档"""
        try:
            raw_items = await self._walk_directory(self.root_path, limit)

            documents = []
            for item in raw_items:
                path = item["path"]
                stat = item["stat"]

                # 只处理支持的文档类型
                doc_type = self._get_doc_type(path)
                if doc_type == DocumentType.UNKNOWN:
                    continue

                rel_path = str(path.relative_to(self.root_path))
                mime_type, _ = mimetypes.guess_type(str(path))

                documents.append(Document(
                    doc_id=rel_path,
                    source_type=SourceType.CUSTOM,
                    title=path.name,
                    content="",  # 需要下载后处理
                    doc_type=doc_type,
                    metadata={
                        "absolute_path": str(path),
                        "relative_path": rel_path,
                        "mime_type": mime_type,
                        "size": stat.st_size,
                        "extension": path.suffix,
                    },
                    url=f"file://{path}",
                    author=None,
                    created_at=datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_ctime),
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                ))

            logger.info(f"Listed {len(documents)} documents from local folder")
            return documents

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档（包含内容）"""
        try:
            file_path = self.root_path / doc_id
            if not file_path.exists() or not file_path.is_file():
                return None

            stat = file_path.stat()
            doc_type = self._get_doc_type(file_path)
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # 对于文本/代码类型，读取内容
            content = ""
            if doc_type in (DocumentType.TEXT, DocumentType.CODE):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            return Document(
                doc_id=doc_id,
                source_type=SourceType.CUSTOM,
                title=file_path.name,
                content=content,
                doc_type=doc_type,
                metadata={
                    "absolute_path": str(file_path),
                    "relative_path": doc_id,
                    "mime_type": mime_type,
                    "size": stat.st_size,
                    "extension": file_path.suffix,
                },
                url=f"file://{file_path}",
                author=None,
                created_at=datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索文档（基于文件名和内容关键词匹配）"""
        try:
            query_lower = query.lower()
            all_docs = await self.list_documents(limit=500)

            scored_docs = []
            for doc in all_docs:
                score = 0.0

                # 文件名匹配
                if query_lower in doc.title.lower():
                    score += 1.0

                # 路径匹配
                rel_path = doc.metadata.get("relative_path", "")
                if query_lower in rel_path.lower():
                    score += 0.5

                if score > 0:
                    scored_docs.append((score, doc))

            # 按分数排序
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            results = [doc for _, doc in scored_docs[:limit]]
            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise

    async def get_webhook_url(self) -> str:
        """本地文件夹不支持Webhook"""
        return ""

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """本地文件夹不支持Webhook"""
        return False

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """本地文件夹不支持Webhook"""
        return []

    async def detect_changes(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """检测文件变更"""
        try:
            changes = []
            raw_items = await self._walk_directory(self.root_path, limit=10000)

            for item in raw_items:
                path = item["path"]
                stat = item["stat"]
                rel_path = str(path.relative_to(self.root_path))

                # 计算当前哈希
                current_hash = self._get_file_hash(path)
                previous_hash = self._file_hashes.get(rel_path)

                change_type = None
                if previous_hash is None:
                    change_type = "created"
                elif previous_hash != current_hash:
                    change_type = "modified"

                # 按时间过滤
                if since:
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    if mtime < since and change_type != "created":
                        continue

                if change_type:
                    changes.append({
                        "path": rel_path,
                        "change_type": change_type,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })

                # 更新哈希缓存
                self._file_hashes[rel_path] = current_hash

            # 检测删除的文件
            current_paths = {
                str(item["path"].relative_to(self.root_path))
                for item in raw_items
            }
            for cached_path in list(self._file_hashes.keys()):
                if cached_path not in current_paths:
                    changes.append({
                        "path": cached_path,
                        "change_type": "deleted",
                        "size": 0,
                        "modified_at": datetime.utcnow().isoformat(),
                    })
                    del self._file_hashes[cached_path]

            logger.info(f"Detected {len(changes)} changes since {since}")
            return changes

        except Exception as e:
            logger.error(f"Failed to detect changes: {e}")
            raise
