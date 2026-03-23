"""
Google Drive 适配器
支持文件列表、下载、元数据、Webhook
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import aiohttp
import json

from ..services.external_source_service import (
    SourceAdapter,
    SourceType,
    File,
    Document,
    DocumentType,
)

logger = logging.getLogger(__name__)


class GoogleDriveAdapter(SourceAdapter):
    """Google Drive API 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.base_url = "https://www.googleapis.com/drive/v3"
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> bool:
        """初始化适配器"""
        try:
            if not self.access_token:
                raise ValueError("access_token is required")

            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            self._initialized = True
            logger.info("Google Drive adapter initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive adapter: {e}")
            return False

    async def connect(self) -> bool:
        """连接到Google Drive（验证token）"""
        try:
            await self._about()
            logger.info("Connected to Google Drive")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Google Drive: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False
        logger.info("Disconnected from Google Drive")
        return True

    async def _about(self) -> Dict[str, Any]:
        """获取Drive信息"""
        async with self._session.get(f"{self.base_url}/about") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        limit: int = 100,
        query: Optional[str] = None,
    ) -> List[File]:
        """列出文件"""
        try:
            # 构建查询
            q = "trashed=false"
            if folder_id:
                q += f" and '{folder_id}' in parents"
            if query:
                q += f" and name contains '{query}'"

            # 获取文件列表
            params = {
                "q": q,
                "fields": "files(id,name,size,mimeType,createdTime,modifiedTime,webViewLink,webContentLink,owners,parents)",
                "pageSize": min(limit, 100),
            }

            async with self._session.get(f"{self.base_url}/files", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            files = []
            for file_data in data.get("files", []):
                files.append(File(
                    file_id=file_data["id"],
                    source_type=SourceType.GOOGLE_DRIVE,
                    name=file_data["name"],
                    size=int(file_data.get("size", 0)),
                    mime_type=file_data["mimeType"],
                    metadata={
                        "folder_id": folder_id,
                        "owners": [o.get("emailAddress") for o in file_data.get("owners", [])],
                        "parents": file_data.get("parents", []),
                    },
                    url=file_data.get("webViewLink"),
                    download_url=file_data.get("webContentLink"),
                    created_at=datetime.fromisoformat(file_data["createdTime"].replace("Z", "+00:00")),
                    modified_at=datetime.fromisoformat(file_data["modifiedTime"].replace("Z", "+00:00")),
                ))

            logger.info(f"Listed {len(files)} files from Google Drive")
            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    async def get_file(self, file_id: str) -> Optional[File]:
        """获取文件信息"""
        try:
            params = {
                "fields": "id,name,size,mimeType,createdTime,modifiedTime,webViewLink,webContentLink,owners,parents",
            }

            async with self._session.get(f"{self.base_url}/files/{file_id}", params=params) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                file_data = await resp.json()

            return File(
                file_id=file_data["id"],
                source_type=SourceType.GOOGLE_DRIVE,
                name=file_data["name"],
                size=int(file_data.get("size", 0)),
                mime_type=file_data["mimeType"],
                metadata={
                    "owners": [o.get("emailAddress") for o in file_data.get("owners", [])],
                    "parents": file_data.get("parents", []),
                },
                url=file_data.get("webViewLink"),
                download_url=file_data.get("webContentLink"),
                created_at=datetime.fromisoformat(file_data["createdTime"].replace("Z", "+00:00")),
                modified_at=datetime.fromisoformat(file_data["modifiedTime"].replace("Z", "+00:00")),
            )

        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            raise

    async def download_file(self, file_id: str) -> bytes:
        """下载文件内容"""
        try:
            params = {"alt": "media"}

            async with self._session.get(f"{self.base_url}/files/{file_id}", params=params) as resp:
                resp.raise_for_status()
                return await resp.read()

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出可文档化的文件（PDF、图片、文本文档等）"""
        # 支持的MIME类型
        supported_mime_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
            "text/csv",
            "application/json",
        ]

        # 添加图片类型
        supported_mime_types.extend([
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        ])

        # 构建查询
        mime_query = " or ".join([f"mimeType = '{mt}'" for mt in supported_mime_types])
        q = f"trashed=false and ({mime_query})"

        params = {
            "q": q,
            "fields": "files(id,name,size,mimeType,createdTime,modifiedTime,webViewLink,owners)",
            "pageSize": min(limit, 100),
        }

        async with self._session.get(f"{self.base_url}/files", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        documents = []
        for file_data in data.get("files", []):
            doc_type = self._mime_to_doc_type(file_data["mimeType"])

            documents.append(Document(
                doc_id=file_data["id"],
                source_type=SourceType.GOOGLE_DRIVE,
                title=file_data["name"],
                content="",  # 需要下载和处理
                doc_type=doc_type,
                metadata={
                    "mime_type": file_data["mimeType"],
                    "owners": [o.get("emailAddress") for o in file_data.get("owners", [])],
                },
                url=file_data.get("webViewLink"),
                author=file_data["owners"][0].get("emailAddress") if file_data.get("owners") else None,
                created_at=datetime.fromisoformat(file_data["createdTime"].replace("Z", "+00:00")),
                modified_at=datetime.fromisoformat(file_data["modifiedTime"].replace("Z", "+00:00")),
            ))

        logger.info(f"Listed {len(documents)} documents from Google Drive")
        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档（包含内容）"""
        file_info = await self.get_file(doc_id)
        if not file_info:
            return None

        try:
            content = await self.download_file(doc_id)
            doc_type = self._mime_to_doc_type(file_info.mime_type)

            # 注意：这里需要调用文档处理器来提取文本
            # 为了简化，这里只返回基本信息
            return Document(
                doc_id=doc_id,
                source_type=SourceType.GOOGLE_DRIVE,
                title=file_info.name,
                content="",  # 需要文档处理器
                doc_type=doc_type,
                metadata={
                    "mime_type": file_info.mime_type,
                    "size": file_info.size,
                    "owners": file_info.metadata.get("owners", []),
                },
                url=file_info.url,
                author=file_info.metadata.get("owners", [{}])[0].get("emailAddress") if file_info.metadata.get("owners") else None,
                created_at=file_info.created_at,
                modified_at=file_info.modified_at,
            )

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索文档"""
        return await self.list_documents(limit=limit)

    async def get_webhook_url(self) -> str:
        """获取Webhook URL（Google Drive使用API轮询或Google Workspace Events）"""
        # Google Drive不支持直接Webhook，需要使用Google Workspace Events API
        # 这里返回占位符
        return "https://www.googleapis.com/workspace/events"

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证Webhook签名（Google Workspace Events使用JWT验证）"""
        # 实际实现需要验证JWT签名
        return True

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """处理Webhook事件（Google Workspace Events）"""
        # 实际实现需要处理不同类型的事件
        return []

    def _mime_to_doc_type(self, mime_type: str) -> DocumentType:
        """将MIME类型转换为DocumentType"""
        if mime_type == "application/pdf":
            return DocumentType.PDF
        elif mime_type.startswith("image/"):
            return DocumentType.IMAGE
        elif mime_type.startswith("video/"):
            return DocumentType.VIDEO
        elif mime_type.startswith("text/"):
            return DocumentType.TEXT
        else:
            return DocumentType.UNKNOWN
