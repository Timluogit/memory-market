"""评估框架测试 - Evaluation Framework Tests"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from app.eval.metrics import EvaluationMetrics, MetricResult
from app.eval.datasets import DatasetManager, TestCase, TestDataset
from app.eval.runner import EvaluationRunner, EvaluationResult
from app.eval.report import EvaluationReport


# ═══════════════════════════════════════
# Metrics Tests
# ═══════════════════════════════════════

class TestMetrics:
    """评估指标测试"""

    def test_accuracy_perfect(self):
        result = EvaluationMetrics.accuracy({"a", "b", "c"}, {"a", "b", "c"})
        assert result.value == 1.0
        assert result.name == "accuracy"

    def test_accuracy_partial(self):
        result = EvaluationMetrics.accuracy({"a", "b"}, {"a", "b", "c"})
        # |{a,b} ∩ {a,b,c}| / |{a,b} ∪ {a,b,c}| = 2/3
        assert abs(result.value - 2/3) < 1e-6

    def test_accuracy_empty(self):
        result = EvaluationMetrics.accuracy(set(), set())
        assert result.value == 1.0

    def test_accuracy_no_overlap(self):
        result = EvaluationMetrics.accuracy({"a"}, {"b"})
        assert result.value == 0.0

    def test_precision(self):
        result = EvaluationMetrics.precision({"a", "b", "c"}, {"a", "b"})
        assert abs(result.value - 2/3) < 1e-6

    def test_precision_empty_predicted(self):
        result = EvaluationMetrics.precision(set(), {"a", "b"})
        assert result.value == 0.0

    def test_recall(self):
        result = EvaluationMetrics.recall({"a", "b"}, {"a", "b", "c"})
        assert abs(result.value - 2/3) < 1e-6

    def test_recall_empty_expected(self):
        result = EvaluationMetrics.recall({"a", "b"}, set())
        assert result.value == 1.0

    def test_f1_score(self):
        predicted = {"a", "b", "c"}
        expected = {"a", "b", "d"}
        result = EvaluationMetrics.f1_score(predicted, expected)
        # p=2/3, r=2/3, f1=2/3
        assert abs(result.value - 2/3) < 1e-6

    def test_f1_no_overlap(self):
        result = EvaluationMetrics.f1_score({"a"}, {"b"})
        assert result.value == 0.0

    def test_mrr_first(self):
        result = EvaluationMetrics.mrr(["a", "b", "c"], {"a"})
        assert result.value == 1.0

    def test_mrr_second(self):
        result = EvaluationMetrics.mrr(["x", "a", "b"], {"a"})
        assert result.value == 0.5

    def test_mrr_not_found(self):
        result = EvaluationMetrics.mrr(["x", "y", "z"], {"a"})
        assert result.value == 0.0

    def test_mrr_with_k(self):
        result = EvaluationMetrics.mrr(["x", "a"], {"a"}, k=1)
        assert result.value == 0.0  # a不在前1个中

    def test_ndcg_perfect(self):
        result = EvaluationMetrics.ndcg(["a", "b"], {"a", "b"})
        assert result.value == 1.0

    def test_ndcg_worst(self):
        result = EvaluationMetrics.ndcg(["x", "y"], {"a", "b"})
        assert result.value == 0.0

    def test_ndcg_partial(self):
        result = EvaluationMetrics.ndcg(["a", "x", "b"], {"a", "b"})
        assert 0 < result.value < 1.0

    def test_evaluate_retrieval(self):
        results = EvaluationMetrics.evaluate_retrieval(
            ["a", "b", "c"], {"a", "b"}, k=10
        )
        assert "accuracy" in results
        assert "precision" in results
        assert "recall" in results
        assert "f1" in results
        assert "mrr" in results
        assert "ndcg" in results

    def test_aggregate_results(self):
        m1 = MetricResult("f1", 0.8, "F1")
        m2 = MetricResult("f1", 0.6, "F1")
        result = EvaluationMetrics.aggregate_results([m1, m2])
        assert result.value == 0.7
        assert result.details["min"] == 0.6
        assert result.details["max"] == 0.8


# ═══════════════════════════════════════
# Dataset Tests
# ═══════════════════════════════════════

class TestDatasets:
    """数据集管理测试"""

    @pytest.fixture
    def tmp_dir(self):
        d = Path(tempfile.mkdtemp())
        yield d
        shutil.rmtree(d)

    @pytest.fixture
    def manager(self, tmp_dir):
        return DatasetManager(data_dir=tmp_dir)

    def test_create_dataset(self, manager):
        ds = manager.create_dataset("test_ds", "描述")
        assert ds.name == "test_ds"
        assert ds.size == 0

    def test_add_case(self, manager):
        ds = manager.create_dataset("test")
        case = TestCase(query="test query", expected_ids={"mem1"})
        added = manager.add_test_case(ds.id, case)
        assert added is not None
        assert manager.get_dataset(ds.id).size == 1

    def test_list_datasets(self, manager):
        manager.create_dataset("ds1")
        manager.create_dataset("ds2")
        datasets = manager.list_datasets()
        assert len(datasets) == 2

    def test_delete_dataset(self, manager):
        ds = manager.create_dataset("to_delete")
        assert manager.delete_dataset(ds.id) is True
        assert manager.get_dataset(ds.id) is None

    def test_dataset_filter_by_category(self, manager):
        ds = manager.create_dataset("test")
        ds.add_case(TestCase(query="q1", category="tech"))
        ds.add_case(TestCase(query="q2", category="general"))
        filtered = ds.filter_by_category("tech")
        assert len(filtered) == 1

    def test_dataset_filter_by_tags(self, manager):
        ds = manager.create_dataset("test")
        ds.add_case(TestCase(query="q1", tags=["ai", "nlp"]))
        ds.add_case(TestCase(query="q2", tags=["web"]))
        filtered = ds.filter_by_tags(["ai"])
        assert len(filtered) == 1

    def test_to_dict_roundtrip(self, manager):
        ds = manager.create_dataset("test", "desc", "1.0")
        ds.add_case(TestCase(query="q", expected_ids={"a"}, category="c"))
        d = ds.to_dict()
        restored = TestDataset.from_dict(d)
        assert restored.name == "test"
        assert restored.size == 1

    def test_generate_from_memories(self, manager):
        memories = [
            {"id": "m1", "content": "Python is a programming language", "category": "tech"},
            {"id": "m2", "content": "Machine learning uses data", "category": "tech"},
        ]
        ds = manager.generate_from_memories(memories, name="auto", num_cases=2)
        assert ds.size > 0

    def test_generate_synthetic(self, manager):
        templates = [{
            "query_template": "What is {topic}?",
            "topics": ["AI", "ML"],
            "keywords": ["artificial", "intelligence"],
            "category": "tech",
        }]
        ds = manager.generate_synthetic(templates, name="syn", num_cases=5)
        assert ds.size == 5


# ═══════════════════════════════════════
# Runner Tests
# ═══════════════════════════════════════

class TestRunner:
    """评估执行器测试"""

    @pytest.fixture
    def tmp_dir(self):
        d = Path(tempfile.mkdtemp())
        # 设置环境变量使 runner 使用临时目录
        import os
        old = os.environ.get("EVAL_DATA_DIR")
        os.environ["EVAL_DATA_DIR"] = str(d)
        yield d
        if old:
            os.environ["EVAL_DATA_DIR"] = old
        else:
            os.environ.pop("EVAL_DATA_DIR", None)
        shutil.rmtree(d)

    @pytest.fixture
    def setup(self, tmp_dir):
        import os
        os.environ["EVAL_DATA_DIR"] = str(tmp_dir)
        dm = DatasetManager(data_dir=tmp_dir)
        ds = dm.create_dataset("test_eval")
        ds.add_case(TestCase(
            query="python programming",
            expected_ids={"mem1", "mem2"},
            expected_keywords={"python", "programming"},
        ))
        ds.add_case(TestCase(
            query="machine learning",
            expected_ids={"mem3"},
            expected_keywords={"learning", "data"},
        ))
        runner = EvaluationRunner(dm)
        return runner, ds

    @pytest.mark.asyncio
    async def test_run_evaluation(self, setup):
        runner, ds = setup

        async def mock_search(query: str):
            if "python" in query:
                return [
                    {"id": "mem1", "content": "python programming tutorial"},
                    {"id": "mem2", "content": "python basics"},
                    {"id": "other", "content": "unrelated"},
                ]
            else:
                return [
                    {"id": "mem3", "content": "machine learning data"},
                    {"id": "other", "content": "unrelated"},
                ]

        result = await runner.run(
            dataset_id=ds.id,
            search_func=mock_search,
            run_name="test_run",
            k=10,
            parallel=2,
        )

        assert result.status == "completed"
        assert result.total_cases == 2
        assert result.completed_cases == 2
        assert result.failed_cases == 0
        assert "precision" in result.aggregated_metrics
        assert "recall" in result.aggregated_metrics
        assert "f1" in result.aggregated_metrics
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_run_with_failure(self, setup):
        runner, ds = setup

        async def failing_search(query: str):
            raise RuntimeError("search failed")

        result = await runner.run(
            dataset_id=ds.id,
            search_func=failing_search,
            run_name="fail_run",
            k=10,
            parallel=1,
        )

        assert result.status == "completed"
        assert result.failed_cases == 2

    def test_compare_results(self, setup):
        runner, ds = setup
        # 创建两个模拟结果
        from app.eval.runner import CaseResult
        r1 = EvaluationResult(
            id="r1", run_name="run1", dataset_id=ds.id,
            aggregated_metrics={"precision": 0.8, "recall": 0.7},
        )
        r2 = EvaluationResult(
            id="r2", run_name="run2", dataset_id=ds.id,
            aggregated_metrics={"precision": 0.9, "recall": 0.6},
        )
        runner._results["r1"] = r1
        runner._results["r2"] = r2

        comparison = runner.compare_results(["r1", "r2"])
        assert "metrics_comparison" in comparison
        assert "best_by_metric" in comparison


# ═══════════════════════════════════════
# Report Tests
# ═══════════════════════════════════════

class TestReport:
    """评估报告测试"""

    @pytest.fixture
    def sample_result(self):
        from app.eval.runner import CaseResult
        return EvaluationResult(
            id="test123",
            run_name="sample_run",
            dataset_id="ds1",
            dataset_name="Sample Dataset",
            status="completed",
            total_cases=10,
            completed_cases=10,
            failed_cases=0,
            aggregated_metrics={
                "accuracy": 0.85, "precision": 0.90,
                "recall": 0.80, "f1": 0.847,
                "mrr": 0.95, "ndcg": 0.88,
            },
            case_results=[
                CaseResult(case_id="c1", query="q1",
                          predicted_ids=["a"], predicted_ranked=["a"],
                          metrics={}, latency_ms=50.0),
            ],
            duration_seconds=2.5,
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:00:02",
        )

    def test_markdown_report(self, sample_result):
        report = EvaluationReport.to_markdown(sample_result)
        assert "sample_run" in report
        assert "准确率" in report
        assert "0.8500" in report

    def test_json_report(self, sample_result):
        report = EvaluationReport.to_json(sample_result)
        assert report["run_name"] == "sample_run"
        assert "aggregated_metrics" in report

    def test_html_report(self, sample_result):
        report = EvaluationReport.to_html(sample_result)
        assert "<html" in report
        assert "sample_run" in report

    def test_compare_markdown(self, sample_result):
        r2 = EvaluationResult(
            id="r2", run_name="run2", dataset_id="ds1",
            aggregated_metrics={"precision": 0.95, "recall": 0.75},
        )
        report = EvaluationReport.compare_markdown([sample_result, r2])
        assert "对比" in report
        assert "run2" in report


# ═══════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════

class TestIntegration:
    """集成测试"""

    @pytest.fixture
    def tmp_dir(self):
        d = Path(tempfile.mkdtemp())
        import os
        os.environ["EVAL_DATA_DIR"] = str(d)
        yield d
        os.environ.pop("EVAL_DATA_DIR", None)
        shutil.rmtree(d)

    @pytest.mark.asyncio
    async def test_full_pipeline(self, tmp_dir):
        """完整评估流程测试"""
        import os
        os.environ["EVAL_DATA_DIR"] = str(tmp_dir)

        # 1. 创建数据集
        dm = DatasetManager(data_dir=tmp_dir)
        ds = dm.create_dataset("full_test", "完整测试")

        # 2. 添加测试用例
        for i in range(5):
            ds.add_case(TestCase(
                query=f"test query {i}",
                expected_ids={f"mem_{i}"},
                expected_keywords={f"keyword_{i}"},
            ))

        # 3. 运行评估
        runner = EvaluationRunner(dm)

        async def mock_search(query: str):
            idx = query.split()[-1]
            return [
                {"id": f"mem_{idx}", "content": f"result for {query}"},
                {"id": "other", "content": "unrelated"},
            ]

        result = await runner.run(
            dataset_id=ds.id,
            search_func=mock_search,
            run_name="full_pipeline",
            parallel=2,
        )

        assert result.status == "completed"
        assert result.total_cases == 5

        # 4. 生成报告
        md_report = EvaluationReport.to_markdown(result)
        assert "full_pipeline" in md_report

        json_report = EvaluationReport.to_json(result)
        assert json_report["status"] == "completed"

        # 5. 验证结果持久化
        retrieved = runner.get_result(result.id)
        assert retrieved is not None
        assert retrieved.id == result.id
