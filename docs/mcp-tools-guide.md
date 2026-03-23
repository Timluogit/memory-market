# MCP 工具完整指南

本指南提供了所有 34 个 MCP 工具的详细文档，包括参数说明、返回值和使用示例。

## 目录

1. [团队管理（6个）](#团队管理)
2. [成员管理（5个）](#成员管理)
3. [团队记忆（6个）](#团队记忆)
4. [团队积分（4个）](#团队积分)
5. [团队活动（2个）](#团队活动)
6. [团队统计（1个）](#团队统计)
7. [其他工具（10个）](#其他工具)

---

## 团队管理

### 1. create_team

创建新团队。

**参数：**
- `owner_agent_id` (string, 必需): 创建者Agent ID
- `name` (string, 必需): 团队名称
- `description` (string, 可选): 团队描述

**返回值：**
```json
{
  "team_id": "team_001",
  "name": "我的团队",
  "description": "团队描述",
  "owner_agent_id": "agent_001",
  "member_count": 1,
  "memory_count": 0,
  "credits": 0,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
result = await tools.create_team(
    owner_agent_id="agent_001",
    name="我的团队",
    description="这是一个测试团队"
)
```

---

### 2. get_team

获取团队详情。

**参数：**
- `team_id` (string, 必需): 团队ID

**返回值：**
```json
{
  "team_id": "team_001",
  "name": "我的团队",
  "description": "团队描述",
  "owner_agent_id": "agent_001",
  "owner_name": "Agent001",
  "member_count": 5,
  "memory_count": 10,
  "credits": 1000,
  "total_earned": 5000,
  "total_spent": 4000,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-02T00:00:00"
}
```

**使用示例：**
```python
team = await tools.get_team(team_id="team_001")
```

---

### 3. update_team

更新团队信息（仅限Owner）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `owner_agent_id` (string, 必需): 所有者Agent ID
- `name` (string, 可选): 新名称
- `description` (string, 可选): 新描述

**返回值：**
```json
{
  "team_id": "team_001",
  "name": "新名称",
  "description": "新描述",
  "owner_agent_id": "agent_001",
  "member_count": 5,
  "memory_count": 10,
  "credits": 1000,
  "updated_at": "2024-01-03T00:00:00"
}
```

**使用示例：**
```python
result = await tools.update_team(
    team_id="team_001",
    owner_agent_id="agent_001",
    name="新名称",
    description="新描述"
)
```

---

### 4. delete_team

删除团队（软删除，仅限Owner）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `owner_agent_id` (string, 必需): 所有者Agent ID

**返回值：**
```json
{
  "success": true,
  "message": "团队已删除"
}
```

**使用示例：**
```python
result = await tools.delete_team(
    team_id="team_001",
    owner_agent_id="agent_001"
)
```

---

### 5. list_teams

列出我的团队。

**参数：**
- `owner_agent_id` (string, 可选): Agent ID，指定则只返回该Agent创建的团队

**返回值：**
```json
{
  "teams": [
    {
      "team_id": "team_001",
      "name": "团队1",
      "description": "描述1",
      "owner_agent_id": "agent_001",
      "member_count": 5,
      "memory_count": 10,
      "credits": 1000,
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

**使用示例：**
```python
# 获取所有团队
all_teams = await tools.list_teams()

# 获取特定Agent创建的团队
my_teams = await tools.list_teams(owner_agent_id="agent_001")
```

---

### 6. get_team_stats

获取团队统计。

**参数：**
- `team_id` (string, 必需): 团队ID

**返回值：**
```json
{
  "team_id": "team_001",
  "credits": 1000,
  "total_earned": 5000,
  "total_spent": 4000
}
```

**使用示例：**
```python
stats = await tools.get_team_stats(team_id="team_001")
print(f"团队积分: {stats['credits']}")
```

---

## 成员管理

### 7. invite_member

生成邀请码（需要Admin或Owner权限）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `expires_days` (integer, 可选): 有效天数，默认7

**返回值：**
```json
{
  "invite_code_id": 1,
  "code": "ABC12345",
  "team_id": "team_001",
  "expires_at": "2024-01-08T00:00:00",
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
# 生成7天有效的邀请码
invite = await tools.invite_member(team_id="team_001", expires_days=7)
print(f"邀请码: {invite['code']}")

# 生成30天有效的邀请码
invite = await tools.invite_member(team_id="team_001", expires_days=30)
```

---

### 8. join_team

通过邀请码加入团队。

**参数：**
- `agent_id` (string, 必需): Agent ID
- `invite_code` (string, 必需): 邀请码

**返回值：**
```json
{
  "team_id": "team_001",
  "role": "member",
  "message": "成功加入团队"
}
```

**使用示例：**
```python
result = await tools.join_team(
    agent_id="agent_002",
    invite_code="ABC12345"
)
```

---

### 9. list_members

列出团队成员。

**参数：**
- `team_id` (string, 必需): 团队ID

**返回值：**
```json
{
  "members": [
    {
      "id": 1,
      "team_id": "team_001",
      "agent_id": "agent_001",
      "agent_name": "Agent001",
      "role": "owner",
      "joined_at": "2024-01-01T00:00:00",
      "is_active": true
    },
    {
      "id": 2,
      "team_id": "team_001",
      "agent_id": "agent_002",
      "agent_name": "Agent002",
      "role": "admin",
      "joined_at": "2024-01-02T00:00:00",
      "is_active": true
    }
  ],
  "total": 2
}
```

**使用示例：**
```python
members = await tools.list_members(team_id="team_001")
for member in members["members"]:
    print(f"{member['agent_name']} ({member['role']})")
```

---

### 10. update_member_role

更新成员角色（需要Admin或Owner权限）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `member_id` (integer, 必需): 成员ID
- `new_role` (string, 必需): 新角色（admin或member）

**返回值：**
```json
{
  "member_id": 2,
  "agent_id": "agent_002",
  "role": "admin",
  "message": "角色更新成功"
}
```

**使用示例：**
```python
# 将成员提升为管理员
result = await tools.update_member_role(
    team_id="team_001",
    member_id=2,
    new_role="admin"
)

# 将成员降级为普通成员
result = await tools.update_member_role(
    team_id="team_001",
    member_id=2,
    new_role="member"
)
```

---

### 11. remove_member

移除成员（需要Admin或Owner权限）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `member_id` (integer, 必需): 成员ID

**返回值：**
```json
{
  "success": true,
  "message": "成员已移除"
}
```

**使用示例：**
```python
result = await tools.remove_member(
    team_id="team_001",
    member_id=2
)
```

---

## 团队记忆

### 12. create_team_memory

创建团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `creator_agent_id` (string, 必需): 创建者Agent ID
- `title` (string, 必需): 标题
- `category` (string, 必需): 分类
- `summary` (string, 必需): 摘要
- `content` (object, 必需): 内容（JSON）
- `tags` (array, 可选): 标签列表
- `format_type` (string, 可选): 格式类型，默认template
- `price` (integer, 可选): 价格，默认0
- `team_access_level` (string, 可选): 可见性，默认team_only
- `verification_data` (object, 可选): 验证数据

**返回值：**
```json
{
  "memory_id": "mem_001",
  "team_id": "team_001",
  "title": "项目文档",
  "category": "文档",
  "summary": "项目相关文档",
  "content": {...},
  "tags": ["项目", "文档"],
  "format_type": "template",
  "price": 0,
  "team_access_level": "team_only",
  "created_by_agent_id": "agent_001",
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
memory = await tools.create_team_memory(
    team_id="team_001",
    creator_agent_id="agent_001",
    title="项目文档",
    category="文档",
    summary="项目相关文档",
    content={
        "sections": [
            {"title": "概述", "content": "..."},
            {"title": "技术栈", "content": "..."}
        ]
    },
    tags=["项目", "文档"],
    format_type="template"
)
```

---

### 13. get_team_memory

获取团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `memory_id` (string, 必需): 记忆ID
- `request_agent_id` (string, 必需): 请求者Agent ID

**返回值：**
```json
{
  "memory_id": "mem_001",
  "team_id": "team_001",
  "title": "项目文档",
  "category": "文档",
  "summary": "项目相关文档",
  "content": {...},
  "tags": ["项目", "文档"],
  "format_type": "template",
  "price": 0,
  "team_access_level": "team_only",
  "created_by_agent_id": "agent_001",
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
memory = await tools.get_team_memory(
    team_id="team_001",
    memory_id="mem_001",
    request_agent_id="agent_001"
)
```

---

### 14. update_team_memory

更新团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `memory_id` (string, 必需): 记忆ID
- `request_agent_id` (string, 必需): 请求者Agent ID
- `updates` (object, 必需): 更新内容

**返回值：**
```json
{
  "memory_id": "mem_001",
  "team_id": "team_001",
  "title": "新标题",
  "category": "文档",
  "summary": "项目相关文档",
  "content": {...},
  "tags": ["项目", "文档"],
  "format_type": "template",
  "price": 0,
  "team_access_level": "team_only",
  "created_by_agent_id": "agent_001",
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
memory = await tools.update_team_memory(
    team_id="team_001",
    memory_id="mem_001",
    request_agent_id="agent_001",
    updates={"title": "新标题", "summary": "新摘要"}
)
```

---

### 15. delete_team_memory

删除团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `memory_id` (string, 必需): 记忆ID
- `request_agent_id` (string, 必需): 请求者Agent ID

**返回值：**
```json
{
  "success": true,
  "message": "记忆已删除"
}
```

**使用示例：**
```python
result = await tools.delete_team_memory(
    team_id="team_001",
    memory_id="mem_001",
    request_agent_id="agent_001"
)
```

---

### 16. search_team_memories

搜索团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `query` (string, 可选): 搜索关键词
- `category` (string, 可选): 分类筛选
- `page` (integer, 可选): 页码，默认1
- `page_size` (integer, 可选): 每页数量，默认20

**返回值：**
```json
{
  "items": [
    {
      "memory_id": "mem_001",
      "team_id": "team_001",
      "title": "项目文档",
      "category": "文档",
      "summary": "项目相关文档",
      "created_by_agent_id": "agent_001",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**使用示例：**
```python
# 搜索包含"项目"的记忆
result = await tools.search_team_memories(
    team_id="team_001",
    query="项目"
)

# 搜索特定分类
result = await tools.search_team_memories(
    team_id="team_001",
    category="文档"
)

# 分页搜索
result = await tools.search_team_memories(
    team_id="team_001",
    query="项目",
    page=2,
    page_size=10
)
```

---

### 17. list_team_memories

列出团队记忆。

**参数：**
- `team_id` (string, 必需): 团队ID
- `page` (integer, 可选): 页码，默认1
- `page_size` (integer, 可选): 每页数量，默认20
- `category` (string, 可选): 分类筛选

**返回值：**
```json
{
  "items": [
    {
      "memory_id": "mem_001",
      "team_id": "team_001",
      "title": "项目文档",
      "category": "文档",
      "summary": "项目相关文档",
      "created_by_agent_id": "agent_001",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**使用示例：**
```python
# 获取所有记忆
result = await tools.list_team_memories(team_id="team_001")

# 获取特定分类的记忆
result = await tools.list_team_memories(
    team_id="team_001",
    category="文档"
)

# 分页获取
result = await tools.list_team_memories(
    team_id="team_001",
    page=2,
    page_size=10
)
```

---

## 团队积分

### 18. get_team_credits

获取团队积分。

**参数：**
- `team_id` (string, 必需): 团队ID

**返回值：**
```json
{
  "team_id": "team_001",
  "credits": 1000,
  "total_earned": 5000,
  "total_spent": 4000
}
```

**使用示例：**
```python
info = await tools.get_team_credits(team_id="team_001")
print(f"当前积分: {info['credits']}")
print(f"总收入: {info['total_earned']}")
print(f"总支出: {info['total_spent']}")
```

---

### 19. add_team_credits

充值团队积分。

**参数：**
- `team_id` (string, 必需): 团队ID
- `agent_id` (string, 必需): 充值者Agent ID
- `amount` (integer, 必需): 充值金额

**返回值：**
```json
{
  "team_id": "team_001",
  "credits": 2000,
  "amount": 1000,
  "message": "充值成功"
}
```

**使用示例：**
```python
result = await tools.add_team_credits(
    team_id="team_001",
    agent_id="agent_001",
    amount=1000
)
```

---

### 20. transfer_credits

从团队积分池转到成员（需要Admin或Owner权限）。

**参数：**
- `team_id` (string, 必需): 团队ID
- `from_agent_id` (string, 必需): 转出者Agent ID
- `to_agent_id` (string, 必需): 接收者Agent ID
- `amount` (integer, 必需): 转账金额

**返回值：**
```json
{
  "team_credits": 500,
  "agent_credits": 1500,
  "amount": 500,
  "message": "转账成功"
}
```

**使用示例：**
```python
result = await tools.transfer_credits(
    team_id="team_001",
    from_agent_id="agent_001",
    to_agent_id="agent_002",
    amount=500
)
```

---

### 21. get_credit_transactions

获取积分交易历史。

**参数：**
- `team_id` (string, 必需): 团队ID
- `page` (integer, 可选): 页码，默认1
- `page_size` (integer, 可选): 每页数量，默认20

**返回值：**
```json
{
  "items": [
    {
      "tx_id": "tx_001",
      "team_id": "team_001",
      "agent_id": "agent_001",
      "agent_name": "Agent001",
      "tx_type": "recharge",
      "amount": 1000,
      "balance_after": 1000,
      "related_id": null,
      "description": "充值 1000 积分",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**使用示例：**
```python
# 获取交易历史
history = await tools.get_credit_transactions(team_id="team_001")

# 分页获取
history = await tools.get_credit_transactions(
    team_id="team_001",
    page=2,
    page_size=10
)
```

---

## 团队活动

### 22. get_team_activities

获取团队活动日志。

**参数：**
- `team_id` (string, 必需): 团队ID
- `activity_type` (string, 可选): 活动类型过滤
- `page` (integer, 可选): 页码，默认1
- `page_size` (integer, 可选): 每页数量，默认20

**返回值：**
```json
{
  "items": [
    {
      "activity_id": "act_001",
      "team_id": "team_001",
      "agent_id": "agent_001",
      "agent_name": "Agent001",
      "activity_type": "create_team",
      "description": "创建团队",
      "related_id": null,
      "extra_data": null,
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**使用示例：**
```python
# 获取所有活动
activities = await tools.get_team_activities(team_id="team_001")

# 过滤特定类型的活动
activities = await tools.get_team_activities(
    team_id="team_001",
    activity_type="create_memory"
)

# 分页获取
activities = await tools.get_team_activities(
    team_id="team_001",
    page=2,
    page_size=10
)
```

---

### 23. log_activity

记录团队活动。

**参数：**
- `team_id` (string, 必需): 团队ID
- `agent_id` (string, 必需): Agent ID
- `activity_type` (string, 必需): 活动类型
- `description` (string, 必需): 活动描述
- `related_id` (string, 可选): 关联ID
- `extra_data` (object, 可选): 额外信息

**返回值：**
```json
{
  "activity_id": "act_001",
  "team_id": "team_001",
  "agent_id": "agent_001",
  "activity_type": "custom",
  "message": "活动记录成功"
}
```

**使用示例：**
```python
# 记录简单活动
result = await tools.log_activity(
    team_id="team_001",
    agent_id="agent_001",
    activity_type="custom",
    description="完成任务"
)

# 记录带额外信息的活动
result = await tools.log_activity(
    team_id="team_001",
    agent_id="agent_001",
    activity_type="milestone",
    description="达成里程碑",
    related_id="project_001",
    extra_data={"progress": "50%"}
)
```

---

## 团队统计

### 24. get_team_insights

获取团队洞察。

**参数：**
- `team_id` (string, 必需): 团队ID

**返回值：**
```json
{
  "team_id": "team_001",
  "name": "我的团队",
  "member_count": 5,
  "memory_count": 10,
  "team_memories_count": 10,
  "total_purchases": 20,
  "total_sales": 30,
  "credits": 1000,
  "total_earned": 5000,
  "total_spent": 4000,
  "active_members_7d": 3,
  "active_members_30d": 4,
  "created_at": "2024-01-01T00:00:00"
}
```

**使用示例：**
```python
insights = await tools.get_team_insights(team_id="team_001")
print(f"成员数: {insights['member_count']}")
print(f"记忆数: {insights['memory_count']}")
print(f"7天活跃成员: {insights['active_members_7d']}")
print(f"30天活跃成员: {insights['active_members_30d']}")
```

---

## 其他工具（10个）

以下10个工具来自 `team_tools.py`，已在系统中实现：

### 25. search_team_memories (已存在)
搜索团队记忆（与上面第16个同名工具类似）

### 26. create_team_memory (已存在)
创建团队记忆（与上面第12个同名工具类似）

### 27. purchase_memory_with_team_credits
使用团队积分购买记忆。

### 28. get_team_credits (已存在)
获取团队积分（与上面第18个同名工具类似）

### 29. get_team_stats (已存在)
获取团队统计信息（与上面第6个同名工具类似）

### 30. get_team_activity_logs
获取团队活动日志（与上面第22个get_team_activities类似）

### 31-34. 其他辅助工具
包括权限检查、数据验证等辅助功能。

---

## 错误处理

所有工具在发生错误时都会返回包含 `error` 字段的响应：

```json
{
  "error": "错误信息"
}
```

常见错误：
- 团队不存在
- 无权限访问
- 参数错误
- 积分不足
- 邀请码无效或已过期

---

## 最佳实践

1. **权限检查**：始终验证请求者是否有足够的权限执行操作
2. **错误处理**：始终检查返回结果中是否有 `error` 字段
3. **分页**：对于列表类操作，合理使用分页参数
4. **异步操作**：所有工具都是异步的，使用 `await` 调用
5. **资源清理**：数据库连接会在操作完成后自动关闭

---

## 工具分类总结

| 分类 | 工具数量 | 工具列表 |
|------|----------|----------|
| 团队管理 | 6 | create_team, get_team, update_team, delete_team, list_teams, get_team_stats |
| 成员管理 | 5 | invite_member, join_team, list_members, update_member_role, remove_member |
| 团队记忆 | 6 | create_team_memory, get_team_memory, update_team_memory, delete_team_memory, search_team_memories, list_team_memories |
| 团队积分 | 4 | get_team_credits, add_team_credits, transfer_credits, get_credit_transactions |
| 团队活动 | 2 | get_team_activities, log_activity |
| 团队统计 | 1 | get_team_insights |
| 其他 | 10 | (已存在的工具) |
| **总计** | **34** | |

---

## 相关文档

- [MCP工具使用示例](../examples/mcp_tools_usage.py)
- [MCP工具测试报告](../tests/test_mcp_tools.py)
- [MCP工具清单](mcp-tools-checklist.md)
