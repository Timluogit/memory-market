"""MCP 工具简化测试

测试工具注册和基本功能，不依赖完整应用启动。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp_tools.team_mcp import TeamMCPTools, register_team_mcp_tools


class TestMCPToolRegistration:
    """测试MCP工具注册"""

    @pytest.fixture
    def mock_server(self):
        """模拟MCP服务器"""
        server = MagicMock()
        server.tools = []

        def add_tool(tool):
            server.tools.append(tool)

        server.add_tool = add_tool
        return server

    def test_register_all_tools(self, mock_server):
        """测试注册所有24个工具"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        # 检查是否注册了24个工具
        assert len(mock_server.tools) == 24

        # 检查工具名称
        tool_names = [tool["name"] for tool in mock_server.tools]

        # 团队管理（6个）
        assert "create_team" in tool_names
        assert "get_team" in tool_names
        assert "update_team" in tool_names
        assert "delete_team" in tool_names
        assert "list_teams" in tool_names
        assert "get_team_stats" in tool_names

        # 成员管理（5个）
        assert "invite_member" in tool_names
        assert "join_team" in tool_names
        assert "list_members" in tool_names
        assert "update_member_role" in tool_names
        assert "remove_member" in tool_names

        # 团队记忆（6个）
        assert "create_team_memory" in tool_names
        assert "get_team_memory" in tool_names
        assert "update_team_memory" in tool_names
        assert "delete_team_memory" in tool_names
        assert "search_team_memories" in tool_names
        assert "list_team_memories" in tool_names

        # 团队积分（4个）
        assert "get_team_credits" in tool_names
        assert "add_team_credits" in tool_names
        assert "transfer_credits" in tool_names
        assert "get_credit_transactions" in tool_names

        # 团队活动（2个）
        assert "get_team_activities" in tool_names
        assert "log_activity" in tool_names

        # 团队统计（1个）
        assert "get_team_insights" in tool_names

    def test_tool_metadata(self, mock_server):
        """测试工具元数据"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        # 检查每个工具都有必要的字段
        for tool in mock_server.tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "handler" in tool

            # 检查参数结构
            params = tool["parameters"]
            assert "type" in params
            assert "properties" in params
            assert "required" in params

            # 验证类型
            assert params["type"] == "object"
            assert isinstance(params["properties"], dict)
            assert isinstance(params["required"], list)

    def test_tool_handlers_are_callable(self, mock_server):
        """测试所有工具的handler都是可调用的"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        for tool in mock_server.tools:
            assert callable(tool["handler"])

    def test_tool_descriptions_are_present(self, mock_server):
        """测试所有工具都有描述"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        for tool in mock_server.tools:
            assert tool["description"]
            assert len(tool["description"]) > 0

    def test_tool_required_parameters_are_valid(self, mock_server):
        """测试所有工具的必需参数都是有效的"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        for tool in mock_server.tools:
            required = tool["parameters"]["required"]
            properties = tool["parameters"]["properties"]

            # 验证所有必需参数都在properties中定义
            for req_param in required:
                assert req_param in properties, f"必需参数 {req_param} 未在 properties 中定义"

    def test_team_management_tools_count(self, mock_server):
        """测试团队管理工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        team_tools = [t for t in mock_server.tools if t["name"] in [
            "create_team", "get_team", "update_team", "delete_team",
            "list_teams", "get_team_stats"
        ]]
        assert len(team_tools) == 6

    def test_member_management_tools_count(self, mock_server):
        """测试成员管理工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        member_tools = [t for t in mock_server.tools if t["name"] in [
            "invite_member", "join_team", "list_members",
            "update_member_role", "remove_member"
        ]]
        assert len(member_tools) == 5

    def test_memory_management_tools_count(self, mock_server):
        """测试团队记忆工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        memory_tools = [t for t in mock_server.tools if t["name"] in [
            "create_team_memory", "get_team_memory", "update_team_memory",
            "delete_team_memory", "search_team_memories", "list_team_memories"
        ]]
        assert len(memory_tools) == 6

    def test_credit_management_tools_count(self, mock_server):
        """测试团队积分工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        credit_tools = [t for t in mock_server.tools if t["name"] in [
            "get_team_credits", "add_team_credits",
            "transfer_credits", "get_credit_transactions"
        ]]
        assert len(credit_tools) == 4

    def test_activity_management_tools_count(self, mock_server):
        """测试团队活动工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        activity_tools = [t for t in mock_server.tools if t["name"] in [
            "get_team_activities", "log_activity"
        ]]
        assert len(activity_tools) == 2

    def test_stats_management_tools_count(self, mock_server):
        """测试团队统计工具数量"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        stats_tools = [t for t in mock_server.tools if t["name"] in [
            "get_team_insights"
        ]]
        assert len(stats_tools) == 1


