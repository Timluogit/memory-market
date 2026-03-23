"""
外部数据源 SDK 集成
提供与主流AI框架的集成接口
"""
from typing import Optional, List, Dict, Any
import logging
import httpx

logger = logging.getLogger(__name__)


class ExternalSourcesSDK:
    """外部数据源SDK基类"""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )

    async def close(self):
        """关闭HTTP客户端"""
        await self._client.aclose()

    async def connect_source(self, source_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """连接数据源"""
        response = await self._client.post(
            f"{self.api_url}/external-sources/connect",
            json={"source_type": source_type, "config": config},
        )
        response.raise_for_status()
        return response.json()

    async def disconnect_source(self, source_id: str) -> Dict[str, Any]:
        """断开数据源"""
        response = await self._client.delete(
            f"{self.api_url}/external-sources/{source_id}/disconnect",
        )
        response.raise_for_status()
        return response.json()

    async def sync_source(self, source_id: str, force: bool = False) -> Dict[str, Any]:
        """同步数据源"""
        response = await self._client.post(
            f"{self.api_url}/external-sources/{source_id}/sync",
            params={"force": force},
        )
        response.raise_for_status()
        return response.json()

    async def list_sources(self) -> Dict[str, Any]:
        """列出数据源"""
        response = await self._client.get(f"{self.api_url}/external-sources")
        response.raise_for_status()
        return response.json()

    async def search_sources(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索所有数据源"""
        # 这里需要实现搜索接口
        return []

    async def list_files(self, source_id: str, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """列出文件"""
        params = {}
        if folder_id:
            params["folder_id"] = folder_id

        response = await self._client.get(
            f"{self.api_url}/external-sources/{source_id}/files",
            params=params,
        )
        response.raise_for_status()
        return response.json()


# ============ Vercel AI SDK 集成 ============

class VercelAISDKTools:
    """Vercel AI SDK 工具集"""

    @staticmethod
    def create_tools(sdk: ExternalSourcesSDK) -> List[Dict[str, Any]]:
        """创建Vercel AI SDK工具"""

        async def connect_source_tool(source_type: str, config: Dict[str, Any]) -> str:
            """连接外部数据源"""
            result = await sdk.connect_source(source_type, config)
            return f"Connected to {result['source_type']} with ID: {result['source_id']}"

        async def search_sources_tool(query: str, limit: int = 10) -> str:
            """搜索外部数据源"""
            results = await sdk.search_sources(query, limit)
            return f"Found {len(results)} results: {results}"

        async def list_files_tool(source_id: str, folder_id: Optional[str] = None) -> str:
            """列出数据源文件"""
            result = await sdk.list_files(source_id, folder_id)
            files = result.get("files", [])
            return f"Found {len(files)} files in {source_id}"

        return [
            {
                "type": "function",
                "function": {
                    "name": "connect_source",
                    "description": "Connect to an external data source (Google Drive, Gmail, Notion, OneDrive, GitHub)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_type": {
                                "type": "string",
                                "enum": ["google_drive", "gmail", "notion", "onedrive", "github"],
                                "description": "Type of data source",
                            },
                            "config": {
                                "type": "object",
                                "description": "Configuration parameters (access_token, etc.)",
                            },
                        },
                        "required": ["source_type", "config"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_sources",
                    "description": "Search across all connected external data sources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 10,
                                "description": "Maximum number of results",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a specific data source",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "Data source ID",
                            },
                            "folder_id": {
                                "type": "string",
                                "description": "Folder ID (optional)",
                            },
                        },
                        "required": ["source_id"],
                    },
                },
            },
        ]


# ============ LangChain 集成 ============

class LangChainTools:
    """LangChain 工具集"""

    @staticmethod
    def create_tools(sdk: ExternalSourcesSDK):
        """创建LangChain工具"""
        from langchain.tools import StructuredTool
        from pydantic import BaseModel, Field

        class ConnectSourceInput(BaseModel):
            source_type: str = Field(description="Type of data source")
            config: Dict[str, Any] = Field(description="Configuration parameters")

        class SearchSourcesInput(BaseModel):
            query: str = Field(description="Search query")
            limit: int = Field(default=10, description="Maximum number of results")

        class ListFilesInput(BaseModel):
            source_id: str = Field(description="Data source ID")
            folder_id: Optional[str] = Field(None, description="Folder ID (optional)")

        async def connect_source(input_data: ConnectSourceInput) -> str:
            result = await sdk.connect_source(input_data.source_type, input_data.config)
            return f"Connected to {result['source_type']} with ID: {result['source_id']}"

        async def search_sources(input_data: SearchSourcesInput) -> str:
            results = await sdk.search_sources(input_data.query, input_data.limit)
            return f"Found {len(results)} results: {results}"

        async def list_files(input_data: ListFilesInput) -> str:
            result = await sdk.list_files(input_data.source_id, input_data.folder_id)
            files = result.get("files", [])
            return f"Found {len(files)} files in {input_data.source_id}"

        return [
            StructuredTool.from_function(
                func=connect_source,
                name="connect_external_source",
                description="Connect to an external data source (Google Drive, Gmail, Notion, OneDrive, GitHub)",
                args_schema=ConnectSourceInput,
            ),
            StructuredTool.from_function(
                func=search_sources,
                name="search_external_sources",
                description="Search across all connected external data sources",
                args_schema=SearchSourcesInput,
            ),
            StructuredTool.from_function(
                func=list_files,
                name="list_external_files",
                description="List files in a specific data source",
                args_schema=ListFilesInput,
            ),
        ]


# ============ LangGraph 集成 ============

class LangGraphNodes:
    """LangGraph 节点"""

    @staticmethod
    def create_nodes(sdk: ExternalSourcesSDK) -> Dict[str, Any]:
        """创建LangGraph节点"""
        from typing import TypedDict, Annotated, Sequence
        import operator

        class GraphState(TypedDict):
            messages: Annotated[Sequence[str], operator.add]
            sources: List[Dict[str, Any]]

        async def connect_source_node(state: GraphState, source_type: str, config: Dict[str, Any]) -> GraphState:
            """连接数据源节点"""
            result = await sdk.connect_source(source_type, config)
            state["sources"].append(result)
            state["messages"].append(f"Connected to {result['source_type']} with ID: {result['source_id']}")
            return state

        async def search_sources_node(state: GraphState, query: str) -> GraphState:
            """搜索数据源节点"""
            results = await sdk.search_sources(query)
            state["messages"].append(f"Found {len(results)} results for query: {query}")
            return state

        return {
            "connect_source": connect_source_node,
            "search_sources": search_sources_node,
        }


# ============ OpenAI Agents SDK 集成 ============

class OpenAITools:
    """OpenAI Agents SDK 工具集"""

    @staticmethod
    def create_tools(sdk: ExternalSourcesSDK) -> List[Dict[str, Any]]:
        """创建OpenAI Agents SDK工具"""

        async def connect_source_tool(source_type: str, config: Dict[str, Any]) -> str:
            """Connect to an external data source"""
            result = await sdk.connect_source(source_type, config)
            return f"Connected to {result['source_type']} with ID: {result['source_id']}"

        async def search_sources_tool(query: str, limit: int = 10) -> str:
            """Search across all connected external data sources"""
            results = await sdk.search_sources(query, limit)
            return f"Found {len(results)} results: {results}"

        async def list_files_tool(source_id: str, folder_id: Optional[str] = None) -> str:
            """List files in a specific data source"""
            result = await sdk.list_files(source_id, folder_id)
            files = result.get("files", [])
            return f"Found {len(files)} files in {source_id}"

        return [
            {
                "type": "function",
                "function": {
                    "name": "connect_source",
                    "description": "Connect to an external data source (Google Drive, Gmail, Notion, OneDrive, GitHub)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_type": {
                                "type": "string",
                                "enum": ["google_drive", "gmail", "notion", "onedrive", "github"],
                            },
                            "config": {"type": "object"},
                        },
                        "required": ["source_type", "config"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_sources",
                    "description": "Search across all connected external data sources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a specific data source",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_id": {"type": "string"},
                            "folder_id": {"type": "string"},
                        },
                        "required": ["source_id"],
                    },
                },
            },
        ]


# ============ Mastra 集成 ============

class MastraTools:
    """Mastra 工具集"""

    @staticmethod
    def create_tools(sdk: ExternalSourcesSDK) -> List[Dict[str, Any]]:
        """创建Mastra工具"""

        async def connect_source_tool(source_type: str, config: Dict[str, Any]) -> str:
            """Connect to an external data source"""
            result = await sdk.connect_source(source_type, config)
            return f"Connected to {result['source_type']} with ID: {result['source_id']}"

        async def search_sources_tool(query: str, limit: int = 10) -> str:
            """Search across all connected external data sources"""
            results = await sdk.search_sources(query, limit)
            return f"Found {len(results)} results: {results}"

        async def list_files_tool(source_id: str, folder_id: Optional[str] = None) -> str:
            """List files in a specific data source"""
            result = await sdk.list_files(source_id, folder_id)
            files = result.get("files", [])
            return f"Found {len(files)} files in {source_id}"

        return [
            {
                "name": "connect_source",
                "description": "Connect to an external data source (Google Drive, Gmail, Notion, OneDrive, GitHub)",
                "parameters": {
                    "source_type": {
                        "type": "string",
                        "enum": ["google_drive", "gmail", "notion", "onedrive", "github"],
                    },
                    "config": {"type": "object"},
                },
                "handler": connect_source_tool,
            },
            {
                "name": "search_sources",
                "description": "Search across all connected external data sources",
                "parameters": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "handler": search_sources_tool,
            },
            {
                "name": "list_files",
                "description": "List files in a specific data source",
                "parameters": {
                    "source_id": {"type": "string"},
                    "folder_id": {"type": "string"},
                },
                "handler": list_files_tool,
            },
        ]


# ============ 便捷函数 ============

async def create_sdk(api_url: str, api_key: str, framework: str = "vercel") -> Dict[str, Any]:
    """
    创建SDK实例

    Args:
        api_url: API URL
        api_key: API密钥
        framework: 框架名称 (vercel, langchain, langgraph, openai, mastra)

    Returns:
        工具集
    """
    sdk = ExternalSourcesSDK(api_url, api_key)

    framework_map = {
        "vercel": VercelAISDKTools,
        "langchain": LangChainTools,
        "langgraph": LangGraphNodes,
        "openai": OpenAITools,
        "mastra": MastraTools,
    }

    if framework not in framework_map:
        raise ValueError(f"Unsupported framework: {framework}")

    return framework_map[framework].create_tools(sdk)
