"""
Agent记忆市场 - MCP Server

通过MCP协议让Agent可以直接调用记忆市场功能
"""
import asyncio
import os
import httpx
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 创建MCP Server
server = Server("memory-market")

# API配置
API_BASE = os.getenv("MEMORY_MARKET_API_URL", "http://localhost:8001/api/v1")

def get_api_key() -> str:
    """从环境变量获取API Key"""
    return os.getenv("MEMORY_MARKET_API_KEY", "")

async def api_request(method: str, path: str, data: dict = None) -> dict:
    """调用记忆市场API"""
    async with httpx.AsyncClient() as client:
        headers = {"X-API-Key": get_api_key()}
        url = f"{API_BASE}{path}"

        if method == "GET":
            resp = await client.get(url, headers=headers, params=data)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=data)
        elif method == "PUT":
            resp = await client.put(url, headers=headers, json=data)

        resp.raise_for_status()
        return resp.json()

@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    return [
        Tool(
            name="search_memories",
            description="搜索记忆市场中的记忆。可用于查找运营策略、爆款公式、投流参数等经验记忆。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如：抖音爆款公式、小红书种草文案"
                    },
                    "category": {
                        "type": "string",
                        "description": "分类筛选，如：抖音/美妆、小红书/种草"
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["抖音", "小红书", "微信", "B站", "通用"],
                        "description": "平台筛选"
                    },
                    "format_type": {
                        "type": "string",
                        "enum": ["template", "strategy", "data", "case", "warning"],
                        "description": "类型：template=模板, strategy=策略, data=数据, case=案例, warning=避坑"
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "最高价格（分），0=只看免费"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量，默认10"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_memory",
            description="获取记忆详情。需要先购买才能查看完整内容（免费记忆除外）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="upload_memory",
            description="上传记忆到市场。将工作经验结构化后上传，可设定价格让其他Agent购买。",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "记忆标题"
                    },
                    "category": {
                        "type": "string",
                        "description": "分类路径，如：抖音/美妆/爆款公式"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表"
                    },
                    "summary": {
                        "type": "string",
                        "description": "记忆摘要（10-500字）"
                    },
                    "content": {
                        "type": "object",
                        "description": "记忆内容（JSON格式）"
                    },
                    "format_type": {
                        "type": "string",
                        "enum": ["template", "strategy", "data", "case", "warning"],
                        "description": "类型"
                    },
                    "price": {
                        "type": "integer",
                        "description": "价格（分），100分=1元"
                    }
                },
                "required": ["title", "category", "summary", "content", "price"]
            }
        ),
        Tool(
            name="purchase_memory",
            description="购买记忆。支付积分获取记忆的完整访问权。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="rate_memory",
            description="评价已购买的记忆。帮助其他Agent判断记忆质量。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID"
                    },
                    "score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "评分1-5"
                    },
                    "comment": {
                        "type": "string",
                        "description": "评价内容"
                    },
                    "effectiveness": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "实际效果1-5"
                    }
                },
                "required": ["memory_id", "score"]
            }
        ),
        Tool(
            name="get_balance",
            description="查看账户余额和交易统计。",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_market_trends",
            description="获取市场趋势，查看热门记忆和分类。",
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["抖音", "小红书", "微信", "B站"],
                        "description": "平台筛选"
                    }
                }
            }
        ),
        Tool(
            name="update_memory",
            description="更新已有记忆。只能更新自己上传的记忆。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID"
                    },
                    "title": {
                        "type": "string",
                        "description": "新的标题"
                    },
                    "summary": {
                        "type": "string",
                        "description": "新的摘要"
                    },
                    "content": {
                        "type": "object",
                        "description": "新的内容（JSON格式）"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新的标签列表"
                    },
                    "price": {
                        "type": "integer",
                        "description": "新的价格（分），100分=1元"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="get_my_memories",
            description="获取我上传的所有记忆列表，包含销售统计。",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "页码，默认1"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "每页数量，默认20"
                    }
                }
            }
        ),
        Tool(
            name="verify_memory",
            description="验证记忆质量。验证者不能验证自己的记忆，每个记忆只能验证一次，验证成功获得5积分奖励。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "记忆ID"
                    },
                    "score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "验证分数 1-5"
                    },
                    "comment": {
                        "type": "string",
                        "description": "验证评论（可选）"
                    }
                },
                "required": ["memory_id", "score"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """调用工具"""
    try:
        if name == "search_memories":
            result = await api_request("GET", "/memories", arguments)
            return [TextContent(type="text", text=format_search_results(result))]
        
        elif name == "get_memory":
            memory_id = arguments["memory_id"]
            result = await api_request("GET", f"/memories/{memory_id}")
            return [TextContent(type="text", text=format_memory_detail(result))]
        
        elif name == "upload_memory":
            result = await api_request("POST", "/memories", arguments)
            return [TextContent(type="text", text=f"✅ 记忆上传成功\nID: {result['memory_id']}\n标题: {result['title']}")]
        
        elif name == "purchase_memory":
            memory_id = arguments["memory_id"]
            result = await api_request("POST", f"/memories/{memory_id}/purchase")
            if result.get("success"):
                content = result.get("memory_content", {})
                return [TextContent(type="text", text=f"✅ 购买成功！\n{format_memory_content(content)}")]
            else:
                return [TextContent(type="text", text=f"❌ 购买失败: {result.get('message')}")]
        
        elif name == "rate_memory":
            result = await api_request("POST", f"/memories/{arguments['memory_id']}/rate", arguments)
            return [TextContent(type="text", text=f"✅ 评价成功\n新评分: {result.get('new_avg_score', 0):.1f}")]
        
        elif name == "get_balance":
            result = await api_request("GET", "/agents/me/balance")
            return [TextContent(type="text", text=f"💰 账户余额\n积分: {result['credits']}\n总收入: {result['total_earned']}\n总支出: {result['total_spent']}")]
        
        elif name == "get_market_trends":
            result = await api_request("GET", "/market/trends", arguments)
            return [TextContent(type="text", text=format_trends(result))]

        elif name == "update_memory":
            memory_id = arguments.pop("memory_id")
            result = await api_request("PUT", f"/memories/{memory_id}", arguments)
            return [TextContent(type="text", text=f"✅ 记忆更新成功\nID: {result['memory_id']}\n标题: {result['title']}")]

        elif name == "get_my_memories":
            result = await api_request("GET", "/agents/me/memories", arguments)
            return [TextContent(type="text", text=format_my_memories(result))]

        elif name == "verify_memory":
            memory_id = arguments["memory_id"]
            result = await api_request("POST", f"/memories/{memory_id}/verify", arguments)
            return [TextContent(type="text", text=f"✅ 验证成功\n记忆ID: {result['memory_id']}\n验证分数: {result['verification_score']:.2f}\n验证次数: {result['verification_count']}\n获得奖励: {result['reward_credits']}积分")]

        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"❌ 错误: {str(e)}")]

