"""用户信息观察者Agent - 提取个人信息和偏好维度

从原始数据中提取：
- 维度1：个人信息（姓名、职位、公司等）
- 维度2：偏好（语言、工具、主题等）
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List

from app.services.agent_base import BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus

logger = logging.getLogger(__name__)

# 常见个人信息模式
_NAME_PATTERNS = [
    r"(?:我叫|我是|名字是|name[:\s]+)([\u4e00-\u9fff\w]+)",
    r"(?:^|\n)(?:姓名|Name)[:\s：]+([\u4e00-\u9fff\w]+)",
]
_TITLE_PATTERNS = [
    r"(?:职位|职务|title|role)[:\s：]+([^\n,，。]+)",
    r"(?:我是|担任)([\u4e00-\u9fff]+(?:工程师|经理|总监|主管|设计师|开发者|架构师|分析师|顾问))",
]
_COMPANY_PATTERNS = [
    r"(?:公司|company|组织|organization)[:\s：]+([^\n,，。]+)",
    r"(?:在|at)\s+([\w\u4e00-\u9fff]+(?:公司|科技|集团|工作室|团队))",
]
_SKILL_PATTERNS = [
    r"(?:技能|skills?|擅长|精通)[:\s：]+([^\n]+)",
    r"(?:使用|use|用)\s+([\w,，、\s/+]+?)(?:开发|编程|构建|实现)",
]
_TOOL_PATTERNS = [
    r"(?:工具|tools?|IDE|编辑器|editor)[:\s：]+([^\n]+)",
]
_LANGUAGE_PATTERNS = [
    r"(?:语言|language|编程语言|programming language)[:\s：]+([^\n]+)",
]
_TOPIC_PATTERNS = [
    r"(?:兴趣|interests?|关注|爱好|hobby)[:\s：]+([^\n]+)",
]


def _extract_first(text: str, patterns: List[str]) -> str:
    """从文本中提取第一个匹配"""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_list(text: str, patterns: List[str]) -> List[str]:
    """从文本中提取列表"""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            items = re.split(r"[,，、/|;；\s]+", raw)
            return [i.strip() for i in items if i.strip()]
    return []


class UserInfoAgent(BaseAgent):
    """用户信息观察者Agent

    职责：从原始数据中提取个人信息和偏好
    对应Supermemory ASMR的维度1（个人信息）和维度2（偏好）
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("role", AgentRole.OBSERVER_USER_INFO)
        super().__init__(**kwargs)

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行用户信息提取"""
        text_sources = self._collect_text(context)

        user_info = self._extract_user_info(text_sources)
        preferences = self._extract_preferences(text_sources)

        # 更新context维度
        context.set_dimension("user_info", user_info)
        context.set_dimension("preferences", preferences)

        confidence = self._calc_confidence(user_info, preferences)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "user_info": user_info,
                "preferences": preferences,
            },
            confidence=confidence,
        )

    def _collect_text(self, context: AgentContext) -> str:
        """收集所有可用文本"""
        parts = [context.query]

        # 从raw_data中收集
        for key in ("text", "content", "description", "profile", "bio", "about"):
            val = context.raw_data.get(key)
            if val and isinstance(val, str):
                parts.append(val)

        # 从observations中收集
        for key, val in context.observations.items():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict):
                for sub_key in ("text", "content", "description"):
                    sub_val = val.get(sub_key)
                    if sub_val and isinstance(sub_val, str):
                        parts.append(sub_val)

        return "\n".join(parts)

    def _extract_user_info(self, text: str) -> Dict[str, Any]:
        """提取个人信息"""
        info: Dict[str, Any] = {}

        name = _extract_first(text, _NAME_PATTERNS)
        if name:
            info["name"] = name

        title = _extract_first(text, _TITLE_PATTERNS)
        if title:
            info["title"] = title

        company = _extract_first(text, _COMPANY_PATTERNS)
        if company:
            info["company"] = company

        skills = _extract_list(text, _SKILL_PATTERNS)
        if skills:
            info["skills"] = skills

        return info

    def _extract_preferences(self, text: str) -> Dict[str, Any]:
        """提取偏好"""
        prefs: Dict[str, Any] = {}

        tools = _extract_list(text, _TOOL_PATTERNS)
        if tools:
            prefs["tools"] = tools

        languages = _extract_list(text, _LANGUAGE_PATTERNS)
        if languages:
            prefs["programming_languages"] = languages

        topics = _extract_list(text, _TOPIC_PATTERNS)
        if topics:
            prefs["topics"] = topics

        return prefs

    def _calc_confidence(self, user_info: Dict, preferences: Dict) -> float:
        """计算提取置信度"""
        score = 0.0
        if user_info.get("name"):
            score += 0.3
        if user_info.get("title"):
            score += 0.2
        if user_info.get("company"):
            score += 0.15
        if user_info.get("skills"):
            score += 0.1
        if preferences:
            score += 0.1 * min(len(preferences), 3)
        return min(score, 1.0)
