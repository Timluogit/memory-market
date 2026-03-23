"""上下文搜索Agent - 寻找相关上下文

通过语义搜索和分类匹配寻找与查询相关的上下文记忆
对应Supermemory ASMR Agent 2：寻找相关上下文
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_base import BaseAgent, AgentRole, AgentContext, AgentResult, AgentStatus
from app.models.tables import Memory, Agent, Purchase

logger = logging.getLogger(__name__)


class ContextAgent(BaseAgent):
    """上下文搜索Agent

    职责：寻找与查询相关的上下文记忆
    策略：分类匹配 + 相关标签 + 用户购买历史 + 语义相似
    """

    def __init__(self, db: Optional[AsyncSession] = None, **kwargs):
        kwargs.setdefault("role", AgentRole.SEARCHER_CONTEXT)
        super().__init__(**kwargs)
        self.db = db

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行上下文搜索"""
        query = context.query
        results = []

        if self.db:
            results = await self._search_db(query, context)
        else:
            results = self._search_from_context(query, context)

        # 补充维度信息到结果
        enriched = self._enrich_with_dimensions(results, context)

        confidence = self._calc_confidence(enriched)

        return AgentResult(
            agent_id=self.agent_id,
            role=self.role,
            status=AgentStatus.COMPLETED,
            data={
                "results": enriched,
                "query": query,
                "strategy": "context",
                "result_count": len(enriched),
            },
            confidence=confidence,
        )

    async def _search_db(self, query: str, context: AgentContext) -> List[Dict[str, Any]]:
        """数据库上下文搜索"""
        try:
            # 基于分类和标签的上下文搜索
            categories = self._extract_categories(context)
            tags = self._extract_tags(context)

            conditions = [Memory.is_active == True]

            # 分类匹配
            if categories:
                cat_conditions = []
                for cat in categories:
                    cat_conditions.append(Memory.category.ilike(f"%{cat}%"))
                conditions.append(or_(*cat_conditions))

            # 标签匹配
            if tags:
                for tag in tags[:5]:
                    conditions.append(
                        Memory.tags.contains([tag])
                    )

            # 摘要语义匹配
            if query:
                conditions.append(Memory.summary.ilike(f"%{query}%"))

            if len(conditions) <= 1:
                # 无有效条件时返回空
                return []

            stmt = (
                select(Memory, Agent.name, Agent.reputation_score)
                .join(Agent, Memory.seller_agent_id == Agent.agent_id)
                .where(and_(*conditions))
                .order_by(Memory.purchase_count.desc())
                .limit(20)
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            memories = []
            for memory, seller_name, seller_rep in rows:
                ctx_score = self._context_score(query, memory, categories, tags)
                memories.append({
                    "memory_id": memory.memory_id,
                    "title": memory.title,
                    "summary": memory.summary,
                    "category": memory.category,
                    "tags": memory.tags or [],
                    "price": memory.price,
                    "context_score": ctx_score,
                    "seller_name": seller_name,
                    "seller_reputation": seller_rep,
                    "purchase_count": memory.purchase_count,
                })

            memories.sort(key=lambda x: x["context_score"], reverse=True)
            return memories[:10]

        except Exception as e:
            logger.error(f"ContextAgent DB search error: {e}")
            return []

    def _search_from_context(self, query: str, context: AgentContext) -> List[Dict[str, Any]]:
        """从上下文中搜索"""
        results = []
        query_lower = query.lower()

        for key, val in context.observations.items():
            if isinstance(val, dict):
                text = ""
                for field in ("summary", "content", "description", "category"):
                    v = val.get(field)
                    if isinstance(v, str):
                        text += " " + v

                if text.strip():
                    # 宽松匹配：关键词部分命中也算
                    words = query_lower.split()
                    match_count = sum(1 for w in words if w in text.lower())
                    if match_count > 0:
                        results.append({
                            "source": key,
                            "data": val,
                            "match_ratio": match_count / max(len(words), 1),
                        })

        results.sort(key=lambda x: x["match_ratio"], reverse=True)
        return results[:10]

    def _extract_categories(self, context: AgentContext) -> List[str]:
        """从上下文中提取分类"""
        cats = []
        raw = context.raw_data
        if "category" in raw and isinstance(raw["category"], str):
            cats.append(raw["category"])
        # 从维度中提取
        user_info = context.get_dimension("user_info")
        if user_info.get("company"):
            cats.append(user_info["company"])
        return cats

    def _extract_tags(self, context: AgentContext) -> List[str]:
        """从上下文中提取标签"""
        tags = []
        raw = context.raw_data
        if "tags" in raw:
            t = raw["tags"]
            if isinstance(t, list):
                tags.extend(t)
            elif isinstance(t, str):
                tags.extend(t.split(","))
        # 从偏好维度提取
        prefs = context.get_dimension("preferences")
        for key in ("tools", "programming_languages", "topics"):
            val = prefs.get(key)
            if isinstance(val, list):
                tags.extend(val)
        return [t.strip() for t in tags if t.strip()]

    def _context_score(
        self, query: str, memory, categories: List[str], tags: List[str]
    ) -> float:
        """计算上下文相关性分数"""
        score = 0.0
        mem_cat = (memory.category or "").lower()
        mem_tags = [t.lower() for t in (memory.tags or [])]

        # 分类匹配
        for cat in categories:
            if cat.lower() in mem_cat:
                score += 0.4
                break

        # 标签匹配
        matched_tags = 0
        for tag in tags:
            if tag.lower() in mem_tags:
                matched_tags += 1
        score += min(matched_tags * 0.15, 0.45)

        # 查询文本匹配
        query_lower = query.lower()
        if query_lower in (memory.title or "").lower():
            score += 0.3
        if query_lower in (memory.summary or "").lower():
            score += 0.2

        # 质量加成
        if memory.avg_score:
            score += (memory.avg_score / 5.0) * 0.1

        return min(score, 2.0)

    def _enrich_with_dimensions(
        self, results: List[Dict], context: AgentContext
    ) -> List[Dict]:
        """用维度信息丰富结果"""
        prefs = context.get_dimension("preferences")
        user_info = context.get_dimension("user_info")

        for r in results:
            r["dimension_context"] = {
                "user_interests": prefs.get("topics", []),
                "user_tools": prefs.get("tools", []),
                "user_company": user_info.get("company", ""),
            }
        return results

    def _calc_confidence(self, results: List) -> float:
        """计算置信度"""
        if not results:
            return 0.0
        avg_score = sum(r.get("context_score", 0) for r in results) / len(results)
        return min(avg_score, 1.0)
