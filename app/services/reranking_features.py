"""重排特征工程模块

提取多维度特征用于智能重排：
- 语义相似度特征（Cross-Encoder 分数）
- 关键词匹配特征（BM25 风格 + 精确匹配）
- 时效性特征（时间衰减）
- 用户偏好特征（个性化）
- 记忆质量特征（信号质量）
"""
from __future__ import annotations
import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class FeatureVector:
    """特征向量，存储一条候选记忆的所有特征"""
    memory_id: str
    # 语义特征
    semantic_score: float = 0.0          # Cross-Encoder 分数 (0-1)
    embedding_similarity: float = 0.0    # 向量余弦相似度 (0-1)
    # 关键词特征
    keyword_exact_match: float = 0.0     # 精确关键词匹配得分 (0-1)
    keyword_bm25_score: float = 0.0      # BM25 风格得分 (归一化 0-1)
    keyword_title_match: float = 0.0     # 标题关键词命中 (0/1)
    keyword_tag_match: float = 0.0       # 标签匹配数量 (归一化)
    # 时效性特征
    recency_score: float = 0.0           # 时效性得分 (0-1)
    freshness_score: float = 0.0         # 新鲜度得分 (0-1, 近7天=1)
    # 用户偏好特征
    user_interest_match: float = 0.0     # 用户兴趣匹配 (0-1)
    user_history_match: float = 0.0      # 用户历史偏好 (0-1)
    user_category_affinity: float = 0.0  # 用户分类亲和度 (0-1)
    # 记忆质量特征
    quality_signal: float = 0.0          # 综合信号质量 (0-1)
    purchase_popularity: float = 0.0     # 购买热度 (0-1)
    rating_score: float = 0.0            # 评分得分 (0-1)
    verification_strength: float = 0.0   # 验证强度 (0-1)
    # 融合分数
    final_score: float = 0.0             # 最终融合分数
    # 原始数据引用
    raw_data: Dict[str, Any] = field(default_factory=dict)


