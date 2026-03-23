"""搜索分析API - 提供搜索趋势、质量指标和性能统计"""
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, case, text
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, get_current_agent, require_admin
from app.models.tables import SearchLog, SearchClick, Agent, Memory
from app.models.schemas import (
    SearchTrend, SearchQualityMetrics, SearchPerformanceStats,
    UserSearchBehavior, SearchAnalyticsResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search-analytics", tags=["search-analytics"])


@router.get("/trends", response_model=List[SearchTrend])
async def get_search_trends(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    limit: int = Query(20, ge=5, le=100, description="返回热门查询数量"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取搜索趋势（热门查询）"""
    # 计算时间范围
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 查询热门查询
    query = (
        select(
            SearchLog.query,
            func.count(SearchLog.log_id).label("count"),
            func.avg(SearchLog.result_count).label("avg_result_count"),
            func.avg(SearchLog.response_time_ms).label("avg_response_time_ms")
        )
        .where(
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        )
        .group_by(SearchLog.query)
        .order_by(desc("count"))
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    trends = []
    for row in rows:
        # 获取该查询最常出现的分类
        category_query = (
            select(SearchLog.category)
            .where(
                SearchLog.query == row.query,
                SearchLog.category.isnot(None)
            )
            .group_by(SearchLog.category)
            .order_by(desc(func.count(SearchLog.log_id)))
            .limit(3)
        )
        category_result = await db.execute(category_query)
        top_categories = [c for c, in category_result.all()]

        trends.append(SearchTrend(
            query=row.query,
            count=row.count,
            avg_result_count=round(row.avg_result_count or 0, 2),
            avg_response_time_ms=round(row.avg_response_time_ms or 0, 2),
            top_categories=top_categories
        ))

    return trends


@router.get("/quality", response_model=SearchQualityMetrics)
async def get_search_quality(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取搜索质量指标"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 总搜索数
    total_searches_result = await db.execute(
        select(func.count(SearchLog.log_id))
        .where(SearchLog.created_at >= start_date)
    )
    total_searches = total_searches_result.scalar() or 0

    if total_searches == 0:
        return SearchQualityMetrics(
            total_searches=0,
            unique_users=0,
            avg_result_count=0,
            avg_response_time_ms=0,
            ctr=0,
            zero_results_rate=0,
            top_queries=[],
            top_zero_result_queries=[]
        )

    # 唯一用户数
    unique_users_result = await db.execute(
        select(func.count(func.distinct(SearchLog.agent_id)))
        .where(SearchLog.created_at >= start_date)
    )
    unique_users = unique_users_result.scalar() or 0

    # 平均结果数和响应时间
    avg_stats_result = await db.execute(
        select(
            func.avg(SearchLog.result_count).label("avg_result_count"),
            func.avg(SearchLog.response_time_ms).label("avg_response_time_ms")
        )
        .where(SearchLog.created_at >= start_date)
    )
    avg_stats = avg_stats_result.first()
    avg_result_count = round(avg_stats.avg_result_count or 0, 2)
    avg_response_time_ms = round(avg_stats.avg_response_time_ms or 0, 2)

    # 零结果率
    zero_results_result = await db.execute(
        select(func.count(SearchLog.log_id))
        .where(
            and_(
                SearchLog.created_at >= start_date,
                SearchLog.result_count == 0
            )
        )
    )
    zero_results_count = zero_results_result.scalar() or 0
    zero_results_rate = round(zero_results_count / total_searches * 100, 2)

    # 点击率（CTR）
    # 统计有点击的搜索数
    searches_with_clicks_result = await db.execute(
        select(func.count(func.distinct(SearchClick.search_log_id)))
        .join(SearchLog, SearchClick.search_log_id == SearchLog.log_id)
        .where(SearchLog.created_at >= start_date)
    )
    searches_with_clicks = searches_with_clicks_result.scalar() or 0
    ctr = round(searches_with_clicks / total_searches * 100, 2)

    # 热门查询
    top_queries_result = await db.execute(
        select(SearchLog.query, func.count(SearchLog.log_id).label("count"))
        .where(SearchLog.created_at >= start_date)
        .group_by(SearchLog.query)
        .order_by(desc("count"))
        .limit(10)
    )
    top_queries = [row.query for row in top_queries_result.all()]

    # 零结果热门查询
    top_zero_result_queries_result = await db.execute(
        select(SearchLog.query, func.count(SearchLog.log_id).label("count"))
        .where(
            and_(
                SearchLog.created_at >= start_date,
                SearchLog.result_count == 0
            )
        )
        .group_by(SearchLog.query)
        .order_by(desc("count"))
        .limit(10)
    )
    top_zero_result_queries = [row.query for row in top_zero_result_queries_result.all()]

    return SearchQualityMetrics(
        total_searches=total_searches,
        unique_users=unique_users,
        avg_result_count=avg_result_count,
        avg_response_time_ms=avg_response_time_ms,
        ctr=ctr,
        zero_results_rate=zero_results_rate,
        top_queries=top_queries,
        top_zero_result_queries=top_zero_result_queries
    )


@router.get("/performance", response_model=SearchPerformanceStats)
async def get_search_performance(
    period: str = Query("day", description="统计周期: hour/day/week"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取搜索性能统计"""
    # 根据周期计算时间范围
    if period == "hour":
        start_date = datetime.utcnow() - timedelta(hours=1)
    elif period == "day":
        start_date = datetime.utcnow() - timedelta(days=1)
    elif period == "week":
        start_date = datetime.utcnow() - timedelta(weeks=1)
    else:
        raise HTTPException(status_code=400, detail="Invalid period. Use: hour, day, or week")

    # 搜索数量
    search_count_result = await db.execute(
        select(func.count(SearchLog.log_id))
        .where(SearchLog.created_at >= start_date)
    )
    search_count = search_count_result.scalar() or 0

    if search_count == 0:
        return SearchPerformanceStats(
            period=period,
            search_count=0,
            avg_response_time_ms=0,
            p50_response_time_ms=0,
            p95_response_time_ms=0,
            p99_response_time_ms=0,
            slow_searches_count=0
        )

    # 响应时间统计
    response_times_result = await db.execute(
        select(SearchLog.response_time_ms)
        .where(SearchLog.created_at >= start_date)
        .order_by(SearchLog.response_time_ms)
    )
    response_times = [row[0] for row in response_times_result.all()]

    # 计算百分位数
    avg_response_time_ms = round(sum(response_times) / len(response_times), 2)
    p50_index = int(len(response_times) * 0.5)
    p95_index = int(len(response_times) * 0.95)
    p99_index = int(len(response_times) * 0.99)

    p50_response_time_ms = response_times[p50_index]
    p95_response_time_ms = response_times[p95_index]
    p99_response_time_ms = response_times[p99_index]

    # 慢查询数量（>1秒）
    slow_searches_result = await db.execute(
        select(func.count(SearchLog.log_id))
        .where(
            and_(
                SearchLog.created_at >= start_date,
                SearchLog.response_time_ms > 1000
            )
        )
    )
    slow_searches_count = slow_searches_result.scalar() or 0

    return SearchPerformanceStats(
        period=period,
        search_count=search_count,
        avg_response_time_ms=avg_response_time_ms,
        p50_response_time_ms=p50_response_time_ms,
        p95_response_time_ms=p95_response_time_ms,
        p99_response_time_ms=p99_response_time_ms,
        slow_searches_count=slow_searches_count
    )


@router.get("/zero-results")
async def get_zero_results_queries(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    limit: int = Query(50, ge=10, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取零结果查询列表"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    result = await db.execute(
        select(
            SearchLog.query,
            func.count(SearchLog.log_id).label("count"),
            func.avg(SearchLog.response_time_ms).label("avg_response_time_ms"),
            func.count(func.distinct(SearchLog.agent_id)).label("unique_users")
        )
        .where(
            and_(
                SearchLog.created_at >= start_date,
                SearchLog.result_count == 0
            )
        )
        .group_by(SearchLog.query)
        .order_by(desc("count"))
        .limit(limit)
    )

    rows = result.all()

    return {
        "period_days": days,
        "queries": [
            {
                "query": row.query,
                "count": row.count,
                "avg_response_time_ms": round(row.avg_response_time_ms or 0, 2),
                "unique_users": row.unique_users
            }
            for row in rows
        ]
    }


@router.get("/user-behavior", response_model=List[UserSearchBehavior])
async def get_user_search_behavior(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    limit: int = Query(50, ge=10, le=200, description="返回用户数量"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取用户搜索行为统计"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 统计每个用户的搜索行为
    query = (
        select(
            SearchLog.agent_id,
            Agent.name.label("agent_name"),
            func.count(SearchLog.log_id).label("total_searches"),
            func.count(func.distinct(SearchLog.query)).label("unique_queries"),
            func.avg(SearchLog.result_count).label("avg_result_count"),
            func.max(SearchLog.created_at).label("last_search_at")
        )
        .join(Agent, SearchLog.agent_id == Agent.agent_id)
        .where(SearchLog.created_at >= start_date)
        .group_by(SearchLog.agent_id, Agent.name)
        .order_by(desc("total_searches"))
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    user_behaviors = []
    for row in rows:
        # 计算点击率
        searches_with_clicks_result = await db.execute(
            select(func.count(func.distinct(SearchClick.search_log_id)))
            .join(SearchLog, SearchClick.search_log_id == SearchLog.log_id)
            .where(
                and_(
                    SearchLog.agent_id == row.agent_id,
                    SearchLog.created_at >= start_date
                )
            )
        )
        searches_with_clicks = searches_with_clicks_result.scalar() or 0
        ctr = round(searches_with_clicks / row.total_searches * 100, 2) if row.total_searches > 0 else 0

        # 计算平均每天搜索次数
        avg_searches_per_day = round(row.total_searches / days, 2)

        # 获取用户最喜欢的查询
        favorite_queries_result = await db.execute(
            select(SearchLog.query, func.count(SearchLog.log_id).label("count"))
            .where(
                and_(
                    SearchLog.agent_id == row.agent_id,
                    SearchLog.created_at >= start_date
                )
            )
            .group_by(SearchLog.query)
            .order_by(desc("count"))
            .limit(5)
        )
        favorite_queries = [q for q, in favorite_queries_result.all()]

        user_behaviors.append(UserSearchBehavior(
            agent_id=row.agent_id,
            agent_name=row.agent_name,
            total_searches=row.total_searches,
            unique_queries=row.unique_queries,
            avg_searches_per_day=avg_searches_per_day,
            avg_result_count=round(row.avg_result_count or 0, 2),
            ctr=ctr,
            last_search_at=row.last_search_at,
            favorite_queries=favorite_queries
        ))

    return user_behaviors


@router.get("/dashboard")
async def get_search_dashboard(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """获取搜索分析Dashboard数据（综合）"""
    trends = await get_search_trends(days=days, limit=10, db=db, current_agent=current_agent)
    quality = await get_search_quality(days=days, db=db, current_agent=current_agent)
    performance = await get_search_performance(period="day", db=db, current_agent=current_agent)
    zero_results = await get_zero_results_queries(days=days, limit=20, db=db, current_agent=current_agent)
    user_behavior = await get_user_search_behavior(days=days, limit=10, db=db, current_agent=current_agent)

    return {
        "period_days": days,
        "trends": trends,
        "quality": quality,
        "performance": performance,
        "zero_results": zero_results,
        "user_behavior": user_behavior
    }
