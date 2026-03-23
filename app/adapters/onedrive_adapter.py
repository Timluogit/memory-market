"""
OneDrive 适配器
支持文件列表、下载、元数据、Webhook
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import aiohttp

from ..services.external_source_service import (
    SourceAdapter,
    SourceType,
    File,
    Document,
    DocumentType,
)

logger = logging.getLogger(__name__)


class OneDriveAdapter(SourceAdapter):
    """OneDrive (Microsoft Graph) API 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.tenant_id = config.get("tenant_id", "common")
        self.base_url = "https://graph.microsoft.com/v1.0/me/drive"
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
            logger.info("OneDrive adapter initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OneDrive adapter: {e}")
            return False

    async def connect(self) -> bool:
        """连接到OneDrive（验证token）"""
        try:
            await self._get_drive_info()
            logger.info("Connected to OneDrive")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OneDrive: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False
        logger.info("Disconnected from OneDrive")
        return True

    async def _get_drive_info(self) -> Dict[str, Any]:
        """获取Drive信息"""
        async with self._session.get(self.base_url) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[File]:
        """列出文件"""
        try:
            # 构建URL
            if folder_id:
                url = f"{self.base_url}/items/{folder_id}/children"
            else:
                url = f"{self.base_url}/root/children"

            params = {
                "$top": min(limit, 100),
                "$select": "id,name,size,file,folder,createdDateTime,lastModifiedDateTime,webUrl,parentReference",
            }

            async with self._session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            files = []
            for item in data.get("value", []):
                file_info = item.get("file", {})
                folder_info = item.get("folder", {})

                # 确定MIME类型
                if file_info:
                    mime_type = file_info.get("mimeType", "application/octet-stream")
                elif folder_info:
                    mime_type = "application/vnd.microsoft.folder"
                else:
                    mime_type = "application/octet-stream"

                # 确定下载URL
                download_url = None
                if file_info:
                    # 文件需要另外获取下载URL
                    download_url = f"{self.base_url}/items/{item['id']}/content"

                files.append(File(
                    file_id=item["id"],
                    source_type=SourceType.ONEDRIVE,
                    name=item["name"],
                    size=item.get("size", 0),
                    mime_type=mime_type,
                    metadata={
                        "folder_id": folder_id,
                        "parent": item.get("parentReference", {}).get("id"),
                    },
                    url=item.get("webUrl"),
                    download_url=download_url,
                    created_at=datetime.fromisoformat(item["createdDateTime"].replace("Z", "+00:00")),
                    modified_at=datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00")),
                ))

            logger.info(f"Listed {len(files)} files from OneDrive")
            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    async def get_file(self, file_id: str) -> Optional[File]:
        """获取文件信息"""
        try:
            async with self._session.get(
                f"{self.base_url}/items/{file_id}",
                params={
                    "$select": "id,name,size,file,folder,createdDateTime,lastModifiedDateTime,webUrl,parentReference",
                }
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                item = await resp.json()

            file_info = item.get("file", {})
            folder_info = item.get("folder", {})

            if file_info:
                mime_type = file_info.get("mimeType", "application/octet-stream")
                download_url = f"{self.base_url}/items/{file_id}/content"
            elif folder_info:
                mime_type = "application/vnd.microsoft.folder"
                download_url = None
            else:
                mime_type = "application/octet-stream"
                download_url = None

            return File(
                file_id=item["id"],
                source_type=SourceType.ONEDRIVE,
                name=item["name"],
                size=item.get("size", 0),
                mime_type=mime_type,
                metadata={
                    "parent": item.get("parentReference", {}).get("id"),
                },
                url=item.get("webUrl"),
                download_url=download_url,
                created_at=datetime.fromisoformat(item["createdDateTime"].replace("Z", "+00:00")),
                modified_at=datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00")),
            )

        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            raise

    async def download_file(self, file_id: str) -> bytes:
        """下载文件内容"""
        try:
            async with self._session.get(f"{self.base_url}/items/{file_id}/content") as resp:
                resp.raise_for_status()
                return await resp.read()

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出可文档化的文件"""
        try:
            # 支持的文件扩展名
            supported_extensions = [
                ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                ".txt", ".csv", ".json", ".xml", ".md",
                ".jpg", ".jpeg", ".png", ".gif", ".webp",
                ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs",
            ]

            # 获取文件列表
            url = f"{self.base_url}/root/children"
            params = {
                "$top": min(limit, 100),
                "$select": "id,name,size,file,createdDateTime,lastModifiedDateTime,webUrl",
            }

            async with self._session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            documents = []
            for item in data.get("value", []):
                # 跳过文件夹
                if "folder" in item:
                    continue

                name = item["name"]
                # 检查文件扩展名
                if not any(name.lower().endswith(ext) for ext in supported_extensions):
                    continue

                file_info = item.get("file", {})
                mime_type = file_info.get("mimeType", "application/octet-stream") if file_info else None
                doc_type = self._mime_to_doc_type(mime_type or name)

                documents.append(Document(
                    doc_id=item["id"],
                    source_type=SourceType.ONEDRIVE,
                    title=name,
                    content="",  # 需要下载和处理
                    doc_type=doc_type,
                    metadata={
                        "mime_type": mime_type,
                        "size": item.get("size", 0),
                    },
                    url=item.get("webUrl"),
                    created_at=datetime.fromisoformat(item["createdDateTime"].replace("Z", "+00:00")),
                    modified_at=datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00")),
                ))

            logger.info(f"Listed {len(documents)} documents from OneDrive")
            return documents

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档（包含内容）"""
        file_info = await self.get_file(doc_id)
        if not file_info:
            return None

        try:
            # 注意：这里需要调用文档处理器来提取文本
            mime_type = file_info.mime_type
            doc_type = self._mime_to_doc_type(mime_type or file_info.name)

            return Document(
                doc_id=doc_id,
                source_type=SourceType.ONEDRIVE,
                title=file_info.name,
                content="",  # 需要文档处理器
                doc_type=doc_type,
                metadata={
                    "mime_type": mime_type,
                    "size": file_info.size,
                },
                url=file_info.url,
                created_at=file_info.created_at,
                modified_at=file_info.modified_at,
            )

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索文档"""
        try:
            # OneDrive搜索API
            params = {
                "$search": f'"{query}"',
                "$top": min(limit, 100),
            }

            async with self._session.get(f"{self.base_url}/root/search(q='{query}')", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            documents = []
            for item in data.get("value", []):
                # 跳过文件夹
                if "folder" in item:
                    continue

                doc_type = self._mime_to_doc_type(item.get("file", {}).get("mimeType") or item["name"])

                documents.append(Document(
                    doc_id=item["id"],
                    source_type=SourceType.ONEDRIVE,
                    title=item["name"],
                    content="",  # 需要下载和处理
                    doc_type=doc_type,
                    metadata={
                        "size": item.get("size", 0),
                    },
                    url=item.get("webUrl"),
                    created_at=datetime.fromisoformat(item["createdDateTime"].replace("Z", "+00:00")),
                    modified_at=datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00")),
                ))

            return documents

        except Exception as e:
            logger.error(f"Failed to search OneDrive: {e}")
            raise

    async def get_webhook_url(self) -> str:
        """获取Webhook URL（OneDrive使用Microsoft Graph订阅）"""
        return "https://graph.microsoft.com/v1.0/subscriptions"

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证Webhook签名（Microsoft Graph使用client state）"""
        # 实际实现需要验证签名
        return True

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """处理Webhook事件（Microsoft Graph变更通知）"""
        # 实际实现需要处理不同类型的通知
        return []

    def _mime_to_doc_type(self, mime_or_name: str) -> DocumentType:
        """将MIME类型或文件名转换为DocumentType"""
        mime_or_name = mime_or_name.lower()

        if ".pdf" in mime_or_name or mime_or_name == "application/pdf":
            return DocumentType.PDF
        elif any(ext in mime_or_name for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]) or mime_or_name.startswith("image/"):
            return DocumentType.IMAGE
        elif any(ext in mime_or_name for ext in [".mp4", ".mov", ".avi", ".mkv"]) or mime_or_name.startswith("video/"):
            return DocumentType.VIDEO
        elif any(ext in mime_or_name for ext in [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs"]):
            return DocumentType.CODE
        elif mime_or_name.startswith("text/"):
            return DocumentType.TEXT
        else:
            return DocumentType.UNKNOWN