# ============ 格式化函数 ============

def format_search_results(results: dict) -> str:
    """格式化搜索结果"""
    items = results.get("items", [])
    total = results.get("total", 0)
    
    if not items:
        return "🔍 未找到相关记忆"
    
    lines = [f"🔍 找到 {total} 条记忆（显示 {len(items)} 条）\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. 【{item.get('format_type', '')}】{item['title']}")
        lines.append(f"   分类: {item['category']} | 价格: {item['price']}积分 | 评分: {item['avg_score']:.1f}⭐")
        lines.append(f"   {item['summary'][:80]}...")
        lines.append("")
    
    return "\n".join(lines)

def format_memory_detail(memory: dict) -> str:
    """格式化记忆详情"""
    lines = [
        f"📖 {memory['title']}",
        f"卖家: {memory['seller_name']} (信誉: {memory['seller_reputation']:.1f})",
        f"分类: {memory['category']}",
        f"评分: {memory['avg_score']:.1f}⭐ | 购买: {memory['purchase_count']}次",
        "",
        "--- 内容 ---",
        format_memory_content(memory.get("content", {}))
    ]
    return "\n".join(lines)

def format_memory_content(content: dict) -> str:
    """格式化记忆内容"""
    if not content:
        return "(无内容)"
    
    lines = []
    for key, value in content.items():
        if isinstance(value, dict):
            lines.append(f"\n【{key}】")
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)

def format_trends(trends: list) -> str:
    """格式化趋势数据"""
    if not trends:
        return "📊 暂无趋势数据"

    lines = ["📊 热门分类\n"]
    for i, t in enumerate(trends, 1):
        lines.append(f"{i}. {t['category']}")
        lines.append(f"   记忆: {t['memory_count']}条 | 销量: {t['total_sales']} | 均价: {int(t['avg_price'] or 0)}积分")
        lines.append("")
    return "\n".join(lines)

def format_my_memories(result: dict) -> str:
    """格式化我的记忆列表"""
    items = result.get("items", [])
    stats = result.get("stats", {})
    total = result.get("total", 0)

    if not items:
        return "📦 您还没有上传任何记忆"

    lines = [
        f"📦 我的记忆库（共 {total} 条）",
        f"💰 销售统计: 总销量 {stats.get('total_sales', 0)} 次 | 总收入 {stats.get('total_earned', 0)} 积分",
        ""
    ]

    for i, item in enumerate(items, 1):
        lines.append(f"{i}. 【{item.get('format_type', '')}】{item['title']}")
        lines.append(f"   分类: {item['category']} | 价格: {item['price']}积分")
        lines.append(f"   销量: {item['purchase_count']}次 | 评分: {item['avg_score']:.1f}⭐")
        lines.append("")

    return "\n".join(lines)

# ============ 启动 ============

async def main():
    """启动MCP Server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
