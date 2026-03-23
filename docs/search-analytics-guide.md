# 搜索分析指南

## 概述

搜索分析系统提供了完整的搜索日志记录、分析和A/B测试功能，帮助您持续优化搜索质量。

## 功能特性

### 1. 搜索日志记录

**特性：**
- ✅ 100%搜索覆盖率 - 记录所有搜索操作
- ✅ 异步写入 - 性能影响<3%
- ✅ 完整信息 - 查询、过滤条件、结果数、响应时间
- ✅ 自动A/B测试分组 - 支持算法对比实验
- ✅ 点击追踪 - 追踪用户点击行为

**日志保留：**
- 默认保留30天（可配置）
- 自动清理过期日志

**记录内容：**
```python
{
  "agent_id": "用户ID",
  "query": "搜索关键词",
  "search_type": "vector/keyword/hybrid",
  "filters": {
    "category": "分类",
    "platform": "平台",
    "format_type": "格式",
    "min_score": 最低评分,
    "max_price": 最高价格,
    "sort_by": "排序方式"
  },
  "result_count": 结果数量,
  "top_result_id": "第一个结果ID",
  "response_time_ms": 响应时间(毫秒),
  "semantic_score": 语义搜索得分,
  "keyword_score": 关键词搜索得分,
  "ab_test_id": "A/B测试ID",
  "ab_test_group": "A/B分组",
  "session_id": "会话ID"
}
```

### 2. 搜索分析能力

#### 2.1 搜索趋势

**API：** `GET /search-analytics/trends`

**功能：**
- 📈 实时统计热门查询
- 📊 分析每个查询的平均结果数
- ⚡ 分析每个查询的平均响应时间
- 🏷️ 识别热门分类

**参数：**
- `days`: 统计天数（1-90）
- `limit`: 返回热门查询数量（5-100）

**示例：**
```bash
GET /search-analytics/trends?days=7&limit=20
```

**响应：**
```json
[
  {
    "query": "抖音爆款视频",
    "count": 150,
    "avg_result_count": 12.5,
    "avg_response_time_ms": 145.2,
    "top_categories": ["抖音", "短视频"]
  }
]
```

#### 2.2 搜索质量指标

**API：** `GET /search-analytics/quality`

**功能：**
- 🎯 CTR（点击率） - 衡量搜索结果相关性
- ❌ 零结果率 - 识别无结果查询
- ⏱️ 平均响应时间 - 性能监控
- 👥 唯一用户数 - 用户覆盖
- 🔥 热门查询 - 用户兴趣分析

**参数：**
- `days`: 统计天数（1-90）

**示例：**
```bash
GET /search-analytics/quality?days=7
```

**响应：**
```json
{
  "total_searches": 10000,
  "unique_users": 500,
  "avg_result_count": 15.3,
  "avg_response_time_ms": 142.5,
  "ctr": 35.2,
  "zero_results_rate": 5.8,
  "top_queries": ["抖音爆款", "小红书种草"],
  "top_zero_result_queries": ["无效查询1", "无效查询2"]
}
```

#### 2.3 搜索性能统计

**API：** `GET /search-analytics/performance`

**功能：**
- 📊 P50/P95/P99 响应时间分布
- 🐌 慢查询统计（>1s）
- ⚡ 平均响应时间
- 📈 搜索量趋势

**参数：**
- `period`: 统计周期（hour/day/week）

**示例：**
```bash
GET /search-analytics/performance?period=day
```

**响应：**
```json
{
  "period": "day",
  "search_count": 1500,
  "avg_response_time_ms": 145.2,
  "p50_response_time_ms": 130,
  "p95_response_time_ms": 200,
  "p99_response_time_ms": 350,
  "slow_searches_count": 12
}
```

#### 2.4 零结果查询分析

**API：** `GET /search-analytics/zero-results`

**功能：**
- 🔍 识别零结果查询
- 📊 分析零结果查询频率
- 👥 识别受影响用户
- ⏱️ 分析查询响应时间

**参数：**
- `days`: 统计天数（1-90）
- `limit`: 返回数量（10-200）

**示例：**
```bash
GET /search-analytics/zero-results?days=7&limit=50
```

**响应：**
```json
{
  "period_days": 7,
  "queries": [
    {
      "query": "无效关键词",
      "count": 25,
      "avg_response_time_ms": 120.5,
      "unique_users": 10
    }
  ]
}
```

#### 2.5 用户搜索行为

**API：** `GET /search-analytics/user-behavior`

**功能：**
- 👤 用户搜索频率分析
- 🔍 唯一查询统计
- ⏱️ 平均每天搜索次数
- 🎯 用户CTR分析
- ❤️ 用户最喜爱的查询

**参数：**
- `days`: 统计天数（1-90）
- `limit`: 返回用户数量（10-200）

