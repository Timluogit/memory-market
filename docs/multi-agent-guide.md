# 多Agent并行推理架构指南

## 概述

基于Supermemory ASMR架构实现的多Agent并行推理系统，通过3个观察者Agent + 3个搜索Agent + 1个聚合器Agent的并行协作，提升搜索准确率。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    MultiAgentPipeline                        │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  Phase 1    │  Phase 2    │  Phase 3    │   Output         │
│  Observers  │  Searchers  │  Aggregator │                  │
│  (并行)     │  (并行)     │  (单线程)   │                  │
├─────────────┼─────────────┼─────────────┼──────────────────┤
│ UserInfo    │ DirectFact  │             │                  │
│ Agent       │ Agent       │  结果聚合   │  最终结果        │
│             │             │  重排评分   │  + 置信度        │
│ Temporal    │ Context     │  置信度计算 │  + 维度覆盖      │
│ Agent       │ Agent       │             │                  │
│             │             │             │                  │
│ General     │ Timeline    │             │                  │
│ Observer    │ Agent       │             │                  │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

## Agent角色定义

### 观察者Agent（Phase 1）

| Agent | 角色 | 职责 | 对应维度 |
|-------|------|------|----------|
| UserInfoAgent | OBSERVER_USER_INFO | 提取个人信息和偏好 | 维度1(个人信息)、维度2(偏好) |
| TemporalAgent | OBSERVER_TEMPORAL | 提取时序数据和事件 | 维度3(事件)、维度4(时序)、维度5(更新) |
| GeneralObserver | OBSERVER_GENERAL | 提取助手信息和数据质量 | 维度6(助手信息) |

### 搜索Agent（Phase 2）

| Agent | 角色 | 职责 | 策略 |
|-------|------|------|------|
| DirectFactAgent | SEARCHER_DIRECT | 搜索直接事实 | 关键词精确匹配 + 标题优先 |
| ContextAgent | SEARCHER_CONTEXT | 寻找相关上下文 | 分类匹配 + 标签 + 购买历史 |
| TimelineAgent | SEARCHER_TIMELINE | 重建时间线和关系 | 时间范围 + 版本历史 + 关联图谱 |

### 聚合器Agent（Phase 3）

| Agent | 角色 | 职责 |
|-------|------|------|
| AggregatorAgent | AGGREGATOR | 结果聚合、去重、加权重排、置信度计算 |

### 权重策略

- 直接事实搜索：40%
- 上下文搜索：35%
- 时间线搜索：25%

## 6大提取维度

| 维度 | 说明 | 示例数据 |
|------|------|----------|
| user_info | 个人信息 | 姓名、职位、公司、技能 |
| preferences | 偏好 | 工具、编程语言、主题 |
| events | 事件 | 会议、项目、发布 |
| temporal | 时序数据 | 日期、相对时间、时间线 |
| updates | 信息更新 | 变更前后对比 |
| assistant | 助手信息 | 交互模式、格式偏好 |

## 使用指南

### 基本使用

```python
from app.services.multi_agent_pipeline import run_multi_agent_search

# 简单搜索
result = await run_multi_agent_search(
    query="Python最佳实践",
    db=db_session,  # 可选
)

print(f"状态: {result.status}")
print(f"结果数: {len(result.results)}")
print(f"置信度: {result.confidence}")
print(f"耗时: {result.total_time_ms:.0f}ms")
```

### 带原始数据的搜索

```python
result = await run_multi_agent_search(
    query="搜索相关记忆",
    raw_data={
        "content": "我是张三，Python工程师...",
        "profile": "在腾讯工作，擅长AI开发",
    },
    user_id="user123",
)
```

### 使用搜索引擎集成层

```python
from app.search.multi_agent_search import get_multi_agent_engine

engine = get_multi_agent_engine(db=db_session)

result = await engine.search(
    query="Python编程",
    page=1,
    page_size=10,
)

# result包含：
# - results: 结果列表
# - confidence: 置信度
# - search_type: "multi_agent" 或 "hybrid_fallback"
# - pipeline_detail: 流水线详情
```

### 自定义聚合权重

```python
from app.agents.aggregator import AggregatorAgent

agent = AggregatorAgent(
    weight_direct=0.5,
    weight_context=0.3,
    weight_timeline=0.2,
)
```

## 降级策略

系统内置三级降级：

1. **多Agent正常执行** → 返回聚合结果
2. **多Agent置信度不足** → 回退到混合搜索引擎
3. **混合搜索也失败** → 返回空结果

降级阈值可通过 `min_confidence` 参数配置（默认0.2）。

## 性能优化

### 并行执行
- Phase 1（观察者）和 Phase 2（搜索Agent）均使用 `asyncio.gather` 并行执行
- 各Agent有独立超时控制

### 超时配置
- 观察者Agent：默认15秒
- 搜索Agent：默认20秒
- 聚合器Agent：默认10秒

### 性能指标
每次搜索返回详细的性能指标：
```python
result.to_dict() == {
    "observer_time_ms": 120.5,
    "searcher_time_ms": 350.2,
    "aggregator_time_ms": 15.3,
    "total_time_ms": 486.0,
    "dimension_coverage": {
        "filled_count": 4,
        "total_count": 6,
        "coverage_ratio": 0.67,
    },
}
```

## 文件结构

```
app/
├── agents/
│   ├── __init__.py
│   ├── observers/
│   │   ├── __init__.py
│   │   ├── user_info_agent.py      # 用户信息观察者
│   │   ├── temporal_agent.py        # 时序观察者
│   │   └── general_observer.py      # 通用观察者
│   ├── searchers/
│   │   ├── __init__.py
│   │   ├── direct_fact_agent.py     # 直接事实搜索
│   │   ├── context_agent.py         # 上下文搜索
│   │   └── timeline_agent.py        # 时间线搜索
│   └── aggregator.py                # 聚合器Agent
├── services/
│   ├── agent_base.py                # Agent抽象层
│   └── multi_agent_pipeline.py      # 多Agent流水线
└── search/
    └── multi_agent_search.py        # 搜索集成层

tests/
└── test_multi_agent.py             # 测试

docs/
└── multi-agent-guide.md            # 本文档
```

## 扩展指南

### 添加新Agent

1. 继承 `BaseAgent` 类
2. 实现 `execute(context: AgentContext) -> AgentResult` 方法
3. 在 `agent_base.py` 的 `_register_default_agents` 中注册
4. 在流水线的相应阶段添加调用

### 添加新维度

1. 在 `AgentContext` 中添加字段
2. 在 `set_dimension`/`get_dimension` 的映射中添加
3. 由对应的观察者Agent负责提取

### 扩展到8变体/12变体

Supermemory ASMR支持8变体集群和12变体决策森林。可通过以下方式扩展：

1. 创建新的搜索Agent变体（不同策略）
2. 在 `MultiAgentPipeline._run_searchers` 中添加更多搜索角色
3. 调整 `AggregatorAgent` 的权重策略
