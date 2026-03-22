# 语义搜索快速参考

## 三种搜索模式

| 模式 | 说明 | 适用场景 | API 参数 |
|------|------|----------|----------|
| keyword | 关键词匹配 | 精确查找 | `search_type=keyword` |
| semantic | 语义搜索 | 概念查询 | `search_type=semantic` |
| hybrid | 混合搜索 | 通用场景（推荐） | `search_type=hybrid`（默认） |

## API 调用示例

```bash
# 语义搜索
GET /memories?search_type=semantic&query=API开发

# 关键词搜索
GET /memories?search_type=keyword&query=Python

# 混合搜索（推荐）
GET /memories?search_type=hybrid&query=web安全

# 带筛选的混合搜索
GET /memories?search_type=hybrid&query=Python&category=编程/Python&page_size=10
```

## Python 代码示例

```python
from app.services.memory_service import search_memories

# 语义搜索
result = await search_memories(
    db,
    query="API开发",
    search_type="semantic",
    page=1,
    page_size=10
)

# 混合搜索（推荐）
result = await search_memories(
    db,
    query="机器学习",
    search_type="hybrid",
    category="AI/机器学习",
    page=1,
    page_size=10
)
```

## 性能数据

- **平均延迟**: < 2ms
- **目标**: < 200ms ✓
- **支持语言**: 中英文

## 测试

```bash
# 单元测试
python test_semantic_search.py

# 集成测试
python test_search_integration.py

# API 测试（需先启动服务器）
python test_api_search.py
```

## 核心文件

- `app/search/vector_search.py` - 向量搜索引擎
- `app/services/memory_service.py` - 搜索服务
- `app/api/routes.py` - API 接口

## 依赖

```txt
scikit-learn>=1.3.0
```

## 更多信息

详见 `SEMANTIC_SEARCH.md` 完整文档。
