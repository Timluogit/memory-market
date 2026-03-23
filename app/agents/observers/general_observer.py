"""通用观察者Agent - 提取助手信息维度

从原始数据中提取：
- 维度6：助手信息（交互模式、使用习惯）
- 也负责通用数据清洗和预处理
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List

from app.services.agent_base import BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus

logger = logging.getLogger(__name__)

# 交互模式模式
_INTERACTION_PATTERNS = [
    r"(?:喜欢|偏好|习惯|prefer|习惯于?)[:\s：]+([^\n。.]+)",
    r"(?:风格|style|语气|tone)[:\s：]+([^\n。.]+)",
    r"(?:工作流|workflow|流程|process)[:\s：]+([^\n。.]+)",
]

# 使用习惯
_USAGE_PATTERNS = [
    r"(?:经常|常用|frequently|often|always)[:\s：]*([^\n。.]+)",
    r"(?:每次|every time|每次都会?)[:\s：]*([^\n。.]+)",
]


class GeneralObserver(BaseAgent):
    """通用观察者Agent

    职责：提取助手交互信息、数据清洗和预处理
    对应Supermemory ASMR的维度6（助手信息）
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("role", AgentRole.OBSERVER_GENERAL)
        super().__init__(**kwargs)

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行通用观察"""
        text_sources = self._collect_text(context)

        assistant_info = self._extract_assistant_info(text_sources)
        data_quality = self._assess_data_quality(context)

        # 更新context维度
        context.set_dimension("assistant", assistant_info)
        context.metadata["data_quality"] = data_quality

        # 汇总已有维度的置信度
        dimension_summary = self._summarize_dimensions(context)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "assistant_info": assistant_info,
                "data_quality": data_quality,
                "dimension_summary": dimension_summary,
            },
            confidence=data_quality.get("overall_score", 0.5),
        )

    def _collect_text(self, context: AgentContext) -> str:
        """收集所有文本"""
        parts = [context.query]
        for key, val in context.raw_data.items():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict):
                for sub in val.values():
                    if isinstance(sub, str):
                        parts.append(sub)
        return "\n".join(parts)

    def _extract_assistant_info(self, text: str) -> Dict[str, Any]:
        """提取助手交互信息"""
        info: Dict[str, Any] = {
            "interaction_patterns": [],
            "usage_habits": [],
            "format_preferences": [],
        }

        # 提取交互模式
        for pat in _INTERACTION_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                val = m.group(1).strip()
                if len(val) > 2:
                    info["interaction_patterns"].append(val)

        # 提取使用习惯
        for pat in _USAGE_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                val = m.group(1).strip()
                if len(val) > 2:
                    info["usage_habits"].append(val)

        # 检测格式偏好
        if re.search(r"(?:代码|code|编程|编程语言)", text, re.IGNORECASE):
            info["format_preferences"].append("code_oriented")
        if re.search(r"(?:表格|table|结构化|structured)", text, re.IGNORECASE):
            info["format_preferences"].append("structured")
        if re.search(r"(?:简洁|concise|简短|brief|短)", text, re.IGNORECASE):
            info["format_preferences"].append("concise")
        if re.search(r"(?:详细|detail|深入|in-depth|深入)", text, re.IGNORECASE):
            info["format_preferences"].append("detailed")

        return info

    def _assess_data_quality(self, context: AgentContext) -> Dict[str, Any]:
        """评估数据质量"""
        text = context.query
        text_len = len(text)

        quality: Dict[str, Any] = {
            "text_length": text_len,
            "has_raw_data": bool(context.raw_data),
            "raw_data_keys": list(context.raw_data.keys()),
            "has_observations": bool(context.observations),
        }

        # 计算整体质量分数
        score = 0.0
        if text_len > 10:
            score += 0.2
        if text_len > 100:
            score += 0.2
        if context.raw_data:
            score += 0.3
        if context.observations:
            score += 0.15
        if context.user_id:
            score += 0.15

        quality["overall_score"] = min(score, 1.0)
        return quality

    def _summarize_dimensions(self, context: AgentContext) -> Dict[str, Any]:
        """汇总各维度的提取情况"""
        summary = {}
        for dim_name in ("user_info", "preferences", "events", "temporal", "updates", "assistant"):
            data = context.get_dimension(dim_name)
            has_data = bool(data)
            item_count = 0
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        item_count += len(v)
                    elif v:
                        item_count += 1
            summary[dim_name] = {
                "has_data": has_data,
                "item_count": item_count,
            }
        return summary
