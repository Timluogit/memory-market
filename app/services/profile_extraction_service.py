"""用户画像提取服务

从对话中自动提取用户画像信息（静态事实）
"""
from typing import Dict, List, Any, Optional, Tuple
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.tables import UserProfile, ProfileFact, ProfileChange
from app.core.config import settings

logger = logging.getLogger(__name__)


class ProfileExtractionService:
    """用户画像提取服务

    使用 LLM 从对话中自动提取用户画像信息
    """

    # 支持的画像字段类型
    FIELD_TYPES = {
        'personal': ['real_name', 'job_title', 'company', 'location', 'timezone'],
        'preference': ['language', 'editor', 'theme', 'ui_scale'],
        'habit': ['work_hours', 'work_days', 'preferred_command'],
        'skill': ['skills', 'tech_stack'],
        'interest': ['interests', 'research_areas']
    }

    def __init__(self):
        """初始化画像提取服务"""
        self.min_confidence = settings.PROFILE_MIN_CONFIDENCE
        self.extraction_model = settings.PROFILE_EXTRACTION_MODEL
        self.auto_forget_days = settings.PROFILE_AUTO_FORGET_DAYS

    async def extract_from_conversation(
        self,
        db: AsyncSession,
        agent_id: str,
        conversation_text: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """从对话中提取画像信息

        Args:
            db: 数据库会话
            agent_id: 用户ID
            conversation_text: 对话文本
            conversation_id: 对话ID（用于追溯来源）

        Returns:
            提取结果: {"facts": [...], "confidence": float, "extraction_time": datetime}
        """
        if not settings.PROFILE_ENABLED or not settings.PROFILE_AUTO_EXTRACTION:
            logger.info(f"Profile extraction disabled for agent {agent_id}")
            return {"facts": [], "confidence": 0.0, "extraction_time": datetime.now()}

        try:
            # 1. 使用 LLM 提取画像信息
            extracted_facts = await self._llm_extract(conversation_text)

            # 2. 过滤低置信度的事实
            high_confidence_facts = [
                fact for fact in extracted_facts
                if fact.get('confidence', 0) >= self.min_confidence
            ]

            # 3. 获取现有画像
            existing_profile = await self._get_profile(db, agent_id)

            # 4. 比较并识别新事实
            new_facts = await self._compare_with_existing(
                db,
                agent_id,
                existing_profile,
                high_confidence_facts,
                conversation_id
            )

            # 5. 更新画像
            if new_facts:
                await self._update_profile(db, agent_id, new_facts, existing_profile)

            logger.info(
                f"Extracted {len(new_facts)} new profile facts for agent {agent_id} "
                f"from conversation {conversation_id}"
            )

            return {
                "facts": new_facts,
                "total_extracted": len(high_confidence_facts),
                "confidence": sum(f.get('confidence', 0) for f in high_confidence_facts) / len(high_confidence_facts) if high_confidence_facts else 0.0,
                "extraction_time": datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to extract profile from conversation: {e}", exc_info=True)
            return {
                "facts": [],
                "confidence": 0.0,
                "extraction_time": datetime.now(),
                "error": str(e)
            }

    async def _llm_extract(self, conversation_text: str) -> List[Dict[str, Any]]:
        """使用 LLM 提取画像信息

        Args:
            conversation_text: 对话文本

        Returns:
            提取的事实列表
        """
        # 构建 LLM 提示词
        prompt = self._build_extraction_prompt(conversation_text)

        # 调用 LLM（这里使用模拟实现，实际应该调用真实的 LLM API）
        try:
            # TODO: 集成真实的 LLM API（如 OpenAI、Anthropic 等）
            # 这里使用规则提取作为示例
            return await self._rule_based_extract(conversation_text)
        except Exception as e:
            logger.warning(f"LLM extraction failed, fallback to rule-based: {e}")
            return await self._rule_based_extract(conversation_text)

    def _build_extraction_prompt(self, conversation_text: str) -> str:
        """构建 LLM 提取提示词

        Args:
            conversation_text: 对话文本

        Returns:
            提示词
        """
        prompt = f"""从以下对话中提取用户画像信息。只提取明确提到的信息，不要猜测。

对话内容:
{conversation_text}

需要提取的信息类别:
1. 个人信息: 姓名、职位、公司、地点、时区
2. 偏好: 语言、编辑器（VSCode/Vim/Emacs）、主题（light/dark）
3. 习惯: 工作时间、工作日、常用命令
4. 技能: 编程语言、框架、技术栈
5. 兴趣: 兴趣领域、研究方向

返回格式（JSON数组）:
[
  {{
    "field": "字段名（如：language、editor、skills）",
    "value": "字段值（字符串或数组）",
    "confidence": 置信度（0-1）,
    "type": "类型（personal/preference/habit/skill/interest）"
  }}
]

只返回提取到的信息，如果没有匹配的信息，返回空数组。"""
        return prompt

    async def _rule_based_extract(self, conversation_text: str) -> List[Dict[str, Any]]:
        """基于规则提取画像信息（作为 LLM 的后备方案）

        Args:
            conversation_text: 对话文本

        Returns:
            提取的事实列表
        """
        facts = []
        text_lower = conversation_text.lower()

        # 提取语言偏好
        if 'english' in text_lower or '英语' in text_text:
            facts.append({
                'field': 'language',
                'value': 'en',
                'confidence': 0.7,
                'type': 'preference'
            })

        # 提取编辑器偏好
        if 'vim' in text_lower:
            facts.append({
                'field': 'editor',
                'value': 'Vim',
                'confidence': 0.8,
                'type': 'preference'
            })
        elif 'vscode' in text_lower or 'vs code' in text_lower:
            facts.append({
                'field': 'editor',
                'value': 'VSCode',
                'confidence': 0.8,
                'type': 'preference'
            })
        elif 'emacs' in text_lower:
            facts.append({
                'field': 'editor',
                'value': 'Emacs',
                'confidence': 0.8,
                'type': 'preference'
            })

        # 提取主题偏好
        if 'dark' in text_lower and ('theme' in text_lower or '主题' in conversation_text):
            facts.append({
                'field': 'theme',
                'value': 'dark',
                'confidence': 0.7,
                'type': 'preference'
            })
        elif 'light' in text_lower and ('theme' in text_lower or '主题' in conversation_text):
            facts.append({
                'field': 'theme',
                'value': 'light',
                'confidence': 0.7,
                'type': 'preference'
            })

        # 提取技能（编程语言和框架）
        programming_languages = ['python', 'javascript', 'java', 'go', 'rust', 'typescript', 'c++', 'ruby', 'php']
        frameworks = ['fastapi', 'django', 'flask', 'react', 'vue', 'angular', 'spring', 'express']

        found_skills = []
        for lang in programming_languages:
            if lang in text_lower:
                found_skills.append({'name': lang.capitalize(), 'level': 'intermediate'})

        for fw in frameworks:
            if fw in text_lower:
                found_skills.append({'name': fw.capitalize(), 'level': 'intermediate'})

        if found_skills:
            facts.append({
                'field': 'skills',
                'value': found_skills,
                'confidence': 0.6,
                'type': 'skill'
            })

        # 提取工作时间
        import re
        time_pattern = r'(\d{1,2}):(\d{2})\s*(?:am|pm)?(?:到|-|至)\s*(\d{1,2}):(\d{2})\s*(?:am|pm)?'
        time_match = re.search(time_pattern, conversation_text, re.IGNORECASE)
        if time_match:
            start_hour = time_match.group(1)
            start_min = time_match.group(2)
            end_hour = time_match.group(3)
            end_min = time_match.group(4)
            facts.append({
                'field': 'work_hours',
                'value': {
                    'start': f"{start_hour}:{start_min}",
                    'end': f"{end_hour}:{end_min}"
                },
                'confidence': 0.7,
                'type': 'habit'
            })

        logger.info(f"Rule-based extraction found {len(facts)} facts")
        return facts

    async def _get_profile(
        self,
        db: AsyncSession,
        agent_id: str
    ) -> Optional[UserProfile]:
        """获取用户画像

        Args:
            db: 数据库会话
            agent_id: 用户ID

        Returns:
            用户画像对象或 None
        """
        result = await db.execute(
            select(UserProfile).where(UserProfile.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    async def _compare_with_existing(
        self,
        db: AsyncSession,
        agent_id: str,
        existing_profile: Optional[UserProfile],
        new_facts: List[Dict[str, Any]],
        conversation_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """比较新提取的事实与现有事实

        Args:
            db: 数据库会话
            agent_id: 用户ID
            existing_profile: 现有画像对象
            new_facts: 新提取的事实列表
            conversation_id: 对话ID

        Returns:
            真实的新事实列表
        """
        truly_new_facts = []

        for fact in new_facts:
            field_name = fact['field']
            new_value = fact['value']

            # 检查是否已存在相同字段的事实
            existing_facts = await db.execute(
                select(ProfileFact).where(
                    and_(
                        ProfileFact.agent_id == agent_id,
                        ProfileFact.fact_key == field_name,
                        ProfileFact.is_valid == True
                    )
                )
            )
            existing_fact = existing_facts.scalar_one_or_none()

            if existing_fact:
                # 比较值是否变化
                if existing_fact.fact_value != new_value:
                    # 值变化，记录变更
                    truly_new_facts.append({
                        **fact,
                        'is_update': True,
                        'old_value': existing_fact.fact_value
                    })
            else:
                # 新事实
                truly_new_facts.append({
                    **fact,
                    'is_update': False
                })

        return truly_new_facts

    async def _update_profile(
        self,
        db: AsyncSession,
        agent_id: str,
        new_facts: List[Dict[str, Any]],
        existing_profile: Optional[UserProfile]
    ):
        """更新用户画像

        Args:
            db: 数据库会话
            agent_id: 用户ID
            new_facts: 新事实列表
            existing_profile: 现有画像对象
        """
        from datetime import datetime

        # 创建或获取画像
        if not existing_profile:
            profile = UserProfile(agent_id=agent_id)
            db.add(profile)
            await db.flush()  # 获取 profile_id
            profile_id = profile.profile_id
        else:
            profile_id = existing_profile.profile_id

        # 添加新事实
        for fact in new_facts:
            # 创建新事实记录
            new_fact = ProfileFact(
                profile_id=profile_id,
                agent_id=agent_id,
                fact_type=fact['type'],
                fact_key=fact['field'],
                fact_value=fact['value'],
                confidence=fact.get('confidence', 0.8),
                source='auto_extraction',
                source_reference=fact.get('source_reference', ''),
                expires_at=datetime.now() + timedelta(days=self.auto_forget_days),
                is_valid=True
            )
            db.add(new_fact)

            # 如果是更新，标记旧事实为无效
            if fact.get('is_update'):
                await db.execute(
                    select(ProfileFact).where(
                        and_(
                            ProfileFact.agent_id == agent_id,
                            ProfileFact.fact_key == fact['field'],
                            ProfileFact.is_valid == True
                        )
                    )
                )
                old_facts = await db.execute(
                    select(ProfileFact).where(
                        and_(
                            ProfileFact.agent_id == agent_id,
                            ProfileFact.fact_key == fact['field'],
                            ProfileFact.is_valid == True
                        )
                    )
                )
                for old_fact in old_facts.scalars().all():
                    old_fact.is_valid = False

            # 记录变更历史
            change = ProfileChange(
                profile_id=profile_id,
                agent_id=agent_id,
                change_type='updated' if fact.get('is_update') else 'created',
                field_name=fact['field'],
                old_value=fact.get('old_value'),
                new_value=fact['value'],
                source='auto_extraction',
                source_reference=fact.get('source_reference', '')
            )
            db.add(change)

        # 更新画像主表字段
        if existing_profile:
            existing_profile.last_updated_at = datetime.now()

        await db.commit()

    async def auto_forget_expired_facts(self, db: AsyncSession):
        """自动遗忘过期的事实

        Args:
            db: 数据库会话
        """
        now = datetime.now()

        # 查找过期的事实
        expired_facts = await db.execute(
            select(ProfileFact).where(
                and_(
                    ProfileFact.is_valid == True,
                    ProfileFact.expires_at <= now
                )
            )
        )

        for fact in expired_facts.scalars().all():
            # 标记为无效
            fact.is_valid = False

            # 记录变更
            change = ProfileChange(
                profile_id=fact.profile_id,
                agent_id=fact.agent_id,
                change_type='expired',
                field_name=fact.fact_key,
                old_value=fact.fact_value,
                new_value=None,
                source='auto_forget',
                change_reason=f'Fact expired at {fact.expires_at}'
            )
            db.add(change)

        await db.commit()
        logger.info(f"Auto-forget: marked {len(expired_facts.scalars().all())} facts as expired")


# 全局单例
_extraction_service: Optional[ProfileExtractionService] = None


def get_extraction_service() -> ProfileExtractionService:
    """获取画像提取服务单例

    Returns:
        画像提取服务实例
    """
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ProfileExtractionService()
    return _extraction_service