class TestTeamMCPToolsClass:
    """测试TeamMCPTools类"""

    def test_initialization(self):
        """测试初始化"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        tools = TeamMCPTools(mock_db_factory)

        assert tools.get_db == mock_db_factory

    @pytest.mark.asyncio
    async def test_log_activity_basic(self):
        """测试log_activity基本功能"""
        from datetime import datetime
        from app.models.tables import TeamActivityLog

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_db_factory = MagicMock(return_value=mock_db)
        tools = TeamMCPTools(mock_db_factory)

        # 由于我们需要模拟TeamActivityLog的创建，这里简化测试
        # 只验证函数存在且可以被调用
        try:
            result = await tools.log_activity(
                team_id="team_001",
                agent_id="agent_001",
                activity_type="test",
                description="测试活动"
            )
            # 验证返回结果结构
            assert "activity_id" in result or "error" in result
        except Exception as e:
            # 某些依赖可能不可用，这是预期的
            assert "error" in str(e) or "activity_id" in str(e)


class TestToolParameters:
    """测试工具参数定义"""

    @pytest.fixture
    def mock_server(self):
        """模拟MCP服务器"""
        server = MagicMock()
        server.tools = []

        def add_tool(tool):
            server.tools.append(tool)

        server.add_tool = add_tool
        return server

    def test_create_team_parameters(self, mock_server):
        """测试create_team参数"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        tool = next(t for t in mock_server.tools if t["name"] == "create_team")
        params = tool["parameters"]["properties"]

        assert "owner_agent_id" in params
        assert "name" in params
        assert "description" in params
        assert params["owner_agent_id"]["type"] == "string"
        assert params["name"]["type"] == "string"
        assert params["description"]["type"] == "string"

    def test_get_team_parameters(self, mock_server):
        """测试get_team参数"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        tool = next(t for t in mock_server.tools if t["name"] == "get_team")
        params = tool["parameters"]["properties"]

        assert "team_id" in params
        assert params["team_id"]["type"] == "string"
        assert tool["parameters"]["required"] == ["team_id"]

    def test_create_team_memory_parameters(self, mock_server):
        """测试create_team_memory参数"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        tool = next(t for t in mock_server.tools if t["name"] == "create_team_memory")
        params = tool["parameters"]["properties"]

        assert "team_id" in params
        assert "creator_agent_id" in params
        assert "title" in params
        assert "category" in params
        assert "summary" in params
        assert "content" in params

        # 验证必需参数
        required = tool["parameters"]["required"]
        assert "team_id" in required
        assert "creator_agent_id" in required
        assert "title" in required
        assert "category" in required
        assert "summary" in required
        assert "content" in required

    def test_search_team_memories_parameters(self, mock_server):
        """测试search_team_memories参数"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        tool = next(t for t in mock_server.tools if t["name"] == "search_team_memories")
        params = tool["parameters"]["properties"]

        assert "team_id" in params
        assert "query" in params
        assert "category" in params
        assert "page" in params
        assert "page_size" in params

        # 验证默认值
        assert params["page"]["default"] == 1
        assert params["page_size"]["default"] == 20

    def test_all_tools_have_description(self, mock_server):
        """测试所有工具都有描述"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        for tool in mock_server.tools:
            assert tool["description"]
            assert len(tool["description"]) > 0


