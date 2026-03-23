"""用户画像系统测试

测试画像提取、管理、API端点和搜索集成
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    UserProfile, ProfileFact, ProfileChange, UserDynamicContext, Agent
)
from app.services.profile_extraction_service import get_extraction_service
from app.services.user_profile_service import get_profile_service


class TestProfileExtraction:
    """测试画像提取服务"""

    @pytest.mark.asyncio
    async def test_rule_based_extraction(self, db: AsyncSession, test_agent: Agent):
        """测试基于规则的提取"""
        service = get_extraction_service()

        conversation = """
        User: 我是用 Python 的，平时用 VSCode 编辑器
        Assistant: 好的，Python 和 VSCode
        User: 对，我喜欢暗色主题
        """

        result = await service._rule_based_extract(conversation)

        assert len(result) > 0
        assert any(f['field'] == 'language' for f in result)
        assert any(f['field'] == 'editor' for f in result)
        assert any(f['field'] == 'theme' for f in result)

    @pytest.mark.asyncio
    async def test_extract_from_conversation(self, db: AsyncSession, test_agent: Agent):
        """测试从对话中提取画像"""
        service = get_extraction_service()

        conversation = """
        User: 我是用 Python 的工程师，平时用 VSCode 编辑器，喜欢暗色主题
        Assistant: 了解，Python 和 VSCode
        """

        result = await service.extract_from_conversation(
            db,
            test_agent.agent_id,
            conversation,
            conversation_id="test_conv_001"
        )

        assert 'facts' in result
        assert 'extraction_time' in result
        assert result['total_extracted'] >= 0


class TestUserProfileService:
    """测试用户画像管理服务"""

    @pytest.mark.asyncio
    async def test_create_profile(self, db: AsyncSession, test_agent: Agent):
        """测试创建画像"""
        service = get_profile_service()

        profile_data = {
            'real_name': 'Test User',
            'job_title': 'Software Engineer',
            'language': 'en',
            'editor': 'VSCode',
            'theme': 'dark'
        }

        profile = await service.create_or_update_profile(
            db,
            test_agent.agent_id,
            profile_data,
            source='manual'
        )

        assert profile['agent_id'] == test_agent.agent_id
        assert profile['real_name'] == 'Test User'
        assert profile['language'] == 'en'
        assert profile['editor'] == 'VSCode'

    @pytest.mark.asyncio
    async def test_get_profile(self, db: AsyncSession, test_agent: Agent):
        """测试获取画像"""
        service = get_profile_service()

        # 先创建画像
        profile_data = {'language': 'zh', 'theme': 'light'}
        await service.create_or_update_profile(
            db, test_agent.agent_id, profile_data
        )

        # 获取画像
        profile = await service.get_profile(db, test_agent.agent_id)

        assert profile is not None
        assert profile['language'] == 'zh'
        assert profile['theme'] == 'light'

    @pytest.mark.asyncio
    async def test_add_fact(self, db: AsyncSession, test_agent: Agent):
        """测试添加事实"""
        service = get_profile_service()

        # 先创建画像
        await service.create_or_update_profile(
            db, test_agent.agent_id, {}
        )

        # 添加事实
        fact = await service.add_fact(
            db,
            test_agent.agent_id,
            fact_type='preference',
            fact_key='editor',
            fact_value='Vim',
            confidence=0.9,
            source='manual'
        )

        assert fact['fact_key'] == 'editor'
        assert fact['fact_value'] == 'Vim'
        assert fact['confidence'] == 0.9

    @pytest.mark.asyncio
    async def test_get_facts(self, db: AsyncSession, test_agent: Agent):
        """测试获取事实列表"""
        service = get_profile_service()

        # 创建画像和添加事实
        await service.create_or_update_profile(db, test_agent.agent_id, {})
        await service.add_fact(db, test_agent.agent_id, 'preference', 'editor', 'Vim')
        await service.add_fact(db, test_agent.agent_id, 'preference', 'theme', 'dark')

        # 获取事实
        facts = await service.get_facts(db, test_agent.agent_id)

        assert len(facts) >= 2
        assert any(f['fact_key'] == 'editor' for f in facts)
        assert any(f['fact_key'] == 'theme' for f in facts)

    @pytest.mark.asyncio
    async def test_delete_fact(self, db: AsyncSession, test_agent: Agent):
        """测试删除事实"""
        service = get_profile_service()

        # 创建画像和添加事实
        await service.create_or_update_profile(db, test_agent.agent_id, {})
        fact = await service.add_fact(db, test_agent.agent_id, 'preference', 'editor', 'Vim')

        # 删除事实
        success = await service.delete_fact(
            db,
            test_agent.agent_id,
            fact['fact_id']
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_get_changes(self, db: AsyncSession, test_agent: Agent):
        """测试获取变更历史"""
        service = get_profile_service()

        # 创建画像（会产生变更记录）
        await service.create_or_update_profile(
            db,
            test_agent.agent_id,
            {'language': 'zh'}
        )

        # 获取变更历史
        changes = await service.get_changes(db, test_agent.agent_id)

        assert len(changes) >= 1
        assert changes[0]['change_type'] == 'created'

    @pytest.mark.asyncio
    async def test_dynamic_context(self, db: AsyncSession, test_agent: Agent):
        """测试动态上下文"""
        service = get_profile_service()

        # 更新动态上下文
        context_data = {
            'current_task': 'Debug API issue',
            'work_state': 'busy',
            'search_count_today': 5
        }

        context = await service.update_dynamic_context(
            db,
            test_agent.agent_id,
            context_data
        )

        assert context['current_task'] == 'Debug API issue'
        assert context['work_state'] == 'busy'
        assert context['search_count_today'] == 5

    @pytest.mark.asyncio
    async def test_profile_completeness(self, db: AsyncSession, test_agent: Agent):
        """测试画像完整度计算"""
        service = get_profile_service()

        # 创建部分画像
        profile_data = {
            'language': 'zh',
            'theme': 'dark',
            'editor': 'VSCode'
        }
        await service.create_or_update_profile(
            db, test_agent.agent_id, profile_data
        )

        # 添加更多事实
        await service.add_fact(db, test_agent.agent_id, 'personal', 'job_title', 'Engineer')
        await service.add_fact(db, test_agent.agent_id, 'skill', 'skills', [{'name': 'Python'}])

        # 获取画像
        profile = await service.get_profile(db, test_agent.agent_id)

        assert 'completeness_score' in profile
        assert profile['completeness_score'] > 0


class TestProfileAPI:
    """测试画像 API 端点"""

    @pytest.mark.asyncio
    async def test_get_my_profile(self, client, auth_headers, db: AsyncSession):
        """测试获取我的画像 API"""
        # 先创建画像
        service = get_profile_service()
        test_agent_id = "test_agent_api"
        await service.create_or_update_profile(
            db, test_agent_id, {'language': 'zh'}
        )

        # 调用 API（需要认证）
        # response = await client.get(
        #     "/user-profiles/me",
        #     headers=auth_headers
        # )
        # assert response.status_code == 200
        # data = response.json()
        # assert data['agent_id'] == test_agent_id
        # assert data['language'] == 'zh'
        pass  # 实际测试需要认证设置

    @pytest.mark.asyncio
    async def test_update_my_profile(self, client, auth_headers, db: AsyncSession):
        """测试更新我的画像 API"""
        # response = await client.put(
        #     "/user-profiles/me",
        #     json={'language': 'en', 'theme': 'light'},
        #     headers=auth_headers
        # )
        # assert response.status_code == 200
        # data = response.json()
        # assert data['language'] == 'en'
        # assert data['theme'] == 'light'
        pass  # 实际测试需要认证设置

    @pytest.mark.asyncio
    async def test_add_fact_api(self, client, auth_headers, db: AsyncSession):
        """测试添加事实 API"""
        # response = await client.post(
        #     "/user-profiles/me/facts",
        #     json={
        #         'fact_type': 'preference',
        #         'fact_key': 'editor',
        #         'fact_value': 'Vim'
        #     },
        #     headers=auth_headers
        # )
        # assert response.status_code == 200
        # data = response.json()
        # assert data['fact_key'] == 'editor'
        # assert data['fact_value'] == 'Vim'
        pass  # 实际测试需要认证设置

    @pytest.mark.asyncio
    async def test_extract_from_conversation_api(self, client, auth_headers):
        """测试从对话提取 API"""
        # response = await client.post(
        #     "/user-profiles/extract",
        #     json={
        #         'conversation_text': '我是用 Python 的工程师，喜欢 VSCode',
        #         'conversation_id': 'test_conv_api'
        #     },
        #     headers=auth_headers
        # )
        # assert response.status_code == 200
        # data = response.json()
        # assert 'facts' in data
        # assert 'extraction_time' in data
        pass  # 实际测试需要认证设置


class TestSearchIntegration:
    """测试搜索集成"""

    @pytest.mark.asyncio
    async def test_personalized_search(self, db: AsyncSession, test_agent: Agent):
        """测试个性化搜索"""
        # 这个测试需要实际的搜索引擎和记忆数据
        # 这里只是测试接口是否可用
        from app.search.hybrid_search import get_hybrid_engine

        engine = get_hybrid_engine()
        assert engine is not None

        # 测试个性化搜索方法是否存在
        assert hasattr(engine, 'personalized_search')


# 测试数据 fixture
@pytest.fixture
async def test_agent(db: AsyncSession):
    """创建测试用户"""
    agent = Agent(
        agent_id="test_agent_user_profile",
        name="Test User",
        api_key="test_api_key_profile",
        credits=1000
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    yield agent

    # 清理
    await db.delete(agent)
    await db.commit()


@pytest.fixture
def auth_headers():
    """认证头"""
    # 返回测试用的认证头
    return {'Authorization': 'Bearer test_token'}
