"""混合搜索引擎

结合向量搜索和关键词搜索，提供更精准的检索结果
支持基于用户画像的个性化搜索
"""
from typing import List, Dict, Tuple, Optional, Set, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tables import Memory, Agent
from app.search.qdrant_engine import get_qdrant_engine
from app.services.user_profile_service import get_profile_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """混合搜索引擎

    结合 Qdrant 向量搜索和关键词搜索，使用 Rerank 策略融合结果
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu"
    ):
        """初始化混合搜索引擎

        Args:
            qdrant_url: Qdrant 服务地址
            qdrant_api_key: Qdrant API 密钥（可选）
            model_name: 嵌入模型名称
            device: 运行设备
        """
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.model_name = model_name
        self.device = device

        # 延迟加载 Qdrant 引擎
        self._qdrant_engine = None

    def _get_qdrant_engine(self):
        """获取 Qdrant 引擎（延迟加载）"""
        if self._qdrant_engine is None:
            self._qdrant_engine = get_qdrant_engine(
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                model_name=self.model_name,
                device=self.device
            )
        return self._qdrant_engine

    async def search(
        self,
        db: AsyncSession,
        query: str,
        base_stmt,
        search_type: str = "hybrid",
        top_k: int = 50,
        min_score: float = 0.1,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        enable_rerank: bool = True,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "relevance",
        filter_expired: bool = True
    ):
        """混合搜索

        Args:
            db: 数据库会话
            query: 搜索查询
            base_stmt: 基础 SQL 查询
            search_type: 搜索类型 (vector/keyword/hybrid)
            top_k: 返回前 k 个结果
            min_score: 最小相似度阈值
            semantic_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
            enable_rerank: 是否启用 Rerank
            page: 页码
            page_size: 每页数量
            sort_by: 排序方式
            filter_expired: 是否过滤过期记忆

        Returns:
            记忆列表
        """
        if not query.strip():
            # 无查询时返回所有结果
            return await self._execute_base_search(
                base_stmt, db, page, page_size, sort_by, filter_expired
            )

        # 获取所有候选记忆（用于关键词搜索和映射）
        all_result = await db.execute(base_stmt)
        all_memories = all_result.all()

        if not all_memories:
            from app.models.schemas import MemoryList
            return MemoryList(items=[], total=0, page=page, page_size=page_size)

        # 过滤过期记忆
        if filter_expired:
            all_memories = self._filter_expired_memories(all_memories)

        if not all_memories:
            from app.models.schemas import MemoryList
            return MemoryList(items=[], total=0, page=page, page_size=page_size)

        # 构建记忆映射
        memory_map = {row.Memory.memory_id: row for row in all_memories}

        # 根据搜索类型执行搜索
        if search_type == "vector":
            # 纯向量搜索
            results = await self._vector_search(
                query, memory_map, top_k, min_score
            )
        elif search_type == "keyword":
            # 纯关键词搜索
            results = await self._keyword_search(
                query, memory_map, base_stmt, db, page, page_size, sort_by
            )
        else:
            # 混合搜索（默认）
            results = await self._hybrid_search(
                query, memory_map, base_stmt, db,
                top_k, min_score, semantic_weight, keyword_weight, enable_rerank
            )

        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_results = results[start_idx:end_idx]

        # 转换为响应格式
        from app.models.schemas import MemoryList
        from app.services.memory_service import memory_to_response

        items = []
        for memory_id, score, row in paged_results:
            memory, seller_name, seller_reputation = row
            items.append(memory_to_response(memory, seller_name, seller_reputation))

        return MemoryList(
            items=items,
            total=len(results),
            page=page,
            page_size=page_size
        )

    async def _vector_search(
        self,
        query: str,
        memory_map: Dict[str, Any],
        top_k: int,
        min_score: float
    ) -> List[Tuple[str, float, Any]]:
        """纯向量搜索

        Args:
            query: 搜索查询
            memory_map: 记忆映射字典
            top_k: 返回数量
            min_score: 最小分数

        Returns:
            [(memory_id, score, row), ...]
        """
        qdrant = self._get_qdrant_engine()

        # 执行向量搜索
        vector_results = qdrant.search(
            query=query,
            top_k=top_k,
            min_score=min_score
        )

        # 映射回记忆对象
        results = []
        for memory_id, score, payload in vector_results:
            if memory_id in memory_map:
                results.append((memory_id, score, memory_map[memory_id]))

        return results

    async def _keyword_search(
        self,
        query: str,
        memory_map: Dict[str, Any],
        base_stmt,
        db: AsyncSession,
        page: int,
        page_size: int,
        sort_by: str
    ):
        """纯关键词搜索

        Args:
            query: 搜索查询
            memory_map: 记忆映射字典
            base_stmt: 基础查询
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            sort_by: 排序方式

        Returns:
            MemoryList
        """
        from app.models.schemas import MemoryList
        from app.services.memory_service import _execute_search

        # 关键词过滤
        stmt = base_stmt
        if query:
            stmt = stmt.where(
                or_(
                    Memory.title.ilike(f"%{query}%"),
                    Memory.summary.ilike(f"%{query}%")
                )
            )

        # 执行搜索
        return await _execute_search(stmt, db, page, page_size, sort_by)

    async def _hybrid_search(
        self,
        query: str,
        memory_map: Dict[str, Any],
        base_stmt,
        db: AsyncSession,
        top_k: int,
        min_score: float,
        semantic_weight: float,
        keyword_weight: float,
        enable_rerank: bool
    ) -> List[Tuple[str, float, Any]]:
        """混合搜索：向量 + 关键词

        Args:
            query: 搜索查询
            memory_map: 记忆映射字典
            base_stmt: 基础查询
            db: 数据库会话
            top_k: 返回数量
            min_score: 最小分数
            semantic_weight: 语义权重
            keyword_weight: 关键词权重
            enable_rerank: 是否启用 Rerank

        Returns:
            [(memory_id, score, row), ...]
        """
        # 1. 向量搜索
        qdrant = self._get_qdrant_engine()
        vector_results = qdrant.search(
            query=query,
            top_k=top_k * 2,  # 获取更多候选结果
            min_score=min_score
        )

        # 2. 关键词搜索
        keyword_stmt = base_stmt
        if query:
            keyword_stmt = keyword_stmt.where(
                or_(
                    Memory.title.ilike(f"%{query}%"),
                    Memory.summary.ilike(f"%{query}%")
                )
            )

        keyword_result = await db.execute(keyword_stmt)
        keyword_memories = keyword_result.all()
        keyword_ids = {row.Memory.memory_id for row in keyword_memories}

        # 3. 融合结果
        hybrid_scores = {}

        # 向量搜索得分（归一化）
        if vector_results:
            max_vector_score = max(score for _, score, _ in vector_results)
            if max_vector_score > 0:
                for memory_id, score, payload in vector_results:
                    normalized_score = score / max_vector_score
                    if memory_id in memory_map:
                        hybrid_scores[memory_id] = normalized_score * semantic_weight

        # 关键词匹配加分
        for memory_id in keyword_ids:
            if memory_id in hybrid_scores:
                hybrid_scores[memory_id] += keyword_weight
            else:
                hybrid_scores[memory_id] = keyword_weight * 0.5

        # 4. Rerank（可选）
        if enable_rerank:
            hybrid_scores = await self._rerank(query, hybrid_scores, memory_map)

        # 5. 排序
        sorted_results = sorted(
            hybrid_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 6. 映射回记忆对象
        final_results = []
        for memory_id, score in sorted_results[:top_k]:
            if memory_id in memory_map:
                final_results.append((memory_id, score, memory_map[memory_id]))

        return final_results

    async def _rerank(
        self,
        query: str,
        scores: Dict[str, float],
        memory_map: Dict[str, Any]
    ) -> Dict[str, float]:
        """Rerank 搜索结果

        优先使用 Cross-Encoder 进行精确重排，失败时回退到规则重排：
        - Cross-Encoder: 深度语义理解，query-content 精确匹配
        - 规则重排: 文本相似度、信号质量、时效性、价格合理性

        Args:
            query: 搜索查询
            scores: 原始分数
            memory_map: 记忆映射

        Returns:
            Rerank后的分数
        """
        # 尝试使用 Cross-Encoder 重排
        try:
            from app.services.reranking_service import get_reranking_service
            from app.core.config import settings

            if settings.RERANK_ENABLED:
                rerank_service = get_reranking_service(
                    model_name=settings.RERANK_MODEL,
                    top_k=50,
                    threshold=settings.RERANK_THRESHOLD
                )

                # 构建候选结果
                candidates = []
                for memory_id, base_score in scores.items():
                    row = memory_map.get(memory_id)
                    if row:
                        memory = row.Memory
                        candidates.append({
                            'memory_id': memory_id,
                            'title': memory.title or '',
                            'summary': memory.summary or '',
                            'content': str(memory.content) if memory.content else '',
                            'base_score': base_score
                        })

                # 执行 Cross-Encoder 重排
                reranked = await rerank_service.rerank(query, candidates, use_cache=True)

                # 提取重排分数（融合原始分数和重排分数）
                reranked_scores = {}
                for item in reranked:
                    memory_id = item['memory_id']
                    rerank_score = item.get('rerank_score', 0)
                    base_score = item.get('base_score', 0)

                    # 加权融合：重排分数占 70%，原始分数占 30%
                    reranked_scores[memory_id] = rerank_score * 0.7 + base_score * 0.3

                logger.info(f"Cross-Encoder rerank: {len(candidates)} -> {len(reranked)} candidates")
                return reranked_scores

        except Exception as e:
            logger.warning(f"Cross-Encoder rerank failed, fallback to rule-based: {e}")

        # 回退到规则重排
        reranked_scores = {}

        for memory_id, base_score in scores.items():
            row = memory_map.get(memory_id)
            if not row:
                continue

            memory = row.Memory

            # 文本相似度
            query_lower = query.lower()
            title_lower = (memory.title or "").lower()
            summary_lower = (memory.summary or "").lower()

            text_sim = 0.0
            if query_lower in title_lower:
                text_sim += 0.3
            if query_lower in summary_lower:
                text_sim += 0.2

            # 信号质量
            signal_score = 0.0
            if memory.avg_score:
                signal_score += (memory.avg_score / 5.0) * 0.2
            if memory.purchase_count:
                # 对数平滑，避免购买次数影响过大
                import math
                signal_score += min(math.log10(memory.purchase_count + 1) / math.log10(100), 0.3)
            if memory.verification_score:
                signal_score += memory.verification_score * 0.2

            # 时效性（新内容优先）
            time_score = 0.0
            if memory.created_at:
                from datetime import datetime
                days_old = (datetime.now() - memory.created_at).days
                if days_old <= 7:
                    time_score = 0.1
                elif days_old <= 30:
                    time_score = 0.05

            # 价格合理性（适中价格加分）
            price_score = 0.0
            if 0 < memory.price <= 100:
                price_score = 0.1
            elif 0 < memory.price <= 300:
                price_score = 0.05

            # 加权融合
            reranked_score = (
                base_score * 0.5 +  # 原始搜索分数
                text_sim +  # 文本相似度
                signal_score +  # 信号质量
                time_score +  # 时效性
                price_score  # 价格合理性
            )

            reranked_scores[memory_id] = reranked_score

        return reranked_scores

    async def personalized_search(
        self,
        db: AsyncSession,
        query: str,
        agent_id: str,
        base_stmt,
        search_type: str = "hybrid",
        top_k: int = 50,
        min_score: float = 0.1,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        enable_rerank: bool = True,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "relevance",
        filter_expired: bool = True
    ):
        """个性化搜索：基于用户画像优化搜索结果

        Args:
            db: 数据库会话
            query: 搜索查询
            agent_id: 用户ID
            base_stmt: 基础 SQL 查询
            search_type: 搜索类型 (vector/keyword/hybrid)
            top_k: 返回前 k 个结果
            min_score: 最小相似度阈值
            semantic_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
            enable_rerank: 是否启用 Rerank
            page: 页码
            page_size: 每页数量
            sort_by: 排序方式
            filter_expired: 是否过滤过期记忆

        Returns:
            记忆列表
        """
        if not settings.PROFILE_ENABLED:
            # 如果画像系统未启用，回退到普通搜索
            return await self.search(
                db, query, base_stmt, search_type, top_k, min_score,
                semantic_weight, keyword_weight, enable_rerank, page, page_size, sort_by, filter_expired
            )

        # 1. 执行基础搜索
        results = await self.search(
            db, query, base_stmt, search_type, top_k, min_score,
            semantic_weight, keyword_weight, enable_rerank, page, page_size, sort_by, filter_expired
        )

        # 2. 获取用户画像
        profile_service = get_profile_service()
        user_profile = await profile_service.get_profile(db, agent_id, use_cache=True)

        if not user_profile:
            # 无画像数据，直接返回搜索结果
            return results

        # 3. 应用画像个性化
        personalized_results = await self._apply_profile_personalization(
            db, results, user_profile, query, agent_id
        )

        return personalized_results

    def _filter_expired_memories(self, memories):
        """过滤过期记忆

        Args:
            memories: 记忆列表

        Returns:
            过滤后的记忆列表
        """
        from datetime import datetime

        now = datetime.now()
        filtered = []

        for row in memories:
            memory = row.Memory

            # 检查是否过期
            if memory.is_active:
                # 没有过期时间或过期时间在未来
                if memory.expiry_time is None or memory.expiry_time > now:
                    filtered.append(row)

        return filtered

    async def _execute_base_search(
        self,
        base_stmt,
        db: AsyncSession,
        page: int,
        page_size: int,
        sort_by: str,
        filter_expired: bool = True
    ):
        """执行基础搜索（无查询时）"""
        from app.services.memory_service import _execute_search

        # 如果需要过滤过期记忆，添加条件
        if filter_expired:
            from datetime import datetime
            now = datetime.now()

            # 添加过滤条件：仅返回未过期的记忆
            from sqlalchemy import and_
            base_stmt = base_stmt.where(
                and_(
                    Memory.is_active == True,
                    or_(
                        Memory.expiry_time.is_(None),
                        Memory.expiry_time > now
                    )
                )
            )

        return await _execute_search(base_stmt, db, page, page_size, sort_by)

    async def _apply_profile_personalization(
        self,
        db: AsyncSession,
        results,
        user_profile: Dict[str, Any],
        query: str,
        agent_id: str
    ):
        """应用用户画像个性化搜索结果

        Args:
            db: 数据库会话
            results: 搜索结果
            user_profile: 用户画像
            query: 搜索查询
            agent_id: 用户ID

        Returns:
            个性化后的结果
        """
        personalized_items = []

        # 提取画像特征
        user_language = user_profile.get('language', 'zh')
        user_interests = user_profile.get('interests', []) or []
        user_research_areas = user_profile.get('research_areas', []) or []
        user_skills = user_profile.get('skills', []) or []
        user_tech_stack = user_profile.get('tech_stack', []) or []
        user_preferred_topics = user_interests + user_research_areas

        for item in results.items:
            memory = item.__dict__ if hasattr(item, '__dict__') else item
            if isinstance(memory, dict):
                memory_dict = memory
            else:
                continue

            # 计算个性化得分
            personalization_score = 0.0

            # 1. 语言匹配（中文/英文）
            title = memory_dict.get('title', '')
            summary = memory_dict.get('summary', '')
            content_text = f"{title} {summary}"

            if user_language == 'zh':
                # 中文用户偏好中文内容
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_text)
                if has_chinese:
                    personalization_score += 0.1
            elif user_language == 'en':
                # 英文用户偏好英文内容
                has_english = content_text.strip() and content_text[0].isascii()
                if has_english:
                    personalization_score += 0.1

            # 2. 兴趣匹配
            category = memory_dict.get('category', '')
            tags = memory_dict.get('tags', []) or []

            for interest in user_preferred_topics:
                interest_lower = interest.lower()
                if interest_lower in category.lower():
                    personalization_score += 0.2
                for tag in tags:
                    if interest_lower in tag.lower():
                        personalization_score += 0.15
                        break

            # 3. 技术栈匹配
            for skill in user_skills + user_tech_stack:
                skill_name = skill.get('name') if isinstance(skill, dict) else skill
                skill_lower = skill_name.lower()
                if skill_lower in content_text.lower():
                    personalization_score += 0.1

            # 4. 编辑器偏好（对于编程相关记忆）
            user_editor = user_profile.get('editor', '').lower()
            if user_editor and ('editor' in content_text.lower() or 'ide' in content_text.lower()):
                if user_editor in content_text.lower():
                    personalization_score += 0.15

            # 5. 主题偏好（对于UI/设计相关记忆）
            user_theme = user_profile.get('theme', '').lower()
            if user_theme and ('theme' in content_text.lower() or 'design' in content_text.lower()):
                if user_theme in content_text.lower():
                    personalization_score += 0.1

            # 更新排序权重（结合原有排序和个性化得分）
            # 假设原有结果有某种 relevance_score，否则使用默认
            base_relevance = getattr(item, 'relevance_score', 0.5) if hasattr(item, 'relevance_score') else 0.5
            final_score = base_relevance * 0.8 + personalization_score * 0.2

            # 添加个性化得分到结果
            if hasattr(item, 'personalization_score'):
                item.personalization_score = personalization_score
                item.final_score = final_score

            personalized_items.append(item)

        # 按最终得分重新排序
        personalized_items.sort(
            key=lambda x: getattr(x, 'final_score', 0.5),
            reverse=True
        )

        # 更新返回结果
        results.items = personalized_items

        return results

    async def _execute_base_search(
        self,
        base_stmt,
        db: AsyncSession,
        page: int,
        page_size: int,
        sort_by: str
    ):
        """执行基础搜索（无查询时）"""
        from app.services.memory_service import _execute_search
        return await _execute_search(base_stmt, db, page, page_size, sort_by)


# 全局单例
_hybrid_engine: Optional[HybridSearchEngine] = None


def get_hybrid_engine(
    qdrant_url: str = "http://localhost:6333",
    qdrant_api_key: Optional[str] = None,
    model_name: str = "BAAI/bge-small-zh-v1.5",
    device: str = "cpu"
) -> HybridSearchEngine:
    """获取混合搜索引擎单例

    Args:
        qdrant_url: Qdrant 服务地址
        qdrant_api_key: Qdrant API 密钥（可选）
        model_name: 嵌入模型名称
        device: 运行设备

    Returns:
        混合搜索引擎实例
    """
    global _hybrid_engine
    if _hybrid_engine is None:
        _hybrid_engine = HybridSearchEngine(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            model_name=model_name,
            device=device
        )
    return _hybrid_engine
