"""时间线搜索Agent - 重建时间线和关系图谱

基于时序维度数据，搜索具有时间关联的记忆，重建时间线
对应Supermemory ASMR Agent 3：重建时间线和关系图谱
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_base import BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus
from app.models.tables import Memory, Agent, MemoryVersion

logger = logging.getLogger(__name__)


class TimelineAgent(BaseAgent):
    """时间线搜索Agent

    职责：基于时序维度数据搜索记忆，重建时间线和关系图谱
    策略：时间范围搜索 + 版本历史 + 关联记忆发现
    """

    def __init__(self, db: Optional[AsyncSession] = None, **kwargs):
        kwargs.setdefault("role", AgentRole.SEARCHER_TIMELINE)
        super().__init__(**kwargs)
        self.db = db

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行时间线搜索"""
        temporal_data = context.get_dimension("temporal")
        events_data = context.get_dimension("events")

        results = []
        timeline = []

        if self.db:
            results, timeline = await self._search_db(context, temporal_data, events_data)
        else:
            results, timeline = self._search_from_context(context, temporal_data, events_data)

        # 构建关系图谱
        relationships = self._build_relationships(results, context)

        confidence = self._calc_confidence(results, timeline)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "results": results,
                "timeline": timeline,
                "relationships": relationships,
                "strategy": "timeline",
                "result_count": len(results),
            },
            confidence=confidence,
        )

    async def _search_db(
        self,
        context: AgentContext,
        temporal_data: Dict,
        events_data: Dict,
    ) -> tuple:
        """数据库时间线搜索"""
        try:
            # 1. 解析时间范围
            time_ranges = self._parse_time_ranges(temporal_data)

            # 2. 搜索时间范围内的记忆
            memories = []
            timeline_entries = []

            if time_ranges:
                for start, end, label in time_ranges:
                    stmt = (
                        select(Memory, Agent.name)
                        .join(Agent, Memory.seller_agent_id == Agent.agent_id)
                        .where(
                            and_(
                                Memory.is_active == True,
                                Memory.created_at >= start,
                                Memory.created_at <= end,
                            )
                        )
                        .order_by(Memory.created_at.desc())
                        .limit(10)
                    )

                    result = await self.db.execute(stmt)
                    rows = result.all()

                    for memory, seller_name in rows:
                        memories.append({
                            "memory_id": memory.memory_id,
                            "title": memory.title,
                            "summary": memory.summary,
                            "category": memory.category,
                            "created_at": memory.created_at.isoformat() if memory.created_at else None,
                            "seller_name": seller_name,
                            "time_context": label,
                        })

                    timeline_entries.append({
                        "period": label,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "memory_count": len(rows),
                    })

            # 3. 搜索版本历史
            if memories:
                memory_ids = [m["memory_id"] for m in memories[:5]]
                version_stmt = (
                    select(MemoryVersion)
                    .where(MemoryVersion.memory_id.in_(memory_ids))
                    .order_by(MemoryVersion.created_at.desc())
                    .limit(10)
                )
                ver_result = await self.db.execute(version_stmt)
                versions = ver_result.scalars().all()

                for ver in versions:
                    timeline_entries.append({
                        "type": "version",
                        "memory_id": ver.memory_id,
                        "version": ver.version_number,
                        "date": ver.created_at.isoformat() if ver.created_at else None,
                        "changelog": ver.changelog,
                    })

            return memories, timeline_entries

        except Exception as e:
            logger.error(f"TimelineAgent DB search error: {e}")
            return [], []

    def _search_from_context(
        self,
        context: AgentContext,
        temporal_data: Dict,
        events_data: Dict,
    ) -> tuple:
        """从上下文中搜索"""
        results = []
        timeline = []

        # 基于events数据构建时间线
        events = events_data.get("items", [])
        for event in events:
            timeline.append({
                "type": "event",
                "description": event.get("description", ""),
                "date": event.get("date"),
                "event_type": event.get("type", "general"),
            })

        # 基于temporal数据补充
        for entry in temporal_data.get("timeline_entries", []):
            timeline.append({
                "type": "temporal",
                "date": entry.get("date"),
                "context": entry.get("context", ""),
            })

        # 搜索observations中有时间标记的数据
        for key, val in context.observations.items():
            if isinstance(val, dict):
                date_fields = ("created_at", "updated_at", "date", "timestamp")
                has_date = any(f in val for f in date_fields)
                if has_date:
                    results.append({
                        "source": key,
                        "data": val,
                        "has_timeline": True,
                    })

        # 按日期排序时间线
        timeline.sort(key=lambda x: x.get("date", ""), reverse=False)

        return results, timeline

    def _parse_time_ranges(self, temporal_data: Dict) -> List[tuple]:
        """解析时间范围"""
        ranges = []
        now = datetime.now()

        # 从相对时间解析
        for rel in temporal_data.get("relative_times", []):
            rel_lower = rel.lower()
            if "天前" in rel_lower or "天以前" in rel_lower:
                import re
                m = re.search(r"(\d+)\s*天", rel_lower)
                if m:
                    days = int(m.group(1))
                    start = now - timedelta(days=days + 1)
                    end = now - timedelta(days=days - 1)
                    ranges.append((start, end, rel))
            elif "周前" in rel_lower or "周以前" in rel_lower:
                import re
                m = re.search(r"(\d+)\s*周", rel_lower)
                if m:
                    weeks = int(m.group(1))
                    start = now - timedelta(weeks=weeks + 1)
                    end = now - timedelta(weeks=weeks - 1)
                    ranges.append((start, end, rel))
            elif "月前" in rel_lower or "月以前" in rel_lower:
                import re
                m = re.search(r"(\d+)\s*月", rel_lower)
                if m:
                    months = int(m.group(1))
                    start = now - timedelta(days=months * 30 + 7)
                    end = now - timedelta(days=months * 30 - 7)
                    ranges.append((start, end, rel))

        # 默认搜索最近30天
        if not ranges:
            ranges.append((now - timedelta(days=30), now, "最近30天"))

        return ranges

    def _build_relationships(
        self, results: List[Dict], context: AgentContext
    ) -> List[Dict[str, Any]]:
        """构建关系图谱"""
        relationships = []

        # 基于分类的关系
        categories = set()
        for r in results:
            cat = r.get("category")
            if cat:
                categories.add(cat)

        # 基于共同标签的关系
        tag_map: Dict[str, List[str]] = {}
        for r in results:
            for tag in r.get("tags", []):
                tag_lower = tag.lower()
                if tag_lower not in tag_map:
                    tag_map[tag_lower] = []
                tag_map[tag_lower].append(r.get("memory_id", r.get("source", "")))

        # 找出共享标签的记忆对
        for tag, memory_ids in tag_map.items():
            if len(memory_ids) > 1:
                for i in range(len(memory_ids)):
                    for j in range(i + 1, len(memory_ids)):
                        relationships.append({
                            "type": "shared_tag",
                            "tag": tag,
                            "source": memory_ids[i],
                            "target": memory_ids[j],
                        })

        return relationships[:20]  # 限制关系数量

    def _calc_confidence(self, results: List, timeline: List) -> float:
        """计算置信度"""
        score = 0.0
        if results:
            score += 0.4
        if timeline:
            score += 0.3
            # 时间线越丰富，置信度越高
            score += min(len(timeline) * 0.05, 0.3)
        return min(score, 1.0)
