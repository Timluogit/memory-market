"""A/B测试服务 - 支持搜索算法对比和分流"""
import hashlib
import random
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, update
from sqlalchemy.orm import selectinload

from app.models.tables import SearchABTest, SearchLog, SearchClick, Agent
from app.models.schemas import ABTestCreate, ABTestResponse, ABTestResult

logger = logging.getLogger(__name__)


class ABTestService:
    """A/B测试服务

    支持搜索算法对比实验，自动分流用户，收集结果并生成报告
    """

    def __init__(self):
        pass

    async def create_test(
        self,
        db: AsyncSession,
        created_by_agent_id: str,
        test_config: ABTestCreate
    ) -> SearchABTest:
        """创建A/B测试

        Args:
            db: 数据库会话
            created_by_agent_id: 创建者ID
            test_config: 测试配置

        Returns:
            A/B测试对象
        """
        # 验证split_ratio
        total_ratio = sum(test_config.split_ratio.values())
        if abs(total_ratio - 1.0) > 0.01:
            raise ValueError("Split ratio must sum to 1.0")

        # 验证时间范围
        if test_config.start_at >= test_config.end_at:
            raise ValueError("End time must be after start time")

        if test_config.start_at < datetime.utcnow():
            raise ValueError("Start time must be in the future")

        # 创建测试
        test = SearchABTest(
            name=test_config.name,
            description=test_config.description,
            created_by_agent_id=created_by_agent_id,
            test_type=test_config.test_type,
            start_at=test_config.start_at,
            end_at=test_config.end_at,
            split_ratio=test_config.split_ratio,
            group_configs=test_config.group_configs,
            metrics=test_config.metrics,
            total_searches=0,
            group_stats={},
            results=None,
            significance=None,
            winner=None,
            status="draft"
        )

        db.add(test)
        await db.commit()
        await db.refresh(test)

        logger.info(f"A/B test created: {test.test_id} - {test.name}")
        return test

    async def start_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> SearchABTest:
        """启动A/B测试"""
        test = await self._get_test(db, test_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        if test.status != "draft":
            raise ValueError(f"Cannot start test with status: {test.status}")

        test.status = "running"
        await db.commit()
        await db.refresh(test)

        logger.info(f"A/B test started: {test.test_id}")
        return test

    async def stop_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> SearchABTest:
        """停止A/B测试"""
        test = await self._get_test(db, test_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        if test.status not in ["running"]:
            raise ValueError(f"Cannot stop test with status: {test.status}")

        test.status = "completed"
        await db.commit()
        await db.refresh(test)

        logger.info(f"A/B test stopped: {test.test_id}")
        return test

    async def get_user_group(
        self,
        db: AsyncSession,
        test_id: str,
        agent_id: str
    ) -> Optional[str]:
        """获取用户所在的测试分组

        Args:
            db: 数据库会话
            test_id: 测试ID
            agent_id: 用户ID

        Returns:
            分组名称（如 "A", "B"）
        """
        test = await self._get_test(db, test_id)
        if not test or test.status != "running":
            return None

        # 根据agent_id哈希值分配组（确保同一用户始终在同一组）
        hash_val = int(hashlib.md5(f"{test.test_id}:{agent_id}".encode()).hexdigest(), 16)
        group_index = hash_val % 100  # 0-99

        # 根据split_ratio分配组
        cumulative = 0
        for group, ratio in test.split_ratio.items():
            cumulative += ratio * 100
            if group_index < cumulative:
                return group

        return None

    async def get_group_config(
        self,
        db: AsyncSession,
        test_id: str,
        group: str
    ) -> Optional[Dict]:
        """获取分组的配置"""
        test = await self._get_test(db, test_id)
        if not test:
            return None

        return test.group_configs.get(group)

    async def collect_results(
        self,
        db: AsyncSession,
        test_id: str
    ) -> Dict:
        """收集A/B测试结果

        Args:
            db: 数据库会话
            test_id: 测试ID

        Returns:
            分组统计数据
        """
        test = await self._get_test(db, test_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        # 统计每个分组的搜索数
        group_stats = {}
        for group in test.split_ratio.keys():
            # 搜索数
            searches_result = await db.execute(
                select(func.count(SearchLog.log_id))
                .where(
                    and_(
                        SearchLog.ab_test_id == test_id,
                        SearchLog.ab_test_group == group,
                        SearchLog.created_at >= test.start_at,
                        SearchLog.created_at <= test.end_at
                    )
                )
            )
            search_count = searches_result.scalar() or 0

            # 点击数
            clicks_result = await db.execute(
                select(func.count(SearchClick.click_id))
                .join(SearchLog, SearchClick.search_log_id == SearchLog.log_id)
                .where(
                    and_(
                        SearchLog.ab_test_id == test_id,
                        SearchLog.ab_test_group == group,
                        SearchClick.created_at >= test.start_at,
                        SearchClick.created_at <= test.end_at
                    )
                )
            )
            click_count = clicks_result.scalar() or 0

            # 平均结果数
            avg_result_count_result = await db.execute(
                select(func.avg(SearchLog.result_count))
                .where(
                    and_(
                        SearchLog.ab_test_id == test_id,
                        SearchLog.ab_test_group == group,
                        SearchLog.created_at >= test.start_at,
                        SearchLog.created_at <= test.end_at
                    )
                )
            )
            avg_result_count = avg_result_count_result.scalar() or 0

            # 平均响应时间
            avg_response_time_result = await db.execute(
                select(func.avg(SearchLog.response_time_ms))
                .where(
                    and_(
                        SearchLog.ab_test_id == test_id,
                        SearchLog.ab_test_group == group,
                        SearchLog.created_at >= test.start_at,
                        SearchLog.created_at <= test.end_at
                    )
                )
            )
            avg_response_time = avg_response_time_result.scalar() or 0

            # 零结果率
            zero_results_result = await db.execute(
                select(func.count(SearchLog.log_id))
                .where(
                    and_(
                        SearchLog.ab_test_id == test_id,
                        SearchLog.ab_test_group == group,
                        SearchLog.result_count == 0,
                        SearchLog.created_at >= test.start_at,
                        SearchLog.created_at <= test.end_at
                    )
                )
            )
            zero_results_count = zero_results_result.scalar() or 0
            zero_results_rate = round(zero_results_count / search_count * 100, 2) if search_count > 0 else 0

            # 点击率
            ctr = round(click_count / search_count * 100, 2) if search_count > 0 else 0

            group_stats[group] = {
                "searches": search_count,
                "clicks": click_count,
                "ctr": ctr,
                "avg_result_count": round(avg_result_count, 2),
                "avg_response_time_ms": round(avg_response_time, 2),
                "zero_results_rate": zero_results_rate
            }

        # 更新测试的统计数据
        test.group_stats = group_stats
        test.total_searches = sum(s["searches"] for s in group_stats.values())
        await db.commit()

        return group_stats

    async def analyze_results(
        self,
        db: AsyncSession,
        test_id: str
    ) -> ABTestResult:
        """分析A/B测试结果

        Args:
            db: 数据库会话
            test_id: 测试ID

        Returns:
            分析结果
        """
        test = await self._get_test(db, test_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        # 收集最新结果
        group_stats = await self.collect_results(db, test_id)

        # 指标对比
        metrics_comparison = {}
        for metric in test.metrics:
            if metric == "ctr":
                metrics_comparison["ctr"] = {
                    group: stats["ctr"]
                    for group, stats in group_stats.items()
                }
            elif metric == "zero_results_rate":
                metrics_comparison["zero_results_rate"] = {
                    group: stats["zero_results_rate"]
                    for group, stats in group_stats.items()
                }
            elif metric == "avg_response_time":
                metrics_comparison["avg_response_time_ms"] = {
                    group: stats["avg_response_time_ms"]
                    for group, stats in group_stats.items()
                }

        # 计算显著性（简化版，实际应使用统计检验）
        significance = None
        if len(group_stats) == 2:
            groups = list(group_stats.keys())
            # 简单的差异百分比作为"显著性"指标
            if "ctr" in metrics_comparison:
                ctr_diff = abs(metrics_comparison["ctr"][groups[0]] - metrics_comparison["ctr"][groups[1]])
                significance = round(ctr_diff, 2)

        # 确定获胜者（基于CTR）
        winner = None
        if "ctr" in metrics_comparison:
            max_ctr_group = max(metrics_comparison["ctr"].items(), key=lambda x: x[1])
            if max_ctr_group[1] > 0:
                winner = max_ctr_group[0]

        # 生成建议
        recommendation = "测试结果无明显差异"
        if winner:
            recommendation = f"建议采用 {winner} 分组的配置（CTR更高）"

        # 更新测试结果
        test.results = metrics_comparison
        test.significance = significance
        test.winner = winner
        await db.commit()

        # 返回结果
        return ABTestResult(
            test_id=test.test_id,
            name=test.name,
            status=test.status,
            group_stats=[
                {
                    "group": group,
                    **stats
                }
                for group, stats in group_stats.items()
            ],
            metrics_comparison=metrics_comparison,
            significance=significance,
            winner=winner,
            recommendation=recommendation
        )

    async def list_tests(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        created_by_agent_id: Optional[str] = None
    ) -> List[SearchABTest]:
        """查询A/B测试列表"""
        query = select(SearchABTest)

        if status:
            query = query.where(SearchABTest.status == status)

        if created_by_agent_id:
            query = query.where(SearchABTest.created_by_agent_id == created_by_agent_id)

        query = query.order_by(desc(SearchABTest.created_at))

        result = await db.execute(query)
        return result.scalars().all()

    async def get_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> Optional[SearchABTest]:
        """获取A/B测试详情"""
        return await self._get_test(db, test_id)

    async def delete_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> bool:
        """删除A/B测试"""
        test = await self._get_test(db, test_id)
        if not test:
            return False

        # 只能删除draft或cancelled状态的测试
        if test.status not in ["draft", "cancelled"]:
            raise ValueError(f"Cannot delete test with status: {test.status}")

        await db.delete(test)
        await db.commit()

        logger.info(f"A/B test deleted: {test.test_id}")
        return True

    async def cancel_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> SearchABTest:
        """取消A/B测试"""
        test = await self._get_test(db, test_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        if test.status not in ["draft", "running"]:
            raise ValueError(f"Cannot cancel test with status: {test.status}")

        test.status = "cancelled"
        await db.commit()
        await db.refresh(test)

        logger.info(f"A/B test cancelled: {test.test_id}")
        return test

    async def _get_test(
        self,
        db: AsyncSession,
        test_id: str
    ) -> Optional[SearchABTest]:
        """获取A/B测试"""
        result = await db.execute(
            select(SearchABTest)
            .where(SearchABTest.test_id == test_id)
        )
        return result.scalar_one_or_none()


# 全局实例
ab_test_service = ABTestService()


async def get_ab_test_service():
    """获取A/B测试服务实例"""
    return ab_test_service
