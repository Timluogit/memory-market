"""测试数据集管理 - Test Dataset Management

支持:
- 测试用例定义与管理
- 数据集加载 (JSON / JSONL / 内存)
- 数据集自动生成
- 数据集版本管理
"""
from __future__ import annotations
import json
import uuid
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Set
from pathlib import Path


DATA_DIR = Path(os.getenv("EVAL_DATA_DIR", "./data/evaluation"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TestCase:
    """单个测试用例"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str = ""
    expected_ids: Set[str] = field(default_factory=set)
    expected_keywords: Set[str] = field(default_factory=set)
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["expected_ids"] = list(self.expected_ids)
        d["expected_keywords"] = list(self.expected_keywords)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCase":
        data = dict(data)
        data["expected_ids"] = set(data.get("expected_ids", []))
        data["expected_keywords"] = set(data.get("expected_keywords", []))
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class TestDataset:
    """测试数据集"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    version: str = "1.0"
    test_cases: List[TestCase] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_case(self, case: TestCase) -> None:
        self.test_cases.append(case)
        self.updated_at = datetime.now().isoformat()

    def remove_case(self, case_id: str) -> bool:
        before = len(self.test_cases)
        self.test_cases = [c for c in self.test_cases if c.id != case_id]
        if len(self.test_cases) < before:
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    @property
    def size(self) -> int:
        return len(self.test_cases)

    @property
    def categories(self) -> List[str]:
        return list(set(c.category for c in self.test_cases))

    def filter_by_category(self, category: str) -> List[TestCase]:
        return [c for c in self.test_cases if c.category == category]

    def filter_by_tags(self, tags: List[str]) -> List[TestCase]:
        tag_set = set(tags)
        return [c for c in self.test_cases if tag_set & set(c.tags)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "size": self.size,
            "categories": self.categories,
            "test_cases": [c.to_dict() for c in self.test_cases],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestDataset":
        cases = [TestCase.from_dict(c) for c in data.get("test_cases", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            test_cases=cases,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class DatasetManager:
    """数据集管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._datasets: Dict[str, TestDataset] = {}
        self._load_all()

    # ── 持久化 ──

    def _load_all(self) -> None:
        for fp in self.data_dir.glob("dataset_*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ds = TestDataset.from_dict(data)
                self._datasets[ds.id] = ds
            except Exception:
                continue

    def _save(self, dataset: TestDataset) -> None:
        fp = self.data_dir / f"dataset_{dataset.id}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(dataset.to_dict(), f, ensure_ascii=False, indent=2)

    # ── CRUD ──

    def create_dataset(self, name: str, description: str = "",
                       version: str = "1.0") -> TestDataset:
        ds = TestDataset(name=name, description=description, version=version)
        self._datasets[ds.id] = ds
        self._save(ds)
        return ds

    def get_dataset(self, dataset_id: str) -> Optional[TestDataset]:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[Dict[str, Any]]:
        return [
            {"id": ds.id, "name": ds.name, "description": ds.description,
             "version": ds.version, "size": ds.size,
             "categories": ds.categories, "created_at": ds.created_at}
            for ds in self._datasets.values()
        ]

    def delete_dataset(self, dataset_id: str) -> bool:
        ds = self._datasets.pop(dataset_id, None)
        if ds:
            fp = self.data_dir / f"dataset_{dataset_id}.json"
            fp.unlink(missing_ok=True)
            return True
        return False

    def add_test_case(self, dataset_id: str, case: TestCase) -> Optional[TestCase]:
        ds = self.get_dataset(dataset_id)
        if not ds:
            return None
        ds.add_case(case)
        self._save(ds)
        return case

    # ── 导入/导出 ──

    def import_json(self, filepath: str, name: str = "",
                    description: str = "") -> TestDataset:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "test_cases" in data:
            ds = TestDataset.from_dict(data)
        elif isinstance(data, list):
            cases = [TestCase.from_dict(c) if isinstance(c, dict)
                     else TestCase(query=str(c)) for c in data]
            ds = TestDataset(
                name=name or Path(filepath).stem,
                description=description,
                test_cases=cases,
            )
        else:
            ds = TestDataset(
                name=name or Path(filepath).stem,
                description=description,
                test_cases=[TestCase.from_dict(data)] if isinstance(data, dict) else [],
            )

        self._datasets[ds.id] = ds
        self._save(ds)
        return ds

    def export_json(self, dataset_id: str, filepath: str) -> bool:
        ds = self.get_dataset(dataset_id)
        if not ds:
            return False
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(ds.to_dict(), f, ensure_ascii=False, indent=2)
        return True

    # ── 自动生成 ──

    def generate_from_memories(
        self,
        memories: List[Dict[str, Any]],
        name: str = "auto_generated",
        num_cases: int = 50,
        categories: Optional[List[str]] = None,
    ) -> TestDataset:
        """从现有记忆数据自动生成测试数据集

        通过提取关键词和ID作为期望答案。
        """
        import random
        random.seed(42)

        ds = self.create_dataset(name, "自动生成的测试数据集")
        sampled = random.sample(memories, min(num_cases, len(memories)))

        for mem in sampled:
            mem_id = mem.get("id", mem.get("memory_id", ""))
            content = mem.get("content", mem.get("text", ""))
            category = mem.get("category", "general")

            if categories and category not in categories:
                continue

            # 从内容提取关键词作为查询
            words = [w.strip(".,;:!?。，；：！？") for w in content.split() if len(w) > 1]
            if len(words) < 2:
                continue

            query_words = random.sample(words, min(3, len(words)))
            query = " ".join(query_words)

            # 提取更多关键词作为期望
            keywords = set(random.sample(words, min(5, len(words))))

            case = TestCase(
                query=query,
                expected_ids={mem_id} if mem_id else set(),
                expected_keywords=keywords,
                category=category,
                tags=[category],
                metadata={"source_memory_id": mem_id},
            )
            ds.add_case(case)

        self._save(ds)
        return ds

    def generate_synthetic(
        self,
        templates: List[Dict[str, Any]],
        name: str = "synthetic",
        num_cases: int = 20,
    ) -> TestDataset:
        """从模板生成合成测试数据集

        templates 格式:
        [{"query_template": "查询 {topic}", "keywords": ["kw1", "kw2"],
          "category": "general"}]
        """
        import random
        random.seed(42)

        ds = self.create_dataset(name, "合成测试数据集")

        for i in range(num_cases):
            tpl = random.choice(templates)
            topic = random.choice(tpl.get("topics", ["topic"]))
            query = tpl.get("query_template", "{topic}").format(topic=topic)

            case = TestCase(
                query=query,
                expected_keywords=set(tpl.get("keywords", [])),
                category=tpl.get("category", "general"),
                tags=tpl.get("tags", []),
            )
            ds.add_case(case)

        self._save(ds)
        return ds
