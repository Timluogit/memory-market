"""
Notion 适配器
支持页面列表、数据库查询、Webhook
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


class NotionAdapter(SourceAdapter):
    """Notion API 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.base_url = "https://api.notion.com/v1"
        self._session: Optional[aiohttp.ClientSession] = None
        self._version = "2022-06-28"

    async def initialize(self) -> bool:
        """初始化适配器"""
        try:
            if not self.access_token:
                raise ValueError("access_token is required")

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Notion-Version": self._version,
            }

            self._session = aiohttp.ClientSession(headers=headers)
            self._initialized = True
            logger.info("Notion adapter initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Notion adapter: {e}")
            return False

    async def connect(self) -> bool:
        """连接到Notion（验证token）"""
        try:
            await self._search()
            logger.info("Connected to Notion")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Notion: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False
        logger.info("Disconnected from Notion")
        return True

    async def _search(self, query: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """搜索Notion"""
        payload = {
            "page_size": min(limit, 100),
        }

        if query:
            payload["query"] = query

        async with self._session.post(f"{self.base_url}/search", json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_files(self, folder_id: Optional[str] = None, limit: int = 100) -> List[File]:
        """Notion使用页面而非文件，返回空"""
        return []

    async def get_file(self, file_id: str) -> Optional[File]:
        """Notion不使用文件，返回None"""
        return None

    async def download_file(self, file_id: str) -> bytes:
        """Notion不使用文件下载"""
        raise NotImplementedError("Notion uses pages, not files")

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出所有页面和数据库"""
        try:
            data = await self._search(limit=limit)

            documents = []
            for result in data.get("results", []):
                doc = await self._parse_block(result)
                if doc:
                    documents.append(doc)

            logger.info(f"Listed {len(documents)} documents from Notion")
            return documents

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    async def _parse_block(self, block: Dict[str, Any]) -> Optional[Document]:
        """解析Notion块（页面或数据库）"""
        try:
            block_id = block["id"]
            object_type = block["object"]

            if object_type == "page":
                properties = block.get("properties", {})
                title = self._extract_title(properties)

                # 获取页面内容
                content = await self._get_page_content(block_id)

                # 提取作者（最后编辑者）
                last_edited_by = block.get("last_edited_by", {})
                author = last_edited_by.get("id") if last_edited_by else None

                # 解析时间
                created_time = block.get("created_time")
                last_edited_time = block.get("last_edited_time")

                created_at = datetime.fromisoformat(created_time.replace("Z", "+00:00")) if created_time else None
                modified_at = datetime.fromisoformat(last_edited_time.replace("Z", "+00:00")) if last_edited_time else None

                return Document(
                    doc_id=block_id,
                    source_type=SourceType.NOTION,
                    title=title,
                    content=content,
                    doc_type=DocumentType.NOTE,
                    metadata={
                        "icon": block.get("icon"),
                        "cover": block.get("cover"),
                        "archived": block.get("archived", False),
                        "in_trash": block.get("in_trash", False),
                        "url": block.get("url"),
                    },
                    url=block.get("url"),
                    author=author,
                    created_at=created_at,
                    modified_at=modified_at,
                )

            elif object_type == "database":
                # 数据库也可以视为一种文档
                title = self._extract_database_title(block)

                return Document(
                    doc_id=block_id,
                    source_type=SourceType.NOTION,
                    title=f"[Database] {title}",
                    content="",  # 数据库内容需要另外查询
                    doc_type=DocumentType.TEXT,
                    metadata={
                        "type": "database",
                        "description": block.get("description"),
                        "url": block.get("url"),
                    },
                    url=block.get("url"),
                    created_at=datetime.fromisoformat(block["created_time"].replace("Z", "+00:00")),
                    modified_at=datetime.fromisoformat(block["last_edited_time"].replace("Z", "+00:00")),
                )

            return None

        except Exception as e:
            logger.error(f"Failed to parse block: {e}")
            return None

    def _extract_title(self, properties: Dict[str, Any]) -> str:
        """提取页面标题"""
        # 标题通常在 "title" 或 "Name" 属性中
        for key, value in properties.items():
            if value.get("type") == "title":
                title_parts = value.get("title", [])
                if title_parts and title_parts[0].get("type") == "text":
                    return title_parts[0]["text"]["content"]

        return "(Untitled)"

    def _extract_database_title(self, block: Dict[str, Any]) -> str:
        """提取数据库标题"""
        title_parts = block.get("title", [])
        if title_parts and title_parts[0].get("type") == "text":
            return title_parts[0]["text"]["content"]
        return "(Untitled Database)"

    async def _get_page_content(self, page_id: str) -> str:
        """获取页面内容"""
        try:
            # 获取页面块
            blocks = await self._get_page_blocks(page_id)

            # 提取文本内容
            content_parts = []
            for block in blocks:
                block_type = block.get("type")
                if block_type == "paragraph":
                    text = self._extract_text_from_block(block, "paragraph")
                    if text:
                        content_parts.append(text)
                elif block_type == "heading_1":
                    text = self._extract_text_from_block(block, "heading_1")
                    if text:
                        content_parts.append(f"# {text}")
                elif block_type == "heading_2":
                    text = self._extract_text_from_block(block, "heading_2")
                    if text:
                        content_parts.append(f"## {text}")
                elif block_type == "heading_3":
                    text = self._extract_text_from_block(block, "heading_3")
                    if text:
                        content_parts.append(f"### {text}")
                elif block_type == "bulleted_list_item":
                    text = self._extract_text_from_block(block, "bulleted_list_item")
                    if text:
                        content_parts.append(f"- {text}")
                elif block_type == "numbered_list_item":
                    text = self._extract_text_from_block(block, "numbered_list_item")
                    if text:
                        content_parts.append(f"1. {text}")
                elif block_type == "to_do":
                    text = self._extract_text_from_block(block, "to_do")
                    checked = block["to_do"].get("checked", False)
                    if text:
                        content_parts.append(f"- [{'x' if checked else ' '}] {text}")
                elif block_type == "quote":
                    text = self._extract_text_from_block(block, "quote")
                    if text:
                        content_parts.append(f"> {text}")
                elif block_type == "code":
                    code = block.get("code", {}).get("text", [])
                    text = "".join([t.get("text", {}).get("content", "") for t in code])
                    if text:
                        content_parts.append(f"```\n{text}\n```")
                elif block_type == "divider":
                    content_parts.append("---")

            return "\n\n".join(content_parts)

        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return ""

    async def _get_page_blocks(self, page_id: str) -> List[Dict[str, Any]]:
        """获取页面的所有块"""
        blocks = []
        start_cursor = None

        while True:
            params = {"page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            async with self._session.get(
                f"{self.base_url}/blocks/{page_id}/children",
                params=params
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            blocks.extend(data.get("results", []))

            if not data.get("has_more"):
                break

            start_cursor = data.get("next_cursor")

        return blocks

    def _extract_text_from_block(self, block: Dict[str, Any], block_type: str) -> str:
        """从块中提取文本"""
        text_parts = []

        try:
            text_content = block.get(block_type, {}).get("text", [])
            for text in text_content:
                text_parts.append(text.get("text", {}).get("content", ""))

            return "".join(text_parts)

        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            return ""

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取Notion页面"""
        try:
            async with self._session.get(f"{self.base_url}/blocks/{doc_id}") as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                block = await resp.json()

            return await self._parse_block(block)

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索Notion"""
        try:
            data = await self._search(query=query, limit=limit)

            documents = []
            for result in data.get("results", []):
                doc = await self._parse_block(result)
                if doc:
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Failed to search Notion: {e}")
            raise

    async def query_database(self, database_id: str) -> List[Dict[str, Any]]:
        """查询数据库"""
        try:
            payload = {"page_size": 100}

            async with self._session.post(
                f"{self.base_url}/databases/{database_id}/query",
                json=payload
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            return data.get("results", [])

        except Exception as e:
            logger.error(f"Failed to query database: {e}")
            raise

    async def get_webhook_url(self) -> str:
        """获取Webhook URL（Notion需要设置web endpoint）"""
        return "https://api.notion.com/v1/webhooks"

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证Webhook签名（Notion使用token验证）"""
        # 实际实现需要验证签名
        return True

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """处理Webhook事件"""
        # Notion Webhook会在页面更新时触发
        event_type = payload.get("type")
        data = payload.get("data", {})

        if event_type == "page.updated":
            block_id = data.get("id")
            doc = await self.get_document(block_id)
            if doc:
                return [doc]

        return []
