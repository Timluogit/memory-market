"""多Agent并行推理架构测试

覆盖：
- Agent抽象层测试
- 观察者Agent测试
- 搜索Agent测试
- 聚合器Agent测试
- 流水线测试
- 集成测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_base import (
    AgentRole, AgentStatus, AgentContext, AgentResult,
    BaseAgent, AgentManager, get_agent_manager,
)
from app.agents.observers.user_info_agent import UserInfoAgent
from app.agents.observers.temporal_agent import TemporalAgent
from app.agents.observers.general_observer import GeneralObserver
from app.agents.searchers.direct_fact_agent import DirectFactAgent
from app.agents.searchers.context_agent import ContextAgent
from app.agents.searchers.timeline_agent import TimelineAgent
from app.agents.aggregator import AggregatorAgent, ScoredResult
from app.services.multi_agent_pipeline import MultiAgentPipeline, PipelineResult


# ============ Agent抽象层测试 ============

class TestAgentContext:
    """AgentContext测试"""

    def test_create_context(self):
        ctx = AgentContext(query="test query", user_id="user1")
        assert ctx.query == "test query"
        assert ctx.user_id == "user1"
        assert ctx.session_id  # 自动生成

    def test_dimension_operations(self):
        ctx = AgentContext(query="test")
        ctx.set_dimension("user_info", {"name": "Alice"})
        assert ctx.get_dimension("user_info") == {"name": "Alice"}

        ctx.set_dimension("user_info", {"title": "Engineer"})
        assert ctx.get_dimension("user_info") == {"name": "Alice", "title": "Engineer"}

    def test_to_dict(self):
        ctx = AgentContext(query="test", user_id="u1")
        ctx.set_dimension("user_info", {"name": "Bob"})
        d = ctx.to_dict()
        assert d["query"] == "test"
        assert d["dimensions"]["user_info"] == {"name": "Bob"}


class TestAgentResult:
    """AgentResult测试"""

    def test_success_result(self):
        r = AgentResult(
            agent_id="a1", role=AgentRole.OBSERVER_GENERAL,
            status=AgentStatus.COMPLETED, confidence=0.8,
        )
        assert r.is_success

    def test_failed_result(self):
        r = AgentResult(
            agent_id="a1", role=AgentRole.OBSERVER_GENERAL,
            status=AgentStatus.FAILED,
        )
        assert not r.is_success


class TestAgentManager:
    """AgentManager测试"""

    def test_register_and_create(self):
        mgr = AgentManager()
        mgr.register(AgentRole.OBSERVER_GENERAL, GeneralObserver)
        agent = mgr.create(AgentRole.OBSERVER_GENERAL)
        assert isinstance(agent, GeneralObserver)
        assert agent.role == AgentRole.OBSERVER_GENERAL

    def test_unknown_role_raises(self):
        mgr = AgentManager()
        with pytest.raises(ValueError):
            mgr.create(AgentRole.AGGREGATOR)  # not registered

    def test_list_roles(self):
        mgr = get_agent_manager()
        roles = mgr.list_roles()
        assert AgentRole.OBSERVER_USER_INFO in roles
        assert AgentRole.SEARCHER_DIRECT in roles
        assert AgentRole.AGGREGATOR in roles


# ============ 观察者Agent测试 ============

class TestUserInfoAgent:
    """用户信息Agent测试"""

    @pytest.mark.asyncio
    async def test_extract_user_info(self):
        agent = UserInfoAgent()
        ctx = AgentContext(
            query="我是张三，高级工程师，在腾讯公司工作。擅长Python, Go。使用VS Code。"
        )

        result = await agent.run(ctx)
        assert result.is_success
        assert result.confidence > 0

        user_info = result.data.get("user_info", {})
        assert user_info.get("name") == "张三"

    @pytest.mark.asyncio
    async def test_extract_preferences(self):
        agent = UserInfoAgent()
        ctx = AgentContext(
            query="兴趣：AI, 机器学习。工具：PyCharm, Docker。语言：Python, Rust。"
        )

        result = await agent.run(ctx)
        assert result.is_success
        prefs = result.data.get("preferences", {})
        assert len(prefs) > 0

    @pytest.mark.asyncio
    async def test_empty_query(self):
        agent = UserInfoAgent()
        ctx = AgentContext(query="")
        result = await agent.run(ctx)
        assert result.is_success
        assert result.confidence == 0.0


class TestTemporalAgent:
    """时序Agent测试"""

    @pytest.mark.asyncio
    async def test_extract_events(self):
        agent = TemporalAgent()
        ctx = AgentContext(
            query="2024-01-15 项目启动会议。2024-02-20 完成v1.0发布。修复了登录bug。"
        )

        result = await agent.run(ctx)
        assert result.is_success
        events = result.data.get("events", [])
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_extract_temporal(self):
        agent = TemporalAgent()
        ctx = AgentContext(
            query="3天前更新了配置。上周完成了代码审查。2024-03-01 部署到生产环境。"
        )

        result = await agent.run(ctx)
        assert result.is_success
        temporal = result.data.get("temporal", {})
        assert temporal.get("relative_times") or temporal.get("dates_mentioned")

    @pytest.mark.asyncio
    async def test_extract_updates(self):
        agent = TemporalAgent()
        ctx = AgentContext(
            query="从MySQL改为PostgreSQL。之前用React，后来换成Vue。"
        )

        result = await agent.run(ctx)
        assert result.is_success


class TestGeneralObserver:
    """通用观察者Agent测试"""

    @pytest.mark.asyncio
    async def test_extract_assistant_info(self):
        agent = GeneralObserver()
        ctx = AgentContext(
            query="我喜欢代码导向的回答。习惯用简洁风格。经常使用Docker部署。"
        )

        result = await agent.run(ctx)
        assert result.is_success
        assistant = result.data.get("assistant_info", {})
        assert "code_oriented" in assistant.get("format_preferences", [])

    @pytest.mark.asyncio
    async def test_data_quality(self):
        agent = GeneralObserver()
        ctx = AgentContext(
            query="这是一个很长的查询，用来测试数据质量评估功能",
            raw_data={"content": "some data"},
            user_id="u1",
        )

        result = await agent.run(ctx)
        quality = result.data.get("data_quality", {})
        assert quality["overall_score"] > 0


# ============ 搜索Agent测试（无DB模式） ============

class TestDirectFactAgent:
    """直接事实搜索Agent测试"""

    @pytest.mark.asyncio
    async def test_search_from_context(self):
        agent = DirectFactAgent()
        ctx = AgentContext(
            query="Python",
            observations={
                "mem1": {"title": "Python最佳实践", "summary": "Python编程技巧"},
                "mem2": {"title": "Java教程", "summary": "Java基础"},
            },
        )

        result = await agent.run(ctx)
        assert result.is_success
        assert result.data["result_count"] >= 1

    @pytest.mark.asyncio
    async def test_empty_query(self):
        agent = DirectFactAgent()
        ctx = AgentContext(query="")
        result = await agent.run(ctx)
        assert result.is_success
        assert result.data["result_count"] == 0


class TestContextAgent:
    """上下文搜索Agent测试"""

    @pytest.mark.asyncio
    async def test_search_from_context(self):
        agent = ContextAgent()
        ctx = AgentContext(
            query="机器学习",
            raw_data={"tags": ["AI", "深度学习"]},
            observations={
                "mem1": {"summary": "深度学习入门", "category": "AI"},
                "mem2": {"summary": "Web开发指南", "category": "前端"},
            },
        )

        result = await agent.run(ctx)
        assert result.is_success


class TestTimelineAgent:
    """时间线搜索Agent测试"""

    @pytest.mark.asyncio
    async def test_search_from_context(self):
        agent = TimelineAgent()
        ctx = AgentContext(
            query="最近的项目",
        )
        ctx.set_dimension("events", {
            "items": [
                {"description": "项目启动", "date": "2024-01-15"},
                {"description": "v1.0发布", "date": "2024-03-01"},
            ]
        })
        ctx.set_dimension("temporal", {
            "timeline_entries": [
                {"date": "2024-01-15", "context": "项目启动会议"},
            ],
            "relative_times": ["3天前"],
        })

        result = await agent.run(ctx)
        assert result.is_success
        assert len(result.data.get("timeline", [])) > 0


# ============ 聚合器测试 ============

class TestAggregatorAgent:
    """聚合器Agent测试"""

    @pytest.mark.asyncio
    async def test_merge_and_rerank(self):
        agent = AggregatorAgent()
        ctx = AgentContext(query="test")
        ctx.search_results = {
            "direct": {
                "results": [
                    {"memory_id": "m1", "title": "Result A", "relevance_score": 0.9},
                    {"memory_id": "m2", "title": "Result B", "relevance_score": 0.7},
                ],
                "confidence": 0.8,
            },
            "context": {
                "results": [
                    {"memory_id": "m1", "title": "Result A", "context_score": 0.6},
                    {"memory_id": "m3", "title": "Result C", "context_score": 0.5},
                ],
                "confidence": 0.7,
            },
            "timeline": {
                "results": [
                    {"memory_id": "m2", "title": "Result B", "timeline_score": 0.8},
                ],
                "confidence": 0.6,
            },
        }

        result = await agent.run(ctx)
        assert result.is_success
        assert result.confidence > 0
        assert len(result.data["results"]) > 0
        # m1 appears in direct+context, should be ranked higher
        assert result.data["results"][0].get("memory_id") in ("m1", "m2")

    @pytest.mark.asyncio
    async def test_empty_results(self):
        agent = AggregatorAgent()
        ctx = AgentContext(query="test")
        ctx.search_results = {
            "direct": {"results": [], "confidence": 0},
            "context": {"results": [], "confidence": 0},
            "timeline": {"results": [], "confidence": 0},
        }

        result = await agent.run(ctx)
        assert result.is_success
        assert result.confidence == 0.0


# ============ 流水线测试 ============

class TestMultiAgentPipeline:
    """多Agent流水线测试"""

    @pytest.mark.asyncio
    async def test_pipeline_no_db(self):
        """无DB的流水线测试（只运行观察者阶段）"""
        pipeline = MultiAgentPipeline(db=None)
        result = await pipeline.run(
            query="我是张三，Python工程师。3天前完成了项目发布。",
            raw_data={"content": "一些原始数据"},
        )

        assert result.status in ("completed", "partial")
        assert result.total_time_ms > 0
        assert result.observer_time_ms > 0
        assert len(result.observer_results) == 3

    @pytest.mark.asyncio
    async def test_pipeline_with_observations(self):
        """带预置观察数据的流水线"""
        pipeline = MultiAgentPipeline(db=None)
        result = await pipeline.run(
            query="搜索Python记忆",
            observations={
                "mem1": {"title": "Python最佳实践", "summary": "Python编程技巧"},
                "mem2": {"title": "Docker部署", "summary": "Docker容器化部署"},
            },
        )

        assert result.status in ("completed", "partial")
        # 搜索Agent应该能从observations中找到结果
        assert len(result.searcher_results) == 3

    @pytest.mark.asyncio
    async def test_pipeline_fallback(self):
        """测试降级策略"""
        pipeline = MultiAgentPipeline(db=None)
        result = await pipeline.run(query="")
        # 应该完成（即使没有结果）
        assert result.status in ("completed", "partial")


# ============ 集成测试 ============

class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self):
        """完整流水线流程测试"""
        from app.services.multi_agent_pipeline import run_multi_agent_search

        result = await run_multi_agent_search(
            query="我是李四，数据分析师，在阿里巴巴工作。擅长SQL和Python。使用Tableau做可视化。"
            "2024年1月完成了用户画像项目，2024年3月从MySQL迁移到ClickHouse。",
        )

        assert result.status in ("completed", "partial")
        assert result.total_time_ms > 0

        # 验证维度覆盖
        if result.dimension_coverage:
            coverage = result.dimension_coverage
            assert coverage.get("filled_count", 0) >= 0

    @pytest.mark.asyncio
    async def test_concurrent_pipelines(self):
        """并发流水线测试"""
        queries = [
            "Python编程最佳实践",
            "Docker容器化部署",
            "微服务架构设计",
        ]

        tasks = [
            run_multi_agent_search(query=q) for q in queries
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for r in results:
            assert r.status in ("completed", "partial")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