class FeatureExtractor:
    """特征提取器

    从候选记忆和查询中提取多维度特征
    """

    # 停用词（中英文混合）
    STOP_WORDS: Set[str] = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "他", "她", "它", "们", "那", "里", "又", "来", "把", "让",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "and", "or", "but", "not", "no", "so", "if", "than", "too", "very",
    }

    def __init__(self, now: Optional[datetime] = None):
        self.now = now or datetime.now()

    def extract_features(
        self,
        query: str,
        candidate: Dict[str, Any],
        semantic_score: float = 0.0,
        embedding_similarity: float = 0.0,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> FeatureVector:
        """提取单条候选的特征向量

        Args:
            query: 搜索查询
            candidate: 候选记忆（dict 形式）
            semantic_score: Cross-Encoder 语义分数
            embedding_similarity: 向量相似度分数
            user_profile: 用户画像（可选）

        Returns:
            FeatureVector
        """
        memory_id = candidate.get("memory_id", "")
        title = candidate.get("title", "") or ""
        summary = candidate.get("summary", "") or ""
        content_text = candidate.get("content_text", "") or ""
        tags = candidate.get("tags", []) or []
        category = candidate.get("category", "") or ""
        created_at = candidate.get("created_at")

        # 解析时间
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = None

        fv = FeatureVector(
            memory_id=memory_id,
            semantic_score=semantic_score,
            embedding_similarity=embedding_similarity,
            raw_data=candidate,
        )

        # ── 关键词特征 ──
        query_terms = self._tokenize(query)
        title_lower = title.lower()
        summary_lower = summary.lower()
        content_lower = content_text.lower()
        combined_text = f"{title_lower} {summary_lower} {content_lower}"

        # 精确匹配
        if query_terms:
            match_count = sum(1 for t in query_terms if t in combined_text)
            fv.keyword_exact_match = match_count / len(query_terms)
            fv.keyword_title_match = 1.0 if any(t in title_lower for t in query_terms) else 0.0
        else:
            fv.keyword_exact_match = 0.0
            fv.keyword_title_match = 0.0

        # BM25 风格得分
        fv.keyword_bm25_score = self._bm25_score(query_terms, title_lower, summary_lower, content_lower)

        # 标签匹配
        if tags and query_terms:
            tag_text = " ".join(str(t).lower() for t in tags)
            tag_matches = sum(1 for t in query_terms if t in tag_text)
            fv.keyword_tag_match = tag_matches / len(query_terms)
        else:
            fv.keyword_tag_match = 0.0

        # ── 时效性特征 ──
        fv.recency_score = self._recency_score(created_at)
        fv.freshness_score = self._freshness_score(created_at)

        # ── 用户偏好特征 ──
        if user_profile:
            fv.user_interest_match = self._interest_match(
                candidate, user_profile
            )
            fv.user_history_match = self._history_match(
                candidate, user_profile
            )
            fv.user_category_affinity = self._category_affinity(
                category, user_profile
            )
        else:
            fv.user_interest_match = 0.0
            fv.user_history_match = 0.0
            fv.user_category_affinity = 0.0

        # ── 记忆质量特征 ──
        avg_score = candidate.get("avg_score", 0.0) or 0.0
        purchase_count = candidate.get("purchase_count", 0) or 0
        verification_score = candidate.get("verification_score", 0.0) or 0.0

        fv.rating_score = min(avg_score / 5.0, 1.0) if avg_score > 0 else 0.0
        fv.purchase_popularity = min(math.log1p(purchase_count) / math.log1p(100), 1.0)
        fv.verification_strength = min(verification_score, 1.0) if verification_score > 0 else 0.0
        fv.quality_signal = (
            fv.rating_score * 0.4
            + fv.purchase_popularity * 0.35
            + fv.verification_strength * 0.25
        )

        return fv

    def extract_batch(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        semantic_scores: Optional[List[float]] = None,
        embedding_similarities: Optional[List[float]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> List[FeatureVector]:
        """批量提取特征

        Args:
            query: 搜索查询
            candidates: 候选列表
            semantic_scores: 每个候选的语义分数列表
            embedding_similarities: 每个候选的向量相似度列表
            user_profile: 用户画像

        Returns:
            FeatureVector 列表
        """
        n = len(candidates)
        if semantic_scores is None:
            semantic_scores = [0.0] * n
        if embedding_similarities is None:
            embedding_similarities = [0.0] * n

        return [
            self.extract_features(
                query=query,
                candidate=c,
                semantic_score=semantic_scores[i],
                embedding_similarity=embedding_similarities[i],
                user_profile=user_profile,
            )
            for i, c in enumerate(candidates)
        ]

    # ── 内部方法 ──

    def _tokenize(self, text: str) -> List[str]:
        """分词：对中文按字符切分，对英文按空格切分"""
        text = text.lower().strip()
        tokens = []
        # 英文单词
        en_tokens = re.findall(r'[a-z][a-z0-9]*', text)
        tokens.extend(en_tokens)
        # 中文字符（每个字作为一个 token）
        cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(cn_chars)
        # 中文2-gram（捕捉词边界）
        for i in range(len(cn_chars) - 1):
            tokens.append(cn_chars[i] + cn_chars[i + 1])
        # 过滤停用词
        return [t for t in tokens if t not in self.STOP_WORDS and len(t) > 0]

    def _bm25_score(
        self,
        query_terms: List[str],
        title: str,
        summary: str,
        content: str,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        """计算简化的 BM25 风格得分

        对每个查询词，计算其在标题/摘要/内容中的 TF，加权求和后归一化。
        """
        if not query_terms:
            return 0.0

        title_len = max(len(title), 1)
        summary_len = max(len(summary), 1)
        content_len = max(len(content), 1)
        avg_len = (title_len + summary_len + content_len) / 3

        total_score = 0.0
        for term in query_terms:
            # TF（标题权重 3x，摘要 2x，内容 1x）
            tf_title = title.count(term) * 3
            tf_summary = summary.count(term) * 2
            tf_content = content.count(term)
            tf = tf_title + tf_summary + tf_content

            if tf == 0:
                continue

            # 简化 BM25
            dl = title_len + summary_len + content_len
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_len))
            total_score += tf_norm

        # 归一化到 0-1
        max_possible = len(query_terms) * (k1 + 1)
        return min(total_score / max_possible, 1.0) if max_possible > 0 else 0.0

    def _recency_score(self, created_at: Optional[datetime]) -> float:
        """计算时效性得分（指数衰减）

        使用半衰期 30 天的指数衰减模型。
        """
        if created_at is None:
            return 0.5  # 无时间信息，给中等分

        days_old = (self.now - created_at).total_seconds() / 86400
        if days_old < 0:
            days_old = 0

        # 半衰期 30 天
        half_life = 30.0
        score = math.exp(-0.693 * days_old / half_life)
        return round(score, 4)

    def _freshness_score(self, created_at: Optional[datetime]) -> float:
        """计算新鲜度得分

        - 7天内 = 1.0
        - 7-30天线性衰减到 0.5
        - 30天以上继续衰减到 0.1
        """
        if created_at is None:
            return 0.3

        days_old = (self.now - created_at).total_seconds() / 86400
        if days_old < 0:
            days_old = 0

        if days_old <= 7:
            return 1.0
        elif days_old <= 30:
            return 1.0 - (days_old - 7) / 23 * 0.5
        else:
            return max(0.5 * math.exp(-0.03 * (days_old - 30)), 0.1)

    def _interest_match(
        self, candidate: Dict, profile: Dict
    ) -> float:
        """计算用户兴趣匹配度"""
        interests = profile.get("interests", []) or []
        research_areas = profile.get("research_areas", []) or []
        tech_stack = profile.get("tech_stack", []) or []

        if not interests and not research_areas and not tech_stack:
            return 0.0

        candidate_text = " ".join([
            str(candidate.get("title", "")),
            str(candidate.get("summary", "")),
            str(candidate.get("category", "")),
            " ".join(str(t) for t in (candidate.get("tags") or [])),
        ]).lower()

        match_count = 0
        total_keywords = 0

        for kw_list in [interests, research_areas]:
            for kw in kw_list:
                total_keywords += 1
                if str(kw).lower() in candidate_text:
                    match_count += 1

        for item in tech_stack:
            name = item.get("name", "") if isinstance(item, dict) else str(item)
            total_keywords += 1
            if name.lower() in candidate_text:
                match_count += 1

        return match_count / total_keywords if total_keywords > 0 else 0.0

    def _history_match(self, candidate: Dict, profile: Dict) -> float:
        """计算用户历史偏好匹配度"""
        preferred_categories = profile.get("preferred_categories", []) or []
        preferred_tags = profile.get("preferred_tags", []) or []

        if not preferred_categories and not preferred_tags:
            return 0.0

        score = 0.0
        category = str(candidate.get("category", "")).lower()
        tags = [str(t).lower() for t in (candidate.get("tags") or [])]

        for cat in preferred_categories:
            if str(cat).lower() in category:
                score += 0.6
                break

        for pref_tag in preferred_tags:
            for tag in tags:
                if str(pref_tag).lower() in tag:
                    score += 0.4
                    break

        return min(score, 1.0)

    def _category_affinity(self, category: str, profile: Dict) -> float:
        """计算分类亲和度"""
        preferred = profile.get("preferred_categories", []) or []
        if not preferred or not category:
            return 0.0

        cat_lower = category.lower()
        for pref in preferred:
            if str(pref).lower() in cat_lower or cat_lower in str(pref).lower():
                return 1.0
        return 0.0


# 全局单例
_extractor: Optional[FeatureExtractor] = None


def get_feature_extractor(now: Optional[datetime] = None) -> FeatureExtractor:
    """获取特征提取器单例"""
    global _extractor
    if _extractor is None:
        _extractor = FeatureExtractor(now=now)
    return _extractor


def reset_feature_extractor():
    """重置（用于测试）"""
    global _extractor
    _extractor = None