**示例：**
```bash
GET /search-analytics/user-behavior?days=7&limit=50
```

**响应：**
```json
[
  {
    "agent_id": "agent_xxx",
    "agent_name": "测试用户",
    "total_searches": 50,
    "unique_queries": 20,
    "avg_searches_per_day": 7.14,
    "avg_result_count": 15.2,
    "ctr": 40.0,
    "last_search_at": "2026-03-23T10:00:00",
    "favorite_queries": ["抖音爆款", "小红书种草"]
  }
]
```

### 3. A/B测试框架

#### 3.1 A/B测试类型

支持的测试类型：

1. **algorithm** - 算法对比
   - 向量搜索 vs 混合搜索
   - 不同嵌入模型对比

2. **reranking** - 重排序策略
   - 不同重排序算法
   - 权重调整对比

3. **filtering** - 过滤策略
   - 不同过滤条件
   - 阈值调整对比

4. **sorting** - 排序策略
   - 不同排序算法
   - 权重调整对比

#### 3.2 创建A/B测试

**API：** `POST /ab-tests`

**请求示例：**
```json
{
  "name": "向量搜索 vs 混合搜索",
  "description": "对比向量搜索和混合搜索的效果",
  "test_type": "algorithm",
  "start_at": "2026-03-24T00:00:00",
  "end_at": "2026-03-31T00:00:00",
  "split_ratio": {
    "A": 0.5,
    "B": 0.5
  },
  "group_configs": {
    "A": {
      "algorithm": "vector",
      "model": "BAAI/bge-small-zh-v1.5"
    },
    "B": {
      "algorithm": "hybrid",
      "model": "BAAI/bge-small-zh-v1.5",
      "keyword_weight": 0.4
    }
  },
  "metrics": ["ctr", "zero_results_rate", "avg_response_time"]
}
```

**参数说明：**

| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 测试名称 |
| description | string | 测试描述（可选） |
| test_type | string | 测试类型 |
| start_at | datetime | 开始时间（必须在未来） |
| end_at | datetime | 结束时间 |
| split_ratio | object | 分流比例（总和必须为1.0） |
| group_configs | object | 各组配置 |
| metrics | array | 目标指标 |

#### 3.3 启动/停止A/B测试

**启动测试：** `POST /ab-tests/{test_id}/start`

**停止测试：** `POST /ab-tests/{test_id}/stop`

**取消测试：** `POST /ab-tests/{test_id}/cancel`

#### 3.4 查看A/B测试结果

**API：** `GET /ab-tests/{test_id}/results`

**响应示例：**
```json
{
  "test_id": "abtest_xxx",
  "name": "向量搜索 vs 混合搜索",
  "status": "completed",
  "group_stats": [
    {
      "group": "A",
      "searches": 500,
      "clicks": 175,
      "ctr": 35.0,
      "avg_result_count": 12.5,
      "avg_response_time_ms": 130.2,
      "zero_results_rate": 6.0
    },
    {
      "group": "B",
      "searches": 500,
      "clicks": 200,
      "ctr": 40.0,
      "avg_result_count": 15.3,
      "avg_response_time_ms": 142.5,
      "zero_results_rate": 4.5
    }
  ],
  "metrics_comparison": {
    "ctr": {
      "A": 35.0,
      "B": 40.0
    },
    "zero_results_rate": {
      "A": 6.0,
      "B": 4.5
    },
    "avg_response_time_ms": {
      "A": 130.2,
      "B": 142.5
    }
  },
  "significance": 5.0,
  "winner": "B",
  "recommendation": "建议采用 B 分组的配置（CTR更高）"
}
```

## Grafana Dashboard

### 导入Dashboard

1. 登录Grafana
2. 进入 **Configuration** -> **Dashboards** -> **Import**
3. 上传 `grafana/dashboards/search-analytics.json`
4. 选择PostgreSQL数据源
5. 点击 **Import**

### Dashboard面板

**概览面板：**
- 24h总搜索量
- 平均响应时间
- CTR（点击率）
- 零结果率

**趋势面板：**
- 搜索趋势（7天）
- 响应时间趋势
- 热门查询排行
- 零结果查询排行

**分布面板：**
- 搜索类型分布
- 排序方式分布
- 分类分布

## 最佳实践

### 1. 搜索优化流程

**步骤1：分析当前状态**
```bash
# 查看搜索质量指标
GET /search-analytics/quality?days=7

# 查看零结果查询
GET /search-analytics/zero-results?days=7
```

**步骤2：识别问题**
- 零结果率过高（>10%）→ 检查数据覆盖
- CTR过低（<20%）→ 检查排序算法
- 响应时间过长（>500ms）→ 检查性能

