# 搜索排序 - 快速参考

## 一句话总结

新增 `sort_by` 参数，支持综合评分、时间、热度、价格 4 种排序方式。

## API 参数

```
GET /api/memories?sort_by=relevance
```

| sort_by 值 | 说明 | 适用场景 |
|-----------|------|----------|
| `relevance` | 综合评分（默认） | 发现高质量内容 |
| `created_at` | 最新上传 | 查看最新内容 |
| `purchase_count` | 最受欢迎 | 发现热门内容 |
| `price` | 价格最低 | 精打细算 |

## 综合评分公式

```
评分×0.3 + 购买×0.2 + 验证×0.25 + 新鲜×0.15 + 收藏×0.1
```

## 快速测试

```bash
# 启动服务
uvicorn app.main:app --reload

# 测试默认排序
curl "http://localhost:8000/api/memories"

# 测试搜索 + 排序
curl "http://localhost:8000/api/memories?query=agent&sort_by=relevance"
```

## 代码示例

```python
# Python 客户端
import requests

response = requests.get("http://localhost:8000/api/memories", params={
    "query": "agent",
    "sort_by": "relevance",
    "page": 1,
    "page_size": 10
})
data = response.json()["data"]
```

## 文件位置

- 核心逻辑: `app/services/memory_service.py:78-197`
- API 路由: `app/api/routes.py:80-98`
- 完整文档: `docs/SEARCH_SORTING_IMPLEMENTATION.md`

## 向后兼容

✅ 不传 `sort_by` 参数时使用综合评分（默认）
✅ 可通过 `sort_by="created_at"` 恢复原有行为
✅ 不影响现有 API 调用

---

**详细文档**: 见 `docs/SEARCH_SORTING_IMPLEMENTATION.md`
