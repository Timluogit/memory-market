"""
GitHub 适配器
支持代码列表、下载、解析、Webhook
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import aiohttp
import base64

from ..services.external_source_service import (
    SourceAdapter,
    SourceType,
    File,
    Document,
    DocumentType,
)

logger = logging.getLogger(__name__)


class GitHubAdapter(SourceAdapter):
    """GitHub API 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.repositories = config.get("repositories", [])
        self.base_url = "https://api.github.com"
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> bool:
        """初始化适配器"""
        try:
            if not self.access_token:
                raise ValueError("access_token is required")

            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            self._session = aiohttp.ClientSession(headers=headers)
            self._initialized = True
            logger.info("GitHub adapter initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GitHub adapter: {e}")
            return False

    async def connect(self) -> bool:
        """连接到GitHub（验证token）"""
        try:
            await self._get_user()
            logger.info("Connected to GitHub")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GitHub: {e}")
            return False

    async def disconnect(self) -> bool:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False
        logger.info("Disconnected from GitHub")
        return True

    async def _get_user(self) -> Dict[str, Any]:
        """获取当前用户信息"""
        async with self._session.get(f"{self.base_url}/user") as resp:
            resp.raise_for_status()
            return await resp.json()

    def _parse_repo(self, repo_str: str) -> Dict[str, str]:
        """解析仓库字符串（owner/repo）"""
        parts = repo_str.split("/")
        if len(parts) == 2:
            return {"owner": parts[0], "repo": parts[1]}
        raise ValueError(f"Invalid repository format: {repo_str}")

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[File]:
        """列出文件"""
        files = []

        for repo_str in self.repositories[:min(len(self.repositories), 5)]:  # 限制仓库数量
            try:
                repo = self._parse_repo(repo_str)
                url = f"{self.base_url}/repos/{repo['owner']}/{repo['repo']}/contents/"

                if folder_id:
                    url += folder_id

                params = {"per_page": min(limit // len(self.repositories) + 1, 100)}

                async with self._session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    items = await resp.json()

                for item in items:
                    if item["type"] == "file":
                        files.append(File(
                            file_id=item["sha"],
                            source_type=SourceType.GITHUB,
                            name=item["name"],
                            size=item.get("size", 0),
                            mime_type="text/plain",  # GitHub API不返回MIME类型
                            metadata={
                                "repo": repo_str,
                                "path": item["path"],
                                "html_url": item["html_url"],
                            },
                            url=item["html_url"],
                            download_url=item.get("download_url"),
                            created_at=None,  # GitHub API不返回创建时间
                            modified_at=None,
                        ))

            except Exception as e:
                logger.warning(f"Failed to list files from {repo_str}: {e}")

        logger.info(f"Listed {len(files)} files from GitHub")
        return files

    async def get_file(self, file_id: str) -> Optional[File]:
        """GitHub的file_id是SHA，需要额外信息"""
        # GitHub不直接通过SHA获取文件信息
        # 这里返回None，需要使用repository + path的方式
        return None

    async def download_file(self, file_id: str, repo: Optional[str] = None, path: Optional[str] = None) -> bytes:
        """下载文件内容"""
        try:
            if not repo or not path:
                raise ValueError("repo and path are required for GitHub")

            repo_parsed = self._parse_repo(repo)
            url = f"{self.base_url}/repos/{repo_parsed['owner']}/{repo_parsed['repo']}/contents/{path}"

            async with self._session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

            # 解码Base64内容
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"])
            else:
                content = data.get("content", "").encode("utf-8")

            return content

        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise

    async def list_documents(self, limit: int = 100) -> List[Document]:
        """列出代码文档"""
        documents = []

        # 支持的文件扩展名
        supported_extensions = [
            ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs",
            ".rb", ".php", ".swift", ".kt", ".scala", ".cs",
            ".md", ".txt", ".json", ".xml", ".yaml", ".yml",
        ]

        for repo_str in self.repositories[:min(len(self.repositories), 5)]:
            try:
                repo = self._parse_repo(repo_str)
                url = f"{self.base_url}/repos/{repo['owner']}/{repo['repo']}/git/trees/master?recursive=1"

                async with self._session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

                for tree_item in data.get("tree", []):
                    if tree_item["type"] != "blob":
                        continue

                    path = tree_item["path"]
                    # 检查文件扩展名
                    if not any(path.lower().endswith(ext) for ext in supported_extensions):
                        continue

                    # 限制文件大小（只处理小文件）
                    if tree_item.get("size", 0) > 100000:  # 100KB
                        continue

                    doc_type = self._path_to_doc_type(path)

                    documents.append(Document(
                        doc_id=tree_item["sha"],
                        source_type=SourceType.GITHUB,
                        title=path.split("/")[-1],
                        content="",  # 需要下载和处理
                        doc_type=doc_type,
                        metadata={
                            "repo": repo_str,
                            "path": path,
                            "size": tree_item.get("size", 0),
                            "url": f"https://github.com/{repo['owner']}/{repo['repo']}/blob/master/{path}",
                        },
                        url=f"https://github.com/{repo['owner']}/{repo['repo']}/blob/master/{path}",
                        created_at=None,
                        modified_at=None,
                    ))

                    if len(documents) >= limit:
                        break

                if len(documents) >= limit:
                    break

            except Exception as e:
                logger.warning(f"Failed to list documents from {repo_str}: {e}")

        logger.info(f"Listed {len(documents)} documents from GitHub")
        return documents

    async def get_document(self, doc_id: str, repo: Optional[str] = None, path: Optional[str] = None) -> Optional[Document]:
        """获取代码文档"""
        if not repo or not path:
            return None

        try:
            content_bytes = await self.download_file(doc_id, repo, path)
            content = content_bytes.decode("utf-8", errors="ignore")

            doc_type = self._path_to_doc_type(path)

            return Document(
                doc_id=doc_id,
                source_type=SourceType.GITHUB,
                title=path.split("/")[-1],
                content=content,
                doc_type=doc_type,
                metadata={
                    "repo": repo,
                    "path": path,
                    "url": f"https://github.com/{repo.split('/')[0]}/{repo.split('/')[1]}/blob/master/{path}",
                },
                url=f"https://github.com/{repo.split('/')[0]}/{repo.split('/')[1]}/blob/master/{path}",
                created_at=None,
                modified_at=None,
            )

        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None

    async def search(self, query: str, limit: int = 10) -> List[Document]:
        """搜索代码"""
        try:
            params = {
                "q": query,
                "per_page": min(limit, 100),
            }

            async with self._session.get(f"{self.base_url}/search/code", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            documents = []
            for item in data.get("items", []):
                path = item["path"]
                repo_str = f"{item['repository']['owner']['login']}/{item['repository']['name']}"
                doc_type = self._path_to_doc_type(path)

                documents.append(Document(
                    doc_id=item["sha"],
                    source_type=SourceType.GITHUB,
                    title=path.split("/")[-1],
                    content="",  # 需要下载和处理
                    doc_type=doc_type,
                    metadata={
                        "repo": repo_str,
                        "path": path,
                        "html_url": item["html_url"],
                    },
                    url=item["html_url"],
                    created_at=None,
                    modified_at=None,
                ))

            return documents

        except Exception as e:
            logger.error(f"Failed to search GitHub: {e}")
            raise

    async def get_webhook_url(self) -> str:
        """获取Webhook URL（GitHub使用Webhooks API）"""
        return "https://api.github.com/repos/{owner}/{repo}/hooks"

    async def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """验证Webhook签名（GitHub使用HMAC-SHA256）"""
        # 实际实现需要验证签名
        # import hmac
        # import hashlib
        # secret = self.config.get("webhook_secret")
        # if secret:
        #     expected = f"sha256={hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()}"
        #     return hmac.compare_digest(signature, expected)
        return True

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[Document]:
        """处理Webhook事件（GitHub Push, Pull Request等）"""
        # 实际实现需要处理不同类型的事件
        return []

    def _path_to_doc_type(self, path: str) -> DocumentType:
        """将文件路径转换为DocumentType"""
        path = path.lower()

        if any(ext in path for ext in [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".cs"]):
            return DocumentType.CODE
        elif any(ext in path for ext in [".md", ".txt"]):
            return DocumentType.TEXT
        else:
            return DocumentType.UNKNOWN

    async def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """获取仓库信息"""
        async with self._session.get(f"{self.base_url}/repos/{owner}/{repo}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def list_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """列出仓库分支"""
        async with self._session.get(f"{self.base_url}/repos/{owner}/{repo}/branches") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "master") -> Optional[str]:
        """获取文件内容"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
            params = {"ref": ref}

            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"])
            else:
                content = data.get("content", "").encode("utf-8")

            return content.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None