**步骤3：设计A/B测试**
```json
{
  "name": "优化方案对比",
  "test_type": "algorithm",
  "split_ratio": {"A": 0.5, "B": 0.5},
  "group_configs": {
    "A": {"algorithm": "vector"},
    "B": {"algorithm": "hybrid", "keyword_weight": 0.5}
  }
}
```

**步骤4：启动测试**
```bash
POST /ab-tests/{test_id}/start
```

**步骤5：监控结果**
```bash
GET /ab-tests/{test_id}/results
```

**步骤6：决策**
- 如果B组CTR显著提高 → 采用B组配置
- 如果无明显差异 → 延长测试或调整方案

### 2. 零结果查询处理

**方法1：扩大搜索范围**
```python
# 提高相似度阈值
top_k = 50  # 从20提高到50
min_score = 0.1  # 从0.2降低到0.1
```

**方法2：添加同义词**
```python
synonyms = {
  "抖音": ["TikTok", "字节跳动"],
  "爆款": ["热门", "流行"]
}
```

**方法3：引导用户**
```python
if result_count == 0:
    suggestions = get_similar_queries(query)
    return {
        "results": [],
        "suggestions": suggestions,
        "message": "未找到相关结果，试试这些关键词？"
    }
```

### 3. 性能优化建议

**异步写入：**
```python
# 使用搜索日志中间件
from app.api.search_middleware import get_search_log_middleware

middleware = await get_search_log_middleware()
await middleware.log_search(
    db=db,
    agent_id=agent_id,
    query=query,
    search_type="hybrid",
    filters=filters,
    results=results,
    response_time_ms=response_time_ms
)
```

**索引优化：**
```sql
-- 复合索引
CREATE INDEX idx_search_logs_agent_time
ON search_logs (agent_id, created_at);

CREATE INDEX idx_search_logs_query_time
ON search_logs (query, created_at);
```

**分区表：**
```sql
-- 按月分区
CREATE TABLE search_logs_202603 PARTITION OF search_logs
FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

## 监控告警

### 建议告警规则

**1. 零结果率过高**
```
条件: zero_results_rate > 15%
持续: 15分钟
通知: 邮件/Slack
```

**2. 响应时间过长**
```
条件: p95_response_time_ms > 500
持续: 10分钟
通知: 邮件/Slack
```

**3. CTR过低**
```
条件: ctr < 10%
持续: 30分钟
通知: 邮件/Slack
```

**4. 搜索量异常**
```
条件: search_count < 历史平均值的50%
持续: 30分钟
通知: 邮件/Slack
```

## API权限

| API | 权限要求 |
|-----|---------|
| `GET /search-analytics/*` | Admin |
| `POST /ab-tests` | 任何用户 |
| `GET /ab-tests` | 任何用户（自己的测试） |
| `GET /ab-tests/{id}` | 任何用户（自己的测试） |
| `POST /ab-tests/{id}/start` | Admin |
| `POST /ab-tests/{id}/stop` | Admin |
| `POST /ab-tests/{id}/cancel` | 创建者 |
| `DELETE /ab-tests/{id}` | 创建者（仅draft/cancelled） |
| `POST /ab-tests/{id}/report` | Admin |
| `GET /ab-tests/{id}/results` | 创建者 |

## 数据隐私

### 脱敏处理

搜索日志中的敏感信息已自动脱敏：
- ✅ 查询内容保留（用于分析）
- ❌ 用户信息匿名化
- ❌ API密钥不记录
- ❌ 详细请求体不记录

### 数据保留策略

- 搜索日志：30天
- 点击日志：30天
- A/B测试配置：永久
- A/B测试结果：90天

## 故障排查

### 问题1：日志未记录

**检查清单：**
- [ ] 搜索日志中间件已启动
- [ ] 数据库连接正常
- [ ] 队列未满（默认1000）

**解决方案：**
```python
# 启动中间件
from app.api.search_middleware import search_log_middleware
await search_log_middleware.start()
```

### 问题2：A/B测试未生效

**检查清单：**
- [ ] 测试状态为running
- [ ] 开始时间已到
- [ ] 结束时间未到
- [ ] split_ratio正确

**解决方案：**
```bash
# 查看测试状态
GET /ab-tests/{test_id}

# 启动测试
POST /ab-tests/{test_id}/start
```

### 问题3：Dashboard无数据

**检查清单：**
- [ ] 数据源配置正确
- [ ] 时间范围正确
- [ ] 有搜索日志数据

**解决方案：**
```sql
-- 检查数据是否存在
SELECT COUNT(*), created_at
FROM search_logs
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY created_at DESC
LIMIT 24;
```

## 下一步

### P1.4计划

- 🔍 智能查询建议
- 🎯 个性化搜索推荐
- 📊 高级统计分析
- 🤖 AI驱动的搜索优化

### 联系支持

如有问题，请联系开发团队或查看文档。
