"""时序观察者Agent - 提取时序数据和事件维度

从原始数据中提取：
- 维度3：事件（会议、项目等）
- 维度4：时序数据（历史记录）
- 维度5：信息更新（变更）
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.agent_base import BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus

logger = logging.getLogger(__name__)

# 日期模式
_DATE_PATTERNS = [
    r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)",
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
    r"((?:今天|昨天|前天|上周|本周|下周|上个月|这个月|下个月))",
    r"(\d+\s*(?:天|周|月|年)(?:前|以前|之前))",
]

# 事件模式
_EVENT_PATTERNS = [
    r"(?:会议|meeting|讨论|review)[:\s：]+([^\n。.]+)",
    r"(?:项目|project|任务|task|需求|requirement)[:\s：]+([^\n。.]+)",
    r"(?:发布|launch|上线|deploy|部署|release)[:\s：]+([^\n。.]+)",
    r"(?:修复|fix|解决|resolve|修了?)[:\s：]*([^\n。.]+)",
    r"(?:完成|finished?|completed?|done)[:\s：]*([^\n。.]+)",
]

# 更新模式
_UPDATE_PATTERNS = [
    r"(?:更新|update|变更|change|修改|modify)[:\s：]+([^\n。.]+)",
    r"(?:从|from)\s+(.+?)\s*(?:改为|改到|变成|to)\s+(.+?)(?:[,，。\n]|$)",
    r"(?:之前|原来|before)[:\s]*(.+?)[,，]\s*(?:现在|后来|after|改为)[:\s]*(.+?)(?:[,，。\n]|$)",
]


class TemporalAgent(BaseAgent):
    """时序观察者Agent

    职责：从原始数据中提取事件、时序数据和变更信息
    对应Supermemory ASMR的维度3（事件）、维度4（时序）、维度5（更新）
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("role", AgentRole.OBSERVER_TEMPORAL)
        super().__init__(**kwargs)

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行时序数据提取"""
        text_sources = self._collect_text(context)

        events = self._extract_events(text_sources)
        temporal_data = self._extract_temporal(text_sources)
        updates = self._extract_updates(text_sources)

        # 更新context维度
        context.set_dimension("events", {"items": events})
        context.set_dimension("temporal", temporal_data)
        context.set_dimension("updates", {"items": updates})

        confidence = self._calc_confidence(events, temporal_data, updates)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "events": events,
                "temporal": temporal_data,
                "updates": updates,
            },
            confidence=confidence,
        )

    def _collect_text(self, context: AgentContext) -> str:
        """收集所有可用文本"""
        parts = [context.query]
        for key in ("text", "content", "log", "history", "timeline", "changelog"):
            val = context.raw_data.get(key)
            if val and isinstance(val, str):
                parts.append(val)
            elif val and isinstance(val, list):
                parts.extend(str(v) for v in val)
        return "\n".join(parts)

    def _extract_events(self, text: str) -> List[Dict[str, Any]]:
        """提取事件"""
        events = []
        for pat in _EVENT_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                desc = m.group(1).strip()
                if len(desc) > 2:
                    # 尝试提取日期
                    date_str = self._find_nearby_date(text, m.start())
                    events.append({
                        "description": desc,
                        "date": date_str,
                        "type": self._classify_event(m.group(0)),
                    })
        return events

    def _extract_temporal(self, text: str) -> Dict[str, Any]:
        """提取时序数据"""
        temporal: Dict[str, Any] = {
            "dates_mentioned": [],
            "relative_times": [],
            "timeline_entries": [],
        }

        # 提取绝对日期
        for pat in _DATE_PATTERNS[:2]:
            for m in re.finditer(pat, text):
                date_str = m.group(1)
                temporal["dates_mentioned"].append(date_str)
                # 提取日期附近的上下文
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 100)
                context_text = text[start:end].strip()
                temporal["timeline_entries"].append({
                    "date": date_str,
                    "context": context_text,
                })

        # 提取相对时间
        for pat in _DATE_PATTERNS[2:]:
            for m in re.finditer(pat, text):
                temporal["relative_times"].append(m.group(1))

        return temporal

    def _extract_updates(self, text: str) -> List[Dict[str, Any]]:
        """提取更新/变更"""
        updates = []
        for pat in _UPDATE_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                groups = m.groups()
                if len(groups) >= 2:
                    updates.append({
                        "before": groups[0].strip(),
                        "after": groups[1].strip(),
                        "type": "change",
                    })
                elif len(groups) == 1:
                    updates.append({
                        "description": groups[0].strip(),
                        "type": "update",
                    })
        return updates

    def _find_nearby_date(self, text: str, pos: int, window: int = 100) -> Optional[str]:
        """在位置附近查找日期"""
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        nearby = text[start:end]
        for pat in _DATE_PATTERNS[:2]:
            m = re.search(pat, nearby)
            if m:
                return m.group(1)
        return None

    def _classify_event(self, text: str) -> str:
        """分类事件类型"""
        text_lower = text.lower()
        if any(w in text_lower for w in ("会议", "meeting", "讨论", "review")):
            return "meeting"
        if any(w in text_lower for w in ("项目", "project", "任务", "task")):
            return "project"
        if any(w in text_lower for w in ("发布", "launch", "上线", "deploy")):
            return "release"
        if any(w in text_lower for w in ("修复", "fix", "解决")):
            return "bugfix"
        if any(w in text_lower for w in ("完成", "finished", "completed")):
            return "completion"
        return "general"

    def _calc_confidence(
        self, events: List, temporal: Dict, updates: List
    ) -> float:
        """计算置信度"""
        score = 0.0
        score += min(len(events) * 0.15, 0.45)
        if temporal.get("dates_mentioned"):
            score += 0.2
        if temporal.get("timeline_entries"):
            score += 0.15
        score += min(len(updates) * 0.1, 0.2)
        return min(score, 1.0)
