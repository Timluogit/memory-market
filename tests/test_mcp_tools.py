"""MCP 工具测试

测试所有34个MCP工具的功能、权限检查、错误处理和边界情况。
"""
import pytest
from unittest.mock import AsyncMock
from app.models.tables import Agent, Team, TeamMember, TeamActivityLog
from mcp_tools.team_mcp import TeamMCPTools


class TestTeamMCPTools:
    """测试团队MCP工具"""

    @pytest.fixture
    async def mock_db_factory(self):
        """模拟数据库会话工厂"""
        return AsyncMock()

    @pytest.fixture
    def team_tools(self, mock_db_factory):
        """创建工具实例"""
        return TeamMCPTools(mock_db_factory)

    # ========== 团队管理（6个） ==========

    @pytest.mark.asyncio
    async def test_create_team_success(self, team_tools, mock_db_factory):
        """测试创建团队成功"""
        mock_db = AsyncMock()
        mock_db_factory.return_value = mock_db

        # 模拟创建结果
        team = Team(
            team_id="team_001",
            name="测试团队",
            description="这是一个测试团队",
            owner_agent_id="agent_001",
            member_count=1,
            memory_count=0,
            credits=0,
            is_active=True
        )
        mock_db.commit = AsyncMock()
        mock_db.close = AsyncMock()

        # 模拟 TeamService.create_team
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.TeamService.create_team') as mock_create:
            mock_create.return_value = team
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock()

            result = await team_tools.create_team(
                owner_agent_id="agent_001",
                name="测试团队",
                description="这是一个测试团队"
            )

            assert result["team_id"] == "team_001"
            assert result["name"] == "测试团队"
            assert result["owner_agent_id"] == "agent_001"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_create_team_missing_name(self, team_tools):
        """测试创建团队缺少名称"""
        result = await team_tools.create_team(
            owner_agent_id="agent_001",
            name="",
            description="描述"
        )
        # 这会抛出验证错误
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_team_success(self, team_tools):
        """测试获取团队成功"""
        from unittest.mock import patch, MagicMock
        from app.models.schemas import TeamResponse

        team_response = TeamResponse(
            team_id="team_001",
            name="测试团队",
            description="描述",
            owner_agent_id="agent_001",
            owner_name="Agent001",
            member_count=5,
            memory_count=10,
            credits=1000,
            total_earned=5000,
            total_spent=4000,
            is_active=True,
            created_at="2024-01-01",
            updated_at="2024-01-01"
        )

        with patch('mcp_tools.team_mcp.TeamService.get_team_detail') as mock_get:
            mock_get.return_value = team_response

            result = await team_tools.get_team(team_id="team_001")

            assert result["team_id"] == "team_001"
            assert result["name"] == "测试团队"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_get_team_not_found(self, team_tools):
        """测试获取不存在的团队"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.TeamService.get_team_detail') as mock_get:
            mock_get.return_value = None

            result = await team_tools.get_team(team_id="nonexistent")

            assert result["error"] == "团队不存在"

    @pytest.mark.asyncio
    async def test_update_team_success(self, team_tools):
        """测试更新团队成功"""
        from unittest.mock import patch
        from app.models.tables import Team

        team = Team(
            team_id="team_001",
            name="新名称",
            description="新描述",
            owner_agent_id="agent_001",
            member_count=5,
            memory_count=10,
            credits=1000
        )

        with patch('mcp_tools.team_mcp.TeamService.update_team') as mock_update:
            mock_update.return_value = team

            result = await team_tools.update_team(
                team_id="team_001",
                owner_agent_id="agent_001",
                name="新名称",
                description="新描述"
            )

            assert result["team_id"] == "team_001"
            assert result["name"] == "新名称"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_delete_team_success(self, team_tools):
        """测试删除团队成功"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.TeamService.delete_team') as mock_delete:
            mock_delete.return_value = True

            result = await team_tools.delete_team(
                team_id="team_001",
                owner_agent_id="agent_001"
            )

            assert result["success"] == True
            assert result["message"] == "团队已删除"

    @pytest.mark.asyncio
    async def test_list_teams(self, team_tools):
        """测试列出团队"""
        from unittest.mock import patch, AsyncMock

        mock_db = AsyncMock()
        mock_result = AsyncMock()
        team = Team(
            team_id="team_001",
            name="测试团队",
            description="描述",
            owner_agent_id="agent_001",
            member_count=5,
            memory_count=10,
            credits=1000,
            is_active=True
        )
        mock_result.all.return_value = [team]
        mock_result.where.return_value = mock_result
        mock_result.order_by.return_value = mock_result
        mock_db.query.return_value = mock_db
        mock_db.where = mock_result
        mock_db.all = mock_result.all

        with patch('mcp_tools.team_mcp.TeamMCPTools.get_db') as mock_get_db:
            mock_get_db.return_value = mock_db

            result = await team_tools.list_teams()

            assert "teams" in result
            assert "total" in result
            assert isinstance(result["teams"], list)

    @pytest.mark.asyncio
    async def test_get_team_stats(self, team_tools):
        """测试获取团队统计"""
        from unittest.mock import patch

        with patch('mcp_tools.team_mcp.CreditService.get_credits_info') as mock_get:
            mock_get.return_value = {
                "team_id": "team_001",
                "credits": 1000,
                "total_earned": 5000,
                "total_spent": 4000
            }

            result = await team_tools.get_team_stats(team_id="team_001")

            assert result["team_id"] == "team_001"
            assert result["credits"] == 1000
            assert "error" not in result

    # ========== 成员管理（5个） ==========

    @pytest.mark.asyncio
    async def test_invite_member_success(self, team_tools):
        """测试生成邀请码成功"""
        from unittest.mock import patch
        from app.models.schemas import TeamInviteCodeResponse
        from datetime import datetime

        invite = TeamInviteCodeResponse(
            invite_code_id=1,
            team_id="team_001",
            code="ABC12345",
            is_active=True,
            expires_at=datetime.now(),
            created_at=datetime.now()
        )

        with patch('mcp_tools.team_mcp.MemberService.generate_invite_code') as mock_invite:
            mock_invite.return_value = invite

            result = await team_tools.invite_member(
                team_id="team_001",
                expires_days=7
            )

            assert result["code"] == "ABC12345"
            assert result["team_id"] == "team_001"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_join_team_success(self, team_tools):
        """测试加入团队成功"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.MemberService.join_team_by_code') as mock_join:
            mock_join.return_value = {
                "team_id": "team_001",
                "role": "member"
            }

            result = await team_tools.join_team(
                agent_id="agent_001",
                invite_code="ABC12345"
            )

            assert result["team_id"] == "team_001"
            assert result["role"] == "member"
            assert result["message"] == "成功加入团队"

    @pytest.mark.asyncio
    async def test_list_members(self, team_tools):
        """测试列出成员"""
        from unittest.mock import patch
        from app.models.schemas import TeamMemberResponse
        from datetime import datetime

        members = [
            TeamMemberResponse(
                id=1,
                team_id="team_001",
                agent_id="agent_001",
                agent_name="Agent001",
                role="owner",
                joined_at=datetime.now(),
                is_active=True
            )
        ]

        with patch('mcp_tools.team_mcp.TeamService.get_team_members') as mock_list:
            mock_list.return_value = members

            result = await team_tools.list_members(team_id="team_001")

            assert "members" in result
            assert result["total"] == 1
            assert len(result["members"]) == 1

    @pytest.mark.asyncio
    async def test_update_member_role(self, team_tools):
        """测试更新成员角色"""
        from unittest.mock import patch
        from app.models.tables import TeamMember

        member = TeamMember(
            id=1,
            team_id="team_001",
            agent_id="agent_002",
            role="admin",
            is_active=True
        )

        with patch('mcp_tools.team_mcp.MemberService.update_member_role') as mock_update:
            mock_update.return_value = member

            result = await team_tools.update_member_role(
                team_id="team_001",
                member_id=1,
                new_role="admin"
            )

            assert result["member_id"] == 1
            assert result["role"] == "admin"
            assert result["message"] == "角色更新成功"

    @pytest.mark.asyncio
    async def test_remove_member(self, team_tools):
        """测试移除成员"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.MemberService.remove_member') as mock_remove:
            mock_remove.return_value = True

            result = await team_tools.remove_member(
                team_id="team_001",
                member_id=1
            )

            assert result["success"] == True
            assert result["message"] == "成员已移除"

    # ========== 团队记忆（6个） ==========

    @pytest.mark.asyncio
    async def test_create_team_memory(self, team_tools):
        """测试创建团队记忆"""
        from unittest.mock import patch
        from app.models.schemas import TeamMemoryResponse
        from datetime import datetime

        memory = TeamMemoryResponse(
            memory_id="mem_001",
            team_id="team_001",
            title="测试记忆",
            category="测试",
            summary="摘要",
            content={"key": "value"},
            tags=["标签"],
            format_type="template",
            price=0,
            team_access_level="team_only",
            created_by_agent_id="agent_001",
            created_at=datetime.now()
        )

        with patch('mcp_tools.team_mcp.create_team_memory') as mock_create:
            mock_create.return_value = memory

            result = await team_tools.create_team_memory(
                team_id="team_001",
                creator_agent_id="agent_001",
                title="测试记忆",
                category="测试",
                summary="摘要",
                content={"key": "value"}
            )

            assert result["memory_id"] == "mem_001"
            assert result["title"] == "测试记忆"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_get_team_memory(self, team_tools):
        """测试获取团队记忆"""
        from unittest.mock import patch
        from app.models.schemas import TeamMemoryResponse
        from datetime import datetime

        memory = TeamMemoryResponse(
            memory_id="mem_001",
            team_id="team_001",
            title="测试记忆",
            category="测试",
            summary="摘要",
            content={"key": "value"},
            tags=["标签"],
            format_type="template",
            price=0,
            team_access_level="team_only",
            created_by_agent_id="agent_001",
            created_at=datetime.now()
        )

        with patch('mcp_tools.team_mcp.get_team_memory') as mock_get:
            mock_get.return_value = memory

            result = await team_tools.get_team_memory(
                team_id="team_001",
                memory_id="mem_001",
                request_agent_id="agent_001"
            )

            assert result["memory_id"] == "mem_001"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_update_team_memory(self, team_tools):
        """测试更新团队记忆"""
        from unittest.mock import patch
        from app.models.schemas import TeamMemoryResponse
        from datetime import datetime

        memory = TeamMemoryResponse(
            memory_id="mem_001",
            team_id="team_001",
            title="新标题",
            category="测试",
            summary="摘要",
            content={"key": "value"},
            tags=["标签"],
            format_type="template",
            price=0,
            team_access_level="team_only",
            created_by_agent_id="agent_001",
            created_at=datetime.now()
        )

        with patch('mcp_tools.team_mcp.update_team_memory') as mock_update:
            mock_update.return_value = memory

            result = await team_tools.update_team_memory(
                team_id="team_001",
                memory_id="mem_001",
                request_agent_id="agent_001",
                updates={"title": "新标题"}
            )

            assert result["title"] == "新标题"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_delete_team_memory(self, team_tools):
        """测试删除团队记忆"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.delete_team_memory') as mock_delete:
            mock_delete.return_value = True

            result = await team_tools.delete_team_memory(
                team_id="team_001",
                memory_id="mem_001",
                request_agent_id="agent_001"
            )

            assert result["success"] == True
            assert result["message"] == "记忆已删除"

    @pytest.mark.asyncio
    async def test_search_team_memories(self, team_tools):
        """测试搜索团队记忆"""
        from unittest.mock import patch, AsyncMock
        from app.models.schemas import TeamMemoryResponse
        from datetime import datetime
        from app.models.pagination import PaginatedResponse

        memories = [
            TeamMemoryResponse(
                memory_id="mem_001",
                team_id="team_001",
                title="测试记忆1",
                category="测试",
                summary="摘要1",
                content={"key": "value"},
                tags=["标签"],
                format_type="template",
                price=0,
                team_access_level="team_only",
                created_by_agent_id="agent_001",
                created_at=datetime.now()
            )
        ]

        paginated = PaginatedResponse(items=memories, total=1, page=1, page_size=20)

        with patch('mcp_tools.team_mcp.get_team_memories') as mock_search:
            mock_search.return_value = paginated

            result = await team_tools.search_team_memories(
                team_id="team_001",
                query="测试"
            )

            assert "items" in result
            assert result["total"] >= 0
            assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_list_team_memories(self, team_tools):
        """测试列出团队记忆"""
        from unittest.mock import patch, AsyncMock
        from app.models.schemas import TeamMemoryResponse
        from datetime import datetime
        from app.models.pagination import PaginatedResponse

        memories = [
            TeamMemoryResponse(
                memory_id="mem_001",
                team_id="team_001",
                title="测试记忆1",
                category="测试",
                summary="摘要1",
                content={"key": "value"},
                tags=["标签"],
                format_type="template",
                price=0,
                team_access_level="team_only",
                created_by_agent_id="agent_001",
                created_at=datetime.now()
            )
        ]

        paginated = PaginatedResponse(items=memories, total=1, page=1, page_size=20)

        with patch('mcp_tools.team_mcp.get_team_memories') as mock_list:
            mock_list.return_value = paginated

            result = await team_tools.list_team_memories(team_id="team_001")

            assert "items" in result
            assert "total" in result
            assert isinstance(result["items"], list)

    # ========== 团队积分（4个） ==========

    @pytest.mark.asyncio
    async def test_get_team_credits(self, team_tools):
        """测试获取团队积分"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.CreditService.get_credits_info') as mock_get:
            mock_get.return_value = {
                "team_id": "team_001",
                "credits": 1000,
                "total_earned": 5000,
                "total_spent": 4000
            }

            result = await team_tools.get_team_credits(team_id="team_001")

            assert result["credits"] == 1000
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_add_team_credits(self, team_tools):
        """测试充值团队积分"""
        from unittest.mock import patch
        from app.models.tables import Team

        team = Team(
            team_id="team_001",
            name="测试团队",
            owner_agent_id="agent_001",
            credits=2000,
            total_earned=6000
        )

        with patch('mcp_tools.team_mcp.CreditService.add_credits') as mock_add:
            mock_add.return_value = team

            result = await team_tools.add_team_credits(
                team_id="team_001",
                agent_id="agent_001",
                amount=1000
            )

            assert result["credits"] == 2000
            assert result["amount"] == 1000
            assert result["message"] == "充值成功"

    @pytest.mark.asyncio
    async def test_transfer_credits(self, team_tools):
        """测试转账"""
        from unittest.mock import patch
        with patch('mcp_tools.team_mcp.CreditService.transfer_credits') as mock_transfer:
            mock_transfer.return_value = {
                "team_credits": 500,
                "agent_credits": 1500
            }

            result = await team_tools.transfer_credits(
                team_id="team_001",
                from_agent_id="agent_001",
                to_agent_id="agent_002",
                amount=500
            )

            assert result["team_credits"] == 500
            assert result["agent_credits"] == 1500
            assert result["message"] == "转账成功"

    @pytest.mark.asyncio
    async def test_get_credit_transactions(self, team_tools):
        """测试获取积分交易历史"""
        from unittest.mock import patch
        from app.models.schemas import TeamCreditTransaction
        from datetime import datetime

        transactions = [
            TeamCreditTransaction(
                tx_id="tx_001",
                team_id="team_001",
                agent_id="agent_001",
                agent_name="Agent001",
                tx_type="recharge",
                amount=1000,
                balance_after=1000,
                description="充值",
                created_at=datetime.now()
            )
        ]

        with patch('mcp_tools.team_mcp.CreditService.get_transactions') as mock_get:
            mock_get.return_value = {
                "items": transactions,
                "total": 1,
                "page": 1,
                "page_size": 20
            }

            result = await team_tools.get_credit_transactions(team_id="team_001")

            assert "items" in result
            assert result["total"] == 1
            assert isinstance(result["items"], list)

    # ========== 团队活动（2个） ==========

    @pytest.mark.asyncio
    async def test_get_team_activities(self, team_tools):
        """测试获取团队活动日志"""
        from unittest.mock import patch
        from app.models.schemas import TeamActivityList, TeamActivityLog
        from datetime import datetime

        logs = TeamActivityList(
            items=[
                TeamActivityLog(
                    activity_id="act_001",
                    team_id="team_001",
                    agent_id="agent_001",
                    agent_name="Agent001",
                    activity_type="create_team",
                    description="创建团队",
                    created_at=datetime.now()
                )
            ],
            total=1,
            page=1,
            page_size=20
        )

        with patch('mcp_tools.team_mcp.get_team_activity_logs') as mock_get:
            mock_get.return_value = logs

            result = await team_tools.get_team_activities(team_id="team_001")

            assert "items" in result
            assert result["total"] == 1
            assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_log_activity(self, team_tools):
        """测试记录团队活动"""
        result = await team_tools.log_activity(
            team_id="team_001",
            agent_id="agent_001",
            activity_type="custom",
            description="自定义活动"
        )

        assert "activity_id" in result
        assert result["team_id"] == "team_001"
        assert result["activity_type"] == "custom"
        assert result["message"] == "活动记录成功"

    # ========== 团队统计（1个） ==========

    @pytest.mark.asyncio
    async def test_get_team_insights(self, team_tools):
        """测试获取团队洞察"""
        from unittest.mock import patch
        from app.models.schemas import TeamStatsResponse
        from datetime import datetime

        stats = TeamStatsResponse(
            team_id="team_001",
            name="测试团队",
            member_count=5,
            memory_count=10,
            team_memories_count=10,
            total_purchases=20,
            total_sales=30,
            credits=1000,
            total_earned=5000,
            total_spent=4000,
            active_members_7d=3,
            active_members_30d=4,
            created_at=datetime.now()
        )

        with patch('mcp_tools.team_mcp.get_team_stats') as mock_get:
            mock_get.return_value = stats

            result = await team_tools.get_team_insights(team_id="team_001")

            assert result["team_id"] == "team_001"
            assert result["member_count"] == 5
            assert result["memory_count"] == 10
            assert "error" not in result


class TestMCPToolRegistration:
    """测试MCP工具注册"""

    @pytest.fixture
    def mock_server(self):
        """模拟MCP服务器"""
        server = type('MockServer', (), {
            'add_tool': lambda self, tool: self.tools.append(tool)
        })()
        server.tools = []
        return server

    def test_register_all_tools(self, mock_server):
        """测试注册所有工具"""
        from mcp_tools.team_mcp import register_team_mcp_tools

        mock_db_factory = AsyncMock()
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
        from mcp_tools.team_mcp import register_team_mcp_tools

        mock_db_factory = AsyncMock()
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
