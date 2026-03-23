"""评估API - Evaluation Endpoints

- POST /api/eval/run          运行评估
- GET  /api/eval/results/{id} 获取结果
- GET  /api/eval/compare       对比结果
- GET  /api/eval/datasets      列出数据集
- POST /api/eval/datasets      创建数据集
- POST /api/eval/datasets/{id}/cases  添加测试用例
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncio

from app.eval.datasets import DatasetManager, TestCase, TestDataset
from app.eval.runner import EvaluationRunner, EvaluationResult
from app.eval.report import EvaluationReport

router = APIRouter(prefix="/api/eval", tags=["Evaluation"])

# 全局实例
_dataset_manager = DatasetManager()
_runner = EvaluationRunner(_dataset_manager)


# ── Schemas ──

class TestCaseCreate(BaseModel):
    query: str
    expected_ids: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    category: str = "general"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    test_cases: List[TestCaseCreate] = Field(default_factory=list)


class EvalRunRequest(BaseModel):
    dataset_id: str
    run_name: str = ""
    k: int = 10
    parallel: int = 4
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    # 搜索模式: "memory_search" 或自定义 callback URL
    search_mode: str = "memory_search"
    search_query_field: str = "query"
    agent_id: Optional[str] = None


class CompareRequest(BaseModel):
    result_ids: List[str]


# ── 数据集 API ──

@router.get("/datasets", summary="列出所有测试数据集")
async def list_datasets():
    return {"success": True, "data": _dataset_manager.list_datasets()}


@router.post("/datasets", summary="创建测试数据集")
async def create_dataset(req: DatasetCreate):
    ds = _dataset_manager.create_dataset(req.name, req.description, req.version)
    for tc in req.test_cases:
        case = TestCase(
            query=tc.query,
            expected_ids=set(tc.expected_ids),
            expected_keywords=set(tc.expected_keywords),
            category=tc.category,
            tags=tc.tags,
            metadata=tc.metadata,
        )
        _dataset_manager.add_test_case(ds.id, case)
    return {"success": True, "data": ds.to_dict()}


@router.get("/datasets/{dataset_id}", summary="获取数据集详情")
async def get_dataset(dataset_id: str):
    ds = _dataset_manager.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"数据集不存在: {dataset_id}")
    return {"success": True, "data": ds.to_dict()}


@router.delete("/datasets/{dataset_id}", summary="删除数据集")
async def delete_dataset(dataset_id: str):
    ok = _dataset_manager.delete_dataset(dataset_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"数据集不存在: {dataset_id}")
    return {"success": True, "message": "已删除"}


@router.post("/datasets/{dataset_id}/cases", summary="添加测试用例")
async def add_test_case(dataset_id: str, req: TestCaseCreate):
    case = TestCase(
        query=req.query,
        expected_ids=set(req.expected_ids),
        expected_keywords=set(req.expected_keywords),
        category=req.category,
        tags=req.tags,
        metadata=req.metadata,
    )
    added = _dataset_manager.add_test_case(dataset_id, case)
    if not added:
        raise HTTPException(status_code=404, detail=f"数据集不存在: {dataset_id}")
    return {"success": True, "data": added.to_dict()}


# ── 评估运行 API ──

@router.post("/run", summary="运行评估")
async def run_evaluation(req: EvalRunRequest):
    """运行评估任务。支持 memory_search 模式和自定义搜索模式。"""

    async def search_func(query: str) -> List[Dict[str, Any]]:
        """内存搜索回调 - 集成现有搜索系统"""
        if req.search_mode == "memory_search":
            return await _memory_search(query, agent_id=req.agent_id, k=req.k)
        else:
            # 未来可扩展: 通过 HTTP callback 调用外部搜索
            return await _memory_search(query, agent_id=req.agent_id, k=req.k)

    try:
        result = await _runner.run(
            dataset_id=req.dataset_id,
            search_func=search_func,
            run_name=req.run_name,
            k=req.k,
            parallel=req.parallel,
            categories=req.categories,
            tags=req.tags,
            config=req.config,
        )
        return {"success": True, "data": result.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _memory_search(query: str, agent_id: Optional[str] = None,
                          k: int = 10) -> List[Dict[str, Any]]:
    """集成现有记忆搜索系统"""
    try:
        from app.services.memory_service import search_memories
        from app.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            results = await search_memories(
                db, query=query, agent_id=agent_id or "eval_agent",
                limit=k, use_semantic=True
            )
            return [
                {
                    "id": str(r.get("id", r.get("memory_id", ""))),
                    "content": r.get("content", r.get("text", "")),
                    "score": r.get("score", r.get("similarity", 0)),
                }
                for r in results
            ]
    except Exception:
        # 降级: 返回空结果
        return []


# ── 结果查询 API ──

@router.get("/results/{result_id}", summary="获取评估结果")
async def get_result(result_id: str):
    result = _runner.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"结果不存在: {result_id}")
    return {"success": True, "data": result.to_dict()}


@router.get("/results", summary="列出评估结果")
async def list_results(
    dataset_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    return {"success": True, "data": _runner.list_results(dataset_id, limit)}


@router.get("/results/{result_id}/report", summary="获取评估报告")
async def get_report(result_id: str, format: str = Query("markdown")):
    result = _runner.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"结果不存在: {result_id}")

    if format == "json":
        return {"success": True, "data": EvaluationReport.to_json(result)}
    elif format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=EvaluationReport.to_html(result))
    else:
        return {"success": True, "report": EvaluationReport.to_markdown(result)}


# ── 对比 API ──

@router.get("/compare", summary="对比评估结果")
async def compare_results(
    ids: str = Query(..., description="逗号分隔的评估结果ID"),
):
    result_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if len(result_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个结果ID进行对比")

    comparison = _runner.compare_results(result_ids)
    if "error" in comparison:
        raise HTTPException(status_code=404, detail=comparison["error"])

    # 生成对比报告
    results = [_runner.get_result(rid) for rid in result_ids]
    results = [r for r in results if r is not None]
    report = EvaluationReport.compare_markdown(results)

    return {"success": True, "data": comparison, "report": report}
