# 细粒度权限系统指南

## 目录
1. [权限模型概述](#权限模型概述)
2. [权限检查机制](#权限检查机制)
3. [权限配置指南](#权限配置指南)
4. [API 使用示例](#api-使用示例)
5. [装饰器使用指南](#装饰器使用指南)
6. [最佳实践](#最佳实践)
7. [性能优化](#性能优化)
8. [故障排查](#故障排查)

---

## 权限模型概述

### 核心概念

细粒度权限系统支持以下维度的权限控制：

#### 1. 权限粒度

- **操作级权限**: 控制单个操作的权限
  - 示例: `memory.create`, `memory.view`, `memory.delete`, `team.admin`
  
- **资源级权限**: 控制特定资源的权限
  - 示例: 用户只能查看特定记忆 `memory_id: mem_123` 的内容

- **角色权限**: 通过角色批量授予权限
  - 示例: `admin`, `moderator`, `member`

#### 2. 权限继承

- **角色继承**: 角色可以从其他角色继承权限
  - 示例: `team_admin` 继承 `team_member` 的所有权限

#### 3. 权限组合

- **任意权限**: 拥有列表中的任意一个权限即可
- **所有权限**: 必须拥有列表中的所有权限

### 数据模型

#### Permission 表

定义所有可用的权限：

```python
class Permission(Base):
    permission_id: str          # 权限ID
    code: str                  # 权限代码（唯一）
    name: str                  # 权限名称
    description: str           # 权限描述
    category: str              # 分类：memory/team/user/system
    level: str                 # 层级：operation/resource/system
    resource_type: str         # 资源类型（可选）
    is_system: bool            # 是否系统内置权限
    is_active: bool            # 是否激活
```

#### Role 表

定义角色：

```python
class Role(Base):
    role_id: str               # 角色ID
    code: str                  # 角色代码（唯一）
    name: str                  # 角色名称
    description: str           # 角色描述
    category: str              # 分类：system/platform/team
    level: int                 # 角色级别
    inherit_from_id: str      # 继承自哪个角色
    is_system: bool            # 是否系统内置角色
    member_count: int          # 拥有此角色的用户数
```

#### RolePermission 表

角色-权限关系：

```python
class RolePermission(Base):
    role_id: str               # 角色ID
    permission_id: str         # 权限ID
    conditions: dict           # 条件限制（可选）
```

#### UserPermission 表

用户-权限关系：

```python
class UserPermission(Base):
    agent_id: str              # 用户ID
    permission_id: str         # 权限ID
    grant_type: str            # 授权类型：allow/deny
    scope: dict                # 权限范围（可选）
    expires_at: datetime       # 过期时间（可选）
```

#### ResourcePermission 表

资源-权限关系：

```python
class ResourcePermission(Base):
    resource_type: str         # 资源类型：memory/team/agent/transaction
    resource_id: str           # 资源ID
    agent_id: str              # 授权给哪个用户（可选）
    role_id: str               # 授权给哪个角色（可选）
    permission_code: str       # 权限代码
    grant_type: str            # 授权类型：allow/deny
    conditions: dict           # 权限条件（可选）
    expires_at: datetime       # 过期时间（可选）
```

### 预定义权限

系统内置以下权限：

#### 记忆权限
- `memory.create` - 创建记忆
- `memory.view` - 查看记忆
- `memory.edit` - 编辑记忆
- `memory.delete` - 删除记忆
- `memory.purchase` - 购买记忆
- `memory.export` - 导出记忆
- `memory.permission.grant` - 授予记忆权限
- `memory.permission.revoke` - 撤销记忆权限

#### 团队权限
- `team.create` - 创建团队
- `team.view` - 查看团队
- `team.edit` - 编辑团队
- `team.delete` - 删除团队
- `team.invite` - 邀请成员
- `team.remove` - 移除成员
- `team.admin` - 团队管理
- `team.permission.grant` - 授予团队权限
- `team.permission.revoke` - 撤销团队权限

#### 系统权限
- `system.user.create` - 创建用户
- `system.user.grant` - 授予用户权限
- `system.user.revoke` - 撤销用户权限
- `system.role.create` - 创建角色
- `system.role.grant` - 授予角色权限
- `system.role.revoke` - 撤销角色权限
- `system.permission.create` - 创建权限
- `system.audit.view` - 查看审计日志

---

## 权限检查机制

### 检查流程

权限检查按照以下优先级顺序进行：

1. **用户级拒绝权限** (Deny 优先级最高)
   - 如果用户有明确的拒绝权限，直接返回 False

2. **用户级允许权限**
   - 检查用户是否有该权限的直接授权

3. **角色权限**
   - 检查用户所属角色的权限（包括继承的角色）

4. **资源级权限**
   - 检查是否有特定资源的权限授权

### 权限范围检查

当检查资源级权限时，系统会验证：

```python
# 示例：用户只能查看特定记忆
scope = {
    "memory_ids": ["mem_123", "mem_456"],  # 允许的记忆ID列表
    "team_ids": ["team_abc"]              # 允许的团队ID列表
}
```

### 缓存机制

- **Redis 缓存**: 用户权限缓存，TTL 1 小时
- **缓存失效**: 权限变更时自动清除相关缓存
- **性能目标**: 权限检查延迟 <5ms

---

## 权限配置指南

### 创建权限

```python
from app.models.tables import Permission

permission = Permission(
    code="memory.share",
    name="分享记忆",
    description="分享记忆给其他用户",
    category="memory",
    level="operation"
)
db.add(permission)
await db.commit()
```

### 创建角色

```python
from app.models.tables import Role

role = Role(
    code="team_contributor",
    name="团队贡献者",
    description="可以贡献内容但不能管理团队",
    category="team",
    level=1,
    inherit_from_id="team_member"  # 继承团队成员
)
db.add(role)
await db.commit()
```

### 授予角色权限

```python
from app.models.tables import RolePermission

role_perm = RolePermission(
    role_id=role.role_id,
    permission_id=permission.permission_id,
    conditions={"max_count": 10}
)
db.add(role_perm)
await db.commit()
```

### 授予用户权限

```python
from app.services.permission_service import PermissionService

service = PermissionService(db)
await service.grant_permission(
    agent_id=user.agent_id,
    permission_code="memory.create",
    grant_type="allow",
    scope={"memory_ids": ["mem_123"]},  # 可选：限制范围
    expires_at=datetime.now() + timedelta(days=30),  # 可选：过期时间
    actor_agent_id=admin.agent_id
)
```

### 授予资源权限

```python
await service.grant_resource_permission(
    resource_type="memory",
    resource_id="mem_123",
    permission_code="memory.view",
    agent_id=user.agent_id,
    conditions={"max_views": 100},
    expires_at=datetime.now() + timedelta(days=7)
)
```

---

## API 使用示例

### 获取权限列表

```bash
GET /permissions?category=memory&is_active=true
```

响应：
```json
{
  "permission_id": "perm_xxx",
  "code": "memory.create",
  "name": "创建记忆",
  "description": "创建新的记忆",
  "category": "memory",
  "level": "operation",
  "resource_type": null,
  "is_system": false,
  "is_active": true,
  "created_at": "2024-03-23T10:00:00Z"
}
```

### 获取用户权限

```bash
GET /permissions/users/{user_id}
```

响应：
```json
{
  "agent_id": "agent_123",
  "permissions": [
    {
      "type": "user",
      "grant_type": "allow",
      "code": "memory.create",
      "name": "创建记忆",
      "category": "memory",
      "scope": null,
      "expires_at": null
    },
    {
      "type": "role",
      "code": "team.member",
      "name": "团队成员",
      "category": "team",
      "role_name": "团队成员"
    }
  ]
}
```

### 授予用户权限

```bash
POST /permissions/users/{user_id}
Content-Type: application/json

{
  "permission_code": "memory.create",
  "grant_type": "allow",
  "scope": {
    "memory_ids": ["mem_123"]
  },
  "expires_days": 30
}
```

### 撤销用户权限

```bash
DELETE /permissions/users/{user_id}/{permission_code}
```

### 获取角色权限

```bash
GET /permissions/roles/{role_id}/permissions
```

### 授予角色权限

```bash
POST /permissions/roles/{role_id}/permissions
Content-Type: application/json

{
  "permission_id": "perm_xxx",
  "conditions": {
    "max_count": 10
  }
}
```

### 获取资源权限

```bash
GET /resource-permissions/memories/{memory_id}
```

响应：
```json
{
  "memory_id": "mem_123",
  "title": "测试记忆",
  "permissions": [
    {
      "id": 1,
      "permission_code": "memory.view",
      "agent_id": "agent_456",
      "role_id": null,
      "grant_type": "allow",
      "conditions": null,
      "expires_at": "2024-04-23T10:00:00Z",
      "created_at": "2024-03-23T10:00:00Z"
    }
  ]
}
```

### 授予资源权限

```bash
POST /resource-permissions/memories/{memory_id}
Content-Type: application/json

{
  "permission_code": "memory.view",
  "agent_id": "agent_456",
  "conditions": {
    "max_views": 100
  },
  "expires_days": 7
}
```

### 撤销资源权限

```bash
DELETE /resource-permissions/memories/{memory_id}/{permission_code}?agent_id={agent_id}
```

---

## 装饰器使用指南

### require_permission

要求特定权限：

```python
from fastapi import APIRouter
from app.api.permission_decorators import require_permission

router = APIRouter()

@router.post("/memories")
@require_permission("memory.create")
async def create_memory(request, db: AsyncSession = Depends(get_db)):
    # 只有拥有 memory.create 权限的用户才能访问
    pass
```

### require_any_permission

要求任意一个权限：

```python
@require_any_permission(["memory.edit", "memory.delete"])
async def modify_or_delete_memory(request, db: AsyncSession = Depends(get_db)):
    # 拥有 memory.edit 或 memory.delete 任一权限即可
    pass
```

### require_all_permissions

要求所有权限：

```python
@require_all_permissions(["memory.create", "team.member"])
async def create_team_memory(request, db: AsyncSession = Depends(get_db)):
    # 必须同时拥有 memory.create 和 team.member 权限
    pass
```

### require_resource_permission

要求资源级权限：

```python
@require_resource_permission("memory.view", "memory_type", "memory_id")
async def view_memory(
    memory_id: str,
    memory_type: str = "memory",
    request,
    db: AsyncSession = Depends(get_db)
):
    # 检查是否有对指定记忆的查看权限
    pass
```

### optional_permission

可选权限（不强制要求）：

```python
@optional_permission("memory.delete", raise_on_missing=False)
async def delete_memory(request, db: AsyncSession = Depends(get_db)):
    agent_id = request.state.agent_id
    has_perm = request.state.has_permission
    
    if has_perm:
        # 可以删除任何记忆
        pass
    else:
        # 只能删除自己的记忆
        pass
```

### 依赖注入方式

获取当前用户权限：

```python
@router.get("/permissions")
async def list_my_permissions(
    permissions: List[dict] = Depends(get_current_user_permissions)
):
    return {"permissions": permissions}
```

检查权限：

```python
@router.get("/check")
async def check_perm(
    has_perm: bool = Depends(lambda r, db: check_permission("memory.view", r, db))
):
    return {"has_permission": has_perm}
```

---

## 最佳实践

### 1. 权限设计原则

- **最小权限原则**: 用户只拥有完成工作所需的最小权限
- **职责分离**: 不同职责使用不同权限
- **权限分层**: 系统权限 > 平台权限 > 业务权限

### 2. 权限命名规范

```
{资源}.{操作}.{子操作}
```

示例：
- `memory.create` - 创建记忆
- `memory.view.own` - 查看自己的记忆
- `memory.view.all` - 查看所有记忆
- `team.member.invite` - 邀请团队成员

### 3. 权限缓存策略

- **读多写少**: 权限检查频繁，变更较少，适合缓存
- **TTL 设置**: 1 小时，平衡性能和一致性
- **主动失效**: 权限变更时主动清除缓存

### 4. 审计日志

记录所有权限操作：

- 权限授予/撤销
- 权限检查结果
- 操作者和操作时间

### 5. 错误处理

```python
try:
    has_perm = await perm_service.has_permission(
        agent_id=user_id,
        permission_code="memory.create"
    )
    if not has_perm:
        raise HTTPException(status_code=403, detail="权限不足")
except Exception as e:
    # 记录错误日志
    logger.error(f"权限检查失败: {e}")
    raise
```

---

## 性能优化

### 1. 索引优化

已创建以下索引：

```sql
-- 权限表索引
CREATE INDEX idx_permissions_code ON permissions(code);
CREATE INDEX idx_permissions_category ON permissions(category);

-- 用户权限表索引
CREATE INDEX idx_user_permissions_agent ON user_permissions(agent_id);
CREATE INDEX idx_user_permissions_agent_active ON user_permissions(agent_id, expires_at);

-- 角色权限表索引
CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);

-- 资源权限表索引
CREATE INDEX idx_resource_permissions_resource ON resource_permissions(resource_type, resource_id);
CREATE INDEX idx_resource_permissions_agent ON resource_permissions(agent_id);
```

### 2. 缓存策略

```python
# Redis 缓存键设计
USER_PERM_KEY = "permissions:{agent_id}"
ROLE_PERM_KEY = "role_permissions:{role_id}"

# 缓存 TTL
CACHE_TTL = 3600  # 1 小时
```

### 3. 批量查询

避免循环查询，使用批量查询：

```python
# 错误示例
for perm_id in perm_ids:
    perm = await db.get(Permission, perm_id)

# 正确示例
query = select(Permission).where(Permission.permission_id.in_(perm_ids))
perms = await db.execute(query)
```

### 4. 性能目标

- 权限检查延迟: <5ms
- 缓存命中率: >80%
- 支持 1000+ 权限规则

---

## 故障排查

### 问题 1: 权限检查结果不符合预期

**可能原因:**
1. 缓存未失效
2. 权限配置错误
3. 拒绝权限优先

**解决方法:**
```python
# 清除缓存
await redis.delete(f"permissions:{agent_id}")

# 检查权限配置
perms = await perm_service.get_user_permissions(agent_id)
print(perms)

# 检查是否有拒绝权限
deny_perms = await db.execute(
    select(UserPermission).where(
        UserPermission.agent_id == agent_id,
        UserPermission.grant_type == "deny"
    )
)
```

### 问题 2: 性能问题

**可能原因:**
1. 缓存命中率低
2. 数据库查询慢
3. 未使用索引

**解决方法:**
```python
# 检查缓存命中率
cache_stats = await redis.info("stats")
print(f"缓存命中率: {cache_stats['keyspace_hits'] / cache_stats['keyspace_hits'] + cache_stats['keyspace_misses']}")

# 查看慢查询
# 使用 EXPLAIN ANALYZE 分析查询计划
```

### 问题 3: 权限过期不生效

**可能原因:**
1. 过期时间未正确设置
2. 时区问题

**解决方法:**
```python
# 使用 UTC 时间
from datetime import datetime, timedelta, timezone
expires_at = datetime.now(timezone.utc) + timedelta(days=30)

# 或使用本地时间
expires_at = datetime.now() + timedelta(days=30)
```

### 问题 4: 资源权限检查失败

**可能原因:**
1. 资源ID错误
2. 权限代码错误
3. 范围限制不匹配

**解决方法:**
```python
# 检查资源权限
query = select(ResourcePermission).where(
    and_(
        ResourcePermission.resource_type == "memory",
        ResourcePermission.resource_id == memory_id,
        ResourcePermission.agent_id == agent_id
    )
)
```

---

## 总结

细粒度权限系统提供了灵活、高性能的权限控制能力。通过合理配置权限、使用装饰器和API，可以实现各种复杂的权限管理场景。

**关键特性:**
- ✅ 操作级权限控制
- ✅ 资源级权限控制
- ✅ 角色权限继承
- ✅ 权限组合（任意/所有）
- ✅ 权限范围限制
- ✅ 权限过期机制
- ✅ Redis 缓存优化
- ✅ 审计日志记录
- ✅ 高性能（<5ms）

**使用建议:**
1. 遵循最小权限原则
2. 合理设计权限粒度
3. 充分利用角色和继承
4. 启用缓存提升性能
5. 记录审计日志追踪变更

如有问题，请参考测试文件 `tests/test_permissions.py` 中的示例。
