"""A/B测试API - 管理搜索算法对比实验"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_agent, require_admin
from app.models.tables import Agent
from app.models.schemas import ABTestCreate, ABTestResponse, ABTestList, ABTestResult
from app.services.ab_test_service import get_ab_test_service

router = APIRouter(prefix="/ab-tests", tags=["ab-tests"])


@router.post("", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test(
    test_config: ABTestCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """创建A/B测试"""
    ab_test_service = await get_ab_test_service()

    try:
        test = await ab_test_service.create_test(db, current_agent.agent_id, test_config)

        # 获取创建者名称
        return ABTestResponse(
            test_id=test.test_id,
            name=test.name,
            description=test.description,
            created_by_agent_id=test.created_by_agent_id,
            created_by_name=current_agent.name,
            test_type=test.test_type,
            start_at=test.start_at,
            end_at=test.end_at,
            split_ratio=test.split_ratio,
            group_configs=test.group_configs,
            metrics=test.metrics,
            total_searches=test.total_searches,
            group_stats=test.group_stats,
            results=test.results,
            significance=test.significance,
            winner=test.winner,
            status=test.status,
            created_at=test.created_at,
            updated_at=test.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ABTestList)
async def list_ab_tests(
    status_filter: Optional[str] = Query(None, description="状态筛选: draft/running/completed/cancelled"),
    mine_only: bool = Query(False, description="只显示我创建的测试"),
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent)
):
    """查询A/B测试列表"""
    ab_test_service = await get_ab_test_service()

    tests = await ab_test_service.list_tests(
        db,
        status=status_filter,
        created_by_agent_id=current_agent.agent_id if mine_only else None
    )

    # 获取创建者名称
    responses = []
    for test in tests:
        # 获取创建者信息
        from sqlalchemy import select
        creator_result = await db.execute(
            select(Agent.name).where(Agent.agent_id == test.created_by_agent_id)
        )
        creator_name = creator_result.scalar() or "Unknown"

        responses.append(ABTestResponse(
            test_id=test.test_id,
            name=test.name,
            description=test.description,
            created_by_agent_id=test.created_by_agent_id,
            created_by_name=creator_name,
            test_type=test.test_type,
            start_at=test.start_at,
            end_at=test.end_at,
            split_ratio=test.split_ratio,
            group_configs=test.group_configs,
            metrics=test.metrics,
            total_searches=test.total_searches,
            group_stats=test.group_stats,
            results=test.results,
            significance=test.significance,
            winner=test.winner,
            status=test.status,
            created_at=test.created_at,
            updated_at=test.updated_at
        ))

    return ABTestList(items=responses, total=len(responses))


@router.get("/{test_id}", response_model=ABTestResponse)
async def get_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent)
):
    """获取A/B测试详情"""
    ab_test_service = await get_ab_test_service()

    test = await ab_test_service.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")

    # 获取创建者名称
    creator_result = await db.execute(
        select(Agent.name).where(Agent.agent_id == test.created_by_agent_id)
    )
    creator_name = creator_result.scalar() or "Unknown"

    return ABTestResponse(
        test_id=test.test_id,
        name=test.name,
        description=test.description,
        created_by_agent_id=test.created_by_agent_id,
        created_by_name=creator_name,
        test_type=test.test_type,
        start_at=test.start_at,
        end_at=test.end_at,
        split_ratio=test.split_ratio,
        group_configs=test.group_configs,
        metrics=test.metrics,
        total_searches=test.total_searches,
        group_stats=test.group_stats,
        results=test.results,
        significance=test.significance,
        winner=test.winner,
        status=test.status,
        created_at=test.created_at,
        updated_at=test.updated_at
    )


@router.post("/{test_id}/start", response_model=ABTestResponse)
async def start_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """启动A/B测试"""
    ab_test_service = await get_ab_test_service()

    try:
        test = await ab_test_service.start_test(db, test_id)

        # 获取创建者名称
        creator_result = await db.execute(
            select(Agent.name).where(Agent.agent_id == test.created_by_agent_id)
        )
        creator_name = creator_result.scalar() or "Unknown"

        return ABTestResponse(
            test_id=test.test_id,
            name=test.name,
            description=test.description,
            created_by_agent_id=test.created_by_agent_id,
            created_by_name=creator_name,
            test_type=test.test_type,
            start_at=test.start_at,
            end_at=test.end_at,
            split_ratio=test.split_ratio,
            group_configs=test.group_configs,
            metrics=test.metrics,
            total_searches=test.total_searches,
            group_stats=test.group_stats,
            results=test.results,
            significance=test.significance,
            winner=test.winner,
            status=test.status,
            created_at=test.created_at,
            updated_at=test.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{test_id}/stop", response_model=ABTestResponse)
async def stop_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """停止A/B测试"""
    ab_test_service = await get_ab_test_service()

    try:
        test = await ab_test_service.stop_test(db, test_id)

        # 获取创建者名称
        creator_result = await db.execute(
            select(Agent.name).where(Agent.agent_id == test.created_by_agent_id)
        )
        creator_name = creator_result.scalar() or "Unknown"

        return ABTestResponse(
            test_id=test.test_id,
            name=test.name,
            description=test.description,
            created_by_agent_id=test.created_by_agent_id,
            created_by_name=creator_name,
            test_type=test.test_type,
            start_at=test.start_at,
            end_at=test.end_at,
            split_ratio=test.split_ratio,
            group_configs=test.group_configs,
            metrics=test.metrics,
            total_searches=test.total_searches,
            group_stats=test.group_stats,
            results=test.results,
            significance=test.significance,
            winner=test.winner,
            status=test.status,
            created_at=test.created_at,
            updated_at=test.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{test_id}/cancel", response_model=ABTestResponse)
async def cancel_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent)
):
    """取消A/B测试"""
    ab_test_service = await get_ab_test_service()

    try:
        test = await ab_test_service.cancel_test(db, test_id)

        # 获取创建者名称
        creator_result = await db.execute(
            select(Agent.name).where(Agent.agent_id == test.created_by_agent_id)
        )
        creator_name = creator_result.scalar() or "Unknown"

        return ABTestResponse(
            test_id=test.test_id,
            name=test.name,
            description=test.description,
            created_by_agent_id=test.created_by_agent_id,
            created_by_name=creator_name,
            test_type=test.test_type,
            start_at=test.start_at,
            end_at=test.end_at,
            split_ratio=test.split_ratio,
            group_configs=test.group_configs,
            metrics=test.metrics,
            total_searches=test.total_searches,
            group_stats=test.group_stats,
            results=test.results,
            significance=test.significance,
            winner=test.winner,
            status=test.status,
            created_at=test.created_at,
            updated_at=test.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent)
):
    """删除A/B测试"""
    ab_test_service = await get_ab_test_service()

    try:
        success = await ab_test_service.delete_test(db, test_id)
        if not success:
            raise HTTPException(status_code=404, detail="A/B test not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{test_id}/report", response_model=ABTestResult)
async def generate_ab_test_report(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(require_admin)
):
    """生成A/B测试报告"""
    ab_test_service = await get_ab_test_service()

    try:
        return await ab_test_service.analyze_results(db, test_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{test_id}/results", response_model=ABTestResult)
async def get_ab_test_results(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent)
):
    """获取A/B测试结果"""
    ab_test_service = await get_ab_test_service()

    test = await ab_test_service.get_test(db, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")

    # 如果测试已经完成，返回已分析的结果
    if test.results:
        return ABTestResult(
            test_id=test.test_id,
            name=test.name,
            status=test.status,
            group_stats=[
                {
                    "group": group,
                    **stats
                }
                for group, stats in test.group_stats.items()
            ],
            metrics_comparison=test.results,
            significance=test.significance,
            winner=test.winner,
            recommendation=""
        )

    # 否则生成新的分析
    try:
        return await ab_test_service.analyze_results(db, test_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
