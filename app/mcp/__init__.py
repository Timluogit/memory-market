"""
Agent记忆市场 - MCP Server

使用FastMCP框架实现，支持stdio和SSE双传输协议
"""
from .server import mcp

__all__ = ["mcp"]