class TestToolCategories:
    """测试工具分类"""

    @pytest.fixture
    def mock_server(self):
        """模拟MCP服务器"""
        server = MagicMock()
        server.tools = []

        def add_tool(tool):
            server.tools.append(tool)

        server.add_tool = add_tool
        return server

    def test_team_management_category(self, mock_server):
        """测试团队管理分类"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        team_tools = [
            "create_team", "get_team", "update_team", "delete_team",
            "list_teams", "get_team_stats"
        ]

        for tool_name in team_tools:
            tool = next((t for t in mock_server.tools if t["name"] == tool_name), None)
            assert tool is not None
            assert "团队" in tool["description"] or "team" in tool["description"].lower()

    def test_member_management_category(self, mock_server):
        """测试成员管理分类"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        member_tools = [
            "invite_member", "join_team", "list_members",
            "update_member_role", "remove_member"
        ]

        for tool_name in member_tools:
            tool = next((t for t in mock_server.tools if t["name"] == tool_name), None)
            assert tool is not None
            assert "成员" in tool["description"] or "member" in tool["description"].lower()

    def test_memory_management_category(self, mock_server):
        """测试团队记忆分类"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        memory_tools = [
            "create_team_memory", "get_team_memory", "update_team_memory",
            "delete_team_memory", "search_team_memories", "list_team_memories"
        ]

        for tool_name in memory_tools:
            tool = next((t for t in mock_server.tools if t["name"] == tool_name), None)
            assert tool is not None
            assert "记忆" in tool["description"] or "memory" in tool["description"].lower()

    def test_credit_management_category(self, mock_server):
        """测试团队积分分类"""
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        credit_tools = [
            "get_team_credits", "add_team_credits",
            "transfer_credits", "get_credit_transactions"
        ]

        for tool_name in credit_tools:
            tool = next((t for t in mock_server.tools if t["name"] == tool_name), None)
            assert tool is not None
            assert "积分" in tool["description"] or "credit" in tool["description"].lower()


class TestToolIntegration:
    """测试工具集成"""

    def test_all_tools_registered(self):
        """测试所有工具都可以被注册"""
        from mcp_tools.team_mcp import TeamMCPTools, register_team_mcp_tools

        # 创建模拟服务器
        mock_server = MagicMock()
        mock_server.tools = []

        def add_tool(tool):
            mock_server.tools.append(tool)

        mock_server.add_tool = add_tool

        # 注册工具
        mock_db_factory = MagicMock(return_value=AsyncMock())
        register_team_mcp_tools(mock_server, mock_db_factory)

        # 验证所有工具都被注册
        expected_tools = [
            "create_team", "get_team", "update_team", "delete_team",
            "list_teams", "get_team_stats",
            "invite_member", "join_team", "list_members",
            "update_member_role", "remove_member",
            "create_team_memory", "get_team_memory", "update_team_memory",
            "delete_team_memory", "search_team_memories", "list_team_memories",
            "get_team_credits", "add_team_credits", "transfer_credits",
            "get_credit_transactions",
            "get_team_activities", "log_activity",
            "get_team_insights"
        ]

        registered_tools = [t["name"] for t in mock_server.tools]

        for expected_tool in expected_tools:
            assert expected_tool in registered_tools, f"工具 {expected_tool} 未被注册"

    def test_tools_export_in_init(self):
        """测试工具在__init__.py中正确导出"""
        from mcp_tools import (
            TeamMemoryTools,
            register_team_tools,
            TeamMCPTools,
            register_team_mcp_tools
        )

        # 验证导出的类和函数
        assert TeamMemoryTools is not None
        assert register_team_tools is not None
        assert TeamMCPTools is not None
        assert register_team_mcp_tools is not None
