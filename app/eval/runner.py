"""评估执行器 - Evaluation Runner

支持:
- 同步/异步评估执行
- 并行执行
- 结果收集与聚合
- 执行历史管理
"""
from __future__ import annotations
import asyncio
import json
import time
import uuid
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable, Awaitable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.eval.metrics import EvaluationMetrics, MetricResult
from app.eval.datasets import TestCase, TestDataset, DatasetManager


DATA_DIR = Path(os.getenv("EVAL_DATA_DIR", "./data/evaluation"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CaseResult:
    """单个测试用例结果"""
    case_id: str
    query: str
    predicted_ids: List[str]
    predicted_ranked: List[str]
    metrics: Dict[str, float]
    latency_ms: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    """评估结果"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    dataset_id: str = ""
    dataset_name: str = ""
    run_name: str = ""
    status: str = "pending"  # pending | running | completed | failed
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    aggregated_metrics: Dict[str, float] = field(default_factory=dict)
    case_results: List[CaseResult] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.completed_cases / self.total_cases

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "run_name": self.run_name,
            "status": self.status,
            "total_cases": self.total_cases,
            "completed_cases": self.completed_cases,
            "failed_cases": self.failed_cases,
            "success_rate": round(self.success_rate, 4),
            "aggregated_metrics": {k: round(v, 6) for k, v in self.aggregated_metrics.items()},
            "case_results": [r.to_dict() for r in self.case_results],
            "config": self.config,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 3),
        }
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationResult":
        crs = [CaseResult(**cr) for cr in data.get("case_results", [])]
        return cls(
            id=data.get("id", ""),
            dataset_id=data.get("dataset_id", ""),
            dataset_name=data.get("dataset_name", ""),
            run_name=data.get("run_name", ""),
            status=data.get("status", "pending"),
            total_cases=data.get("total_cases", 0),
            completed_cases=data.get("completed_cases", 0),
            failed_cases=data.get("failed_cases", 0),
            aggregated_metrics=data.get("aggregated_metrics", {}),
            case_results=crs,
            config=data.get("config", {}),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds", 0.0),
        )


# 搜索回调类型
SearchFunc = Callable[[str], Awaitable[List[Dict[str, Any]]]]


class EvaluationRunner:
    """评估执行器"""

    def __init__(self, dataset_manager: Optional[DatasetManager] = None):
        self.dataset_manager = dataset_manager or DatasetManager()
        self._results: Dict[str, EvaluationResult] = {}
        self._load_results()

    # ── 持久化 ──

    def _load_results(self) -> None:
        for fp in DATA_DIR.glob("result_*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                r = EvaluationResult.from_dict(data)
                self._results[r.id] = r
            except Exception:
                continue

    def _save_result(self, result: EvaluationResult) -> None:
        fp = DATA_DIR / f"result_{result.id}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    # ── 执行 ──

    async def run(
        self,
        dataset_id: str,
        search_func: SearchFunc,
        run_name: str = "",
        k: int = 10,
        parallel: int = 4,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """运行评估

        Args:
            dataset_id: 数据集ID
            search_func: 搜索函数 callback(query) -> List[{id, score, ...}]
            run_name: 运行名称
            k: 取前k个结果计算指标
            parallel: 并行度
            categories: 按类别过滤
            tags: 按标签过滤
            config: 额外配置
        """
        ds = self.dataset_manager.get_dataset(dataset_id)
        if not ds:
            raise ValueError(f"数据集不存在: {dataset_id}")

        # 过滤测试用例
        cases = ds.test_cases
        if categories:
            cases = [c for c in cases if c.category in categories]
        if tags:
            tag_set = set(tags)
            cases = [c for c in cases if tag_set & set(c.tags)]

        result = EvaluationResult(
            dataset_id=dataset_id,
            dataset_name=ds.name,
            run_name=run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            total_cases=len(cases),
            config={"k": k, "parallel": parallel, **(config or {})},
            started_at=datetime.now().isoformat(),
            status="running",
        )
        self._results[result.id] = result

        # 并行执行
        semaphore = asyncio.Semaphore(parallel)

        async def run_single(case: TestCase) -> CaseResult:
            async with semaphore:
                return await self._eval_case(case, search_func, k)

        tasks = [run_single(c) for c in cases]
        case_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        all_metrics: Dict[str, List[float]] = {}
        for cr in case_results:
            if isinstance(cr, Exception):
                result.failed_cases += 1
                result.case_results.append(CaseResult(
                    case_id="error", query="", predicted_ids=[], predicted_ranked=[],
                    metrics={}, latency_ms=0, error=str(cr),
                ))
            else:
                result.completed_cases += 1
                result.case_results.append(cr)
                for name, val in cr.metrics.items():
                    all_metrics.setdefault(name, []).append(val)

        # 聚合指标
        result.aggregated_metrics = {
            name: round(sum(vals) / len(vals), 6)
            for name, vals in all_metrics.items()
        }
        result.status = "completed"
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = (
            datetime.fromisoformat(result.completed_at) -
            datetime.fromisoformat(result.started_at)
        ).total_seconds()

        self._save_result(result)
        return result

    async def _eval_case(
        self, case: TestCase, search_func: SearchFunc, k: int,
    ) -> CaseResult:
        """执行单个测试用例"""
        start = time.time()
        try:
            raw_results = await search_func(case.query)
            latency = (time.time() - start) * 1000

            predicted_ranked = [r.get("id", "") for r in raw_results[:k]]
            predicted_set = set(predicted_ranked)

            # 使用ID匹配或关键词匹配
            expected = case.expected_ids
            if not expected and case.expected_keywords:
                # 关键词匹配：检查预测内容中是否包含期望关键词
                expected = case.expected_keywords
                predicted_set = set()
                for r in raw_results[:k]:
                    content = r.get("content", r.get("text", ""))
                    words = set(content.lower().split())
                    if words & expected:
                        predicted_set.add(r.get("id", content[:20]))
                predicted_ranked = list(predicted_set)

            metrics = EvaluationMetrics.evaluate_retrieval(
                predicted_ranked, expected, k
            )

            return CaseResult(
                case_id=case.id,
                query=case.query,
                predicted_ids=list(predicted_set),
                predicted_ranked=predicted_ranked,
                metrics={name: m.value for name, m in metrics.items()},
                latency_ms=round(latency, 2),
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return CaseResult(
                case_id=case.id,
                query=case.query,
                predicted_ids=[],
                predicted_ranked=[],
                metrics={},
                latency_ms=round(latency, 2),
                error=str(e),
            )

    # ── 结果查询 ──

    def get_result(self, result_id: str) -> Optional[EvaluationResult]:
        return self._results.get(result_id)

    def list_results(
        self, dataset_id: Optional[str] = None, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = list(self._results.values())
        if dataset_id:
            results = [r for r in results if r.dataset_id == dataset_id]
        results.sort(key=lambda r: r.started_at or "", reverse=True)
        return [
            {"id": r.id, "run_name": r.run_name, "dataset_id": r.dataset_id,
             "dataset_name": r.dataset_name, "status": r.status,
             "total_cases": r.total_cases, "completed_cases": r.completed_cases,
             "aggregated_metrics": r.aggregated_metrics,
             "duration_seconds": r.duration_seconds,
             "started_at": r.started_at}
            for r in results[:limit]
        ]

    def compare_results(self, result_ids: List[str]) -> Dict[str, Any]:
        """对比多个评估结果"""
        results = [self._results[rid] for rid in result_ids if rid in self._results]
        if not results:
            return {"error": "未找到评估结果", "result_ids": result_ids}

        comparison = {
            "result_ids": [r.id for r in results],
            "run_names": [r.run_name for r in results],
            "metrics_comparison": {},
            "best_by_metric": {},
        }

        # 收集所有指标
        all_metric_names = set()
        for r in results:
            all_metric_names.update(r.aggregated_metrics.keys())

        for metric_name in all_metric_names:
            values = []
            for r in results:
                val = r.aggregated_metrics.get(metric_name, 0.0)
                values.append({"run_name": r.run_name, "value": val})
            comparison["metrics_comparison"][metric_name] = values
            if values:
                best = max(values, key=lambda x: x["value"])
                comparison["best_by_metric"][metric_name] = best

        return comparison
