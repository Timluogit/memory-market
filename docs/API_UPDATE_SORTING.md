# API 更新说明 - 搜索排序优化

## 更新内容

`GET /api/memories` 接口新增 `sort_by` 参数，支持多种排序方式。

## 新增参数

| 参数名 | 类型 | 可选值 | 默认值 | 说明 |
|--------|------|--------|--------|------|
| sort_by | string | relevance, created_at, purchase_count, price | relevance | 排序方式 |

## 参数说明

### relevance - 综合评分（默认）

综合考虑多个因素的综合评分：

```
综合评分 = 评分×0.3 + 购买次数×0.2 + 验证分数×0.25 + 时间新鲜度×0.15 + 收藏次数×0.1
```

**特点**：
- 高质量记忆优先
- 热门记忆不会完全垄断（使用对数归一化）
- 新记忆有时间加成
- 搜索时标题匹配额外加分

### created_at - 创建时间

按记忆上传时间倒序排列，最新的在前。

### purchase_count - 购买次数

按购买次数倒序排列，最受欢迎的在前。

### price - 价格

按价格升序排列，最便宜的在前。

## 使用示例

```bash
# 默认：综合评分排序
GET /api/memories

# 明确指定：综合评分
GET /api/memories?sort_by=relevance

# 按创建时间
GET /api/memories?sort_by=created_at

# 按购买次数
GET /api/memories?sort_by=purchase_count

# 按价格
GET /api/memories?sort_by=price

# 组合使用：搜索 + 综合评分
GET /api/memories?query=agent&sort_by=relevance
```

## 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "memory_id": "mem_abc123",
        "title": "高质量Agent模板",
        "avg_score": 4.8,
        "purchase_count": 156,
        "favorite_count": 89,
        "verification_score": 0.92,
        "price": 500,
        "created_at": "2026-03-20T10:30:00"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 10
  }
}
```

## 兼容性说明

- ✅ **向后兼容**：不传 `sort_by` 参数时，使用新的综合评分排序（默认行为）
- ✅ **可选参数**：可通过 `sort_by="created_at"` 恢复原来的时间排序行为
- ✅ **无破坏性**：不影响现有 API 调用

## 实现细节

详见完整文档：`docs/SEARCH_SORTING_IMPLEMENTATION.md`
