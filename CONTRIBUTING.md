# 贡献指南 | Contributing Guide

感谢你对 **Agent 记忆市场** 项目的关注！我们欢迎各种形式的贡献。

Thanks for your interest in contributing to **Agent Memory Market**! We welcome all forms of contributions.

---

## 📋 目录 | Table of Contents

- [如何贡献](#-如何贡献--how-to-contribute)
- [开发环境搭建](#-开发环境搭建--development-setup)
- [代码规范](#-代码规范--code-standards)
- [测试指南](#-测试指南--testing-guidelines)
- [提交流程](#-提交流程--submission-workflow)
- [文档贡献](#-文档贡献--documentation-contributions)

---

## 🤝 如何贡献 | How to Contribute

### 报告 Bug | Report Bugs

如果你发现了 Bug，请：

If you found a bug, please:

1. 在 [Issues](https://github.com/Timluogit/memory-market/issues) 中搜索是否已存在相同问题
   Search if the issue already exists in [Issues](https://github.com/Timluogit/memory-market/issues)
2. 如果没有，创建新的 Issue，使用下面的 Bug 报告模板：
   If not, create a new issue using the bug report template below:

   ```markdown
   ### Bug 描述 | Bug Description
   简洁清晰的问题描述

   ### 复现步骤 | Reproduction Steps
   1. 步骤一
   2. 步骤二
   3. 步骤三

   ### 预期行为 | Expected Behavior
   描述你期望发生什么

   ### 实际行为 | Actual Behavior
   描述实际发生了什么

   ### 环境信息 | Environment
   - OS: [例如 macOS 14.0]
   - Python 版本: [例如 3.11.5]
   - 项目版本: [例如 v0.1.0]

   ### 日志/截图 | Logs/Screenshots
   ```
   - Clear title | 清晰的标题
   - Detailed reproduction steps | 详细的复现步骤
   - Expected and actual behavior | 预期行为和实际行为
   - Environment info (Python version, OS, etc.) | 环境信息（Python 版本、操作系统等）
   - Error logs or screenshots | 错误日志或截图

### 提出新功能 | Suggest Features

我们欢迎功能建议！请创建一个 Issue 并使用功能请求模板：

We welcome feature suggestions! Please create an issue using the feature request template:

```markdown
### 功能描述 | Feature Description
简洁的功能描述

### 动机 | Motivation
为什么需要这个功能？它解决了什么问题？

### 建议的解决方案 | Proposed Solution
详细描述你希望实现的功能

### 替代方案 | Alternatives
描述你考虑过的其他替代解决方案

### 附加信息 | Additional Context
截图、示例代码或其他相关资料
```

- Feature description and use cases | 功能描述和使用场景
- Why this feature is valuable | 为什么这个功能对项目有价值
- Possible implementation approach (if any) | 可能的实现方案（如果有）

### 提交代码 | Submit Code

---

## 🔧 开发环境搭建 | Development Setup

### 前置要求 | Prerequisites

- Python 3.11 或更高版本 | Python 3.11 or higher
- Git | Git
- Docker 和 Docker Compose（可选，用于容器化部署） | Docker and Docker Compose (optional)

### 1. Fork 并克隆仓库 | Fork and Clone

```bash
# 1. 在 GitHub 上 Fork 本仓库
# Fork the repository on GitHub

# 2. 克隆你的 Fork
# Clone your fork
git clone https://github.com/YOUR_USERNAME/memory-market.git
cd memory-market

# 3. 添加上游远程仓库
# Add upstream remote
git remote add upstream https://github.com/Timluogit/memory-market.git
```

### 2. 创建虚拟环境 | Create Virtual Environment

```bash
# 创建虚拟环境 | Create virtual environment
python3.11 -m venv venv

# 激活虚拟环境 | Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

### 3. 安装依赖 | Install Dependencies

```bash
# 升级 pip | Upgrade pip
pip install --upgrade pip

# 安装项目依赖（开发模式）
# Install project dependencies (editable mode)
pip install -e .

# 安装开发依赖
# Install development dependencies
pip install -e ".[dev]"
```

**依赖说明 | Dependencies Explained:**

```bash
# 核心依赖 | Core dependencies
fastapi==0.115.0          # Web 框架
uvicorn==0.30.0           # ASGI 服务器
pydantic==2.9.0           # 数据验证
sqlalchemy==2.0.35        # ORM
aiosqlite==0.20.0         # 异步 SQLite
httpx==0.27.0             # HTTP 客户端
qdrant-client>=1.12.0     # 向量数据库客户端
mcp>=1.0.0               # MCP 协议支持

# 开发依赖 | Dev dependencies
pytest>=7.0              # 测试框架
pytest-asyncio>=0.21     # 异步测试支持
black>=23.0              # 代码格式化
ruff>=0.1.0              # 代码检查
mypy>=1.0.0              # 类型检查
```

### 4. 配置环境变量 | Configure Environment Variables

创建 `.env` 文件：

Create `.env` file:

```bash
# 复制示例配置文件
# Copy example config
cp .env.example .env

# 编辑配置
# Edit configuration
nano .env  # 或使用你喜欢的编辑器
```

`.env` 文件内容：

```bash
# API 配置 | API Configuration
API_KEY=sk_test_your_api_key_here
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True

# 数据库配置 | Database Configuration
DATABASE_URL=sqlite+aiosqlite:///./data/memory_market.db

# Qdrant 配置（可选）| Qdrant Configuration (optional)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=memory_market

# 日志配置 | Logging Configuration
LOG_LEVEL=INFO
```

### 5. 初始化数据库 | Initialize Database

```bash
# 创建数据目录
# Create data directory
mkdir -p data

# 运行数据库迁移
# Run database migrations
python -m app.db.database

# 导入种子数据（可选）
# Import seed data (optional)
python scripts/seed_all_categories.py
python scripts/seed_more_memories.py
```

### 6. 启动开发服务器 | Start Development Server

```bash
# 方式 1: 直接运行
# Method 1: Direct run
python -m app.main

# 方式 2: 使用 uvicorn
# Method 2: Using uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式 3: 使用 Docker
# Method 3: Using Docker
docker-compose up -d
```

访问：
- Web UI: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 交互式文档: http://localhost:8000/redoc

### 7. 验证安装 | Verify Installation

```bash
# 运行测试
# Run tests
pytest tests/ -v

# 测试 API 连接
# Test API connection
curl http://localhost:8000/api/v1/health

# 测试 MCP Server
# Test MCP Server
python -m app.mcp.server
```

---

## 🏗️ 项目结构 | Project Structure

```
memory-market/
├── app/
│   ├── api/                    # API 路由
│   │   ├── routes.py          # 核心 API 端点
│   │   └── transactions.py    # 交易相关 API
│   ├── core/                   # 核心配置
│   │   ├── config.py          # 配置管理
│   │   ├── auth.py            # 认证逻辑
│   │   └── exceptions.py      # 自定义异常
│   ├── db/                     # 数据库
│   │   └── database.py        # 数据库连接
│   ├── models/                 # 数据模型
│   │   ├── schemas.py         # Pydantic 模型
│   │   └── tables.py          # SQLAlchemy 表
│   ├── services/               # 业务逻辑
│   │   ├── agent_service.py   # Agent 服务
│   │   └── memory_service.py  # 记忆服务
│   ├── search/                 # 搜索模块
│   │   ├── semantic.py        # 语义搜索
│   │   ├── keyword.py         # 关键词搜索
│   │   └── hybrid.py          # 混合搜索
│   ├── mcp/                    # MCP Server
│   │   └── server.py          # MCP 协议实现
│   ├── static/                 # 前端资源
│   └── main.py                # 应用入口
│
├── memory_market/             # SDK & CLI
│   ├── __init__.py
│   ├── client.py              # SDK 客户端
│   └── cli.py                 # CLI 命令行
│
├── scripts/                   # 工具脚本
│   ├── seed_memories.py       # 导入种子数据
│   ├── install.sh             # 一键安装脚本
│   └── start.sh               # 启动脚本
│
├── tests/                     # 测试
│   ├── test_api.py
│   ├── test_search.py
│   └── test_sdk.py
│
├── docs/                      # 文档
│   ├── SEMANTIC_SEARCH.md
│   └── SCREENSHOTS.md         # 截图说明
│
├── pyproject.toml             # 项目配置
├── requirements.txt           # 依赖列表
├── Dockerfile                 # Docker 镜像
├── docker-compose.yml         # Docker Compose
├── .env.example               # 环境变量示例
├── README.md                  # 项目说明
└── CONTRIBUTING.md            # 贡献指南
```

---

## 📝 开发工作流 | Development Workflow

### 1. 创建分支 | Create Branch

```bash
# 从 main 创建新分支
# Create new branch from main
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name

# 或创建修复分支
# Or create fix branch
git checkout -b fix/your-bug-fix
```

**分支命名规范 | Branch Naming Convention:**

- `feature/` - 新功能 | New features
  - 示例：`feature/semantic-search`
- `fix/` - Bug 修复 | Bug fixes
  - 示例：`fix/purchase-race-condition`
- `docs/` - 文档更新 | Documentation updates
  - 示例：`docs/api-reference`
- `refactor/` - 代码重构 | Code refactoring
  - 示例：`refactor/search-service`
- `test/` - 测试相关 | Test related
  - 示例：`test/add-integration-tests`
- `chore/` - 构建/工具 | Build/tool related
  - 示例：`chore/update-dependencies`

### 2. 编写代码 | Write Code

请遵循以下代码规范：

Please follow these code standards:

- **Python 风格 | Python Style**: 使用 [Black](https://github.com/psf/black) 格式化代码
  ```bash
  # 格式化所有代码
  # Format all code
  black app/ tests/ memory_market/

  # 检查格式（不修改文件）
  # Check format (don't modify files)
  black --check app/ tests/
  ```

- **代码质量 | Code Quality**: 使用 [Ruff](https://docs.astral.sh/ruff/) 检查
  ```bash
  # 检查代码问题
  # Check code issues
  ruff check app/ tests/

  # 自动修复问题
  # Auto-fix issues
  ruff check --fix app/ tests/
  ```

- **类型检查 | Type Checking**: 使用 [MyPy](https://mypy-lang.org/)
  ```bash
  # 类型检查
  # Type checking
  mypy app/
  ```

- **导入排序 | Import Sorting**: Ruff 自动处理
  ```bash
  ruff check --select I --fix app/
  ```

### 3. 运行测试 | Run Tests

```bash
# 运行所有测试
# Run all tests
pytest tests/ -v

# 运行特定测试文件
# Run specific test file
pytest tests/test_search.py -v

# 运行特定测试
# Run specific test
pytest tests/test_search.py::test_semantic_search -v

# 显示测试覆盖率
# Show test coverage
pytest --cov=app --cov-report=html tests/

# 运行集成测试
# Run integration tests
pytest tests/ -m integration

# 运行单元测试
# Run unit tests
pytest tests/ -m unit
```

### 4. 提交更改 | Commit Changes

```bash
# 查看修改
# View changes
git status
git diff

# 暂存文件
# Stage files
git add path/to/file.py
# 或暂存所有修改
# Or stage all changes
git add .

# 提交
# Commit
git commit -m "feat: add semantic search with Qdrant"
```

**提交信息格式 | Commit Message Format:**

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

Follow [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 | Types:**
- `feat`: 新功能 | New feature
- `fix`: Bug 修复 | Bug fix
- `docs`: 文档更新 | Documentation update
- `style`: 代码格式调整 | Code style changes
- `refactor`: 代码重构 | Code refactoring
- `test`: 测试相关 | Test related
- `chore`: 构建/工具相关 | Build/tool related
- `perf`: 性能优化 | Performance improvement

**示例 | Examples:**

```bash
# 简单提交
# Simple commit
git commit -m "fix: resolve memory purchase race condition"

# 带范围的提交
# Commit with scope
git commit -m "feat(search): add hybrid search combining semantic and keyword"

# 详细提交
# Detailed commit
git commit -m "feat(api): add memory version control

- Add version tracking to memories table
- Create /memories/{id}/versions endpoint
- Support version comparison and rollback

Closes #123"
```

### 5. 推送到 Fork | Push to Fork

```bash
# 推送分支
# Push branch
git push origin feature/your-feature-name

# 或设置上游分支（首次推送）
# Or set upstream (first push)
git push -u origin feature/your-feature-name
```

### 6. 创建 Pull Request | Create Pull Request

1. 访问原始仓库的 Pull Requests 页面
   Visit the original repository's Pull Requests page
   ```
   https://github.com/Timluogit/memory-market/pulls
   ```

2. 点击 "New Pull Request"
   Click "New Pull Request"

3. 选择你的分支 | Select your branch
   - Click "Compare across forks"
   - Select your fork and branch

4. 填写 PR 描述模板 | Fill in the PR description template

5. 等待 CI 检查通过 | Wait for CI checks to pass

6. 等待代码审查 | Wait for code review

### 7. 更新 PR | Update PR

根据审查意见修改代码：

Update your code based on review feedback:

```bash
# 修改代码后提交
# Commit after making changes
git add .
git commit -m "fix: address review comments"

# 推送到同一分支
# Push to same branch
git push origin feature/your-feature-name
```

### 8. 保持 Fork 同步 | Keep Fork Synced

定期同步上游仓库：

Keep your fork synced with upstream regularly:

```bash
# 获取上游更新
# Fetch upstream changes
git fetch upstream

# 合并到你的分支
# Merge into your branch
git checkout feature/your-feature-name
git merge upstream/main

# 推送更新
# Push updates
git push origin feature/your-feature-name
```

---

## 🎨 代码规范 | Code Standards

### Python 代码风格 | Python Code Style

遵循 PEP 8 规范，使用 Black 自动格式化：

Follow PEP 8, use Black for auto-formatting:

```python
# ✅ 好的示例 | Good example
from typing import Optional, List
from datetime import datetime

async def get_memory(
    memory_id: str,
    include_purchased: bool = False,
    include_version: bool = False
) -> Optional[dict]:
    """
    获取记忆详情 | Get memory details

    Args:
        memory_id: 记忆 ID | Memory ID
        include_purchased: 是否包含购买信息 | Include purchase info
        include_version: 是否包含版本信息 | Include version info

    Returns:
        记忆数据或 None | Memory data or None

    Raises:
        MemoryNotFoundError: 记忆不存在 | Memory not found
    """
    if not memory_id:
        raise ValueError("memory_id 不能为空 | memory_id cannot be empty")

    # 实现代码 | Implementation
    pass

# ❌ 避免这样的代码 | Avoid this
async def getMemory(memoryID, purchased=False):
    # 缺少类型注解
    # 没有文档字符串
    # 变量命名不规范
    pass
```

### 文档字符串 | Docstrings

使用 Google 风格的文档字符串：

Use Google-style docstrings:

```python
def search_memories(
    query: str,
    category: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 20
) -> List[MemorySchema]:
    """搜索记忆 | Search memories

    Args:
        query: 搜索关键词 | Search query
        category: 分类筛选 | Category filter (optional)
        min_score: 最低评分 | Minimum score (default: 0.0)
        limit: 返回数量限制 | Result limit (default: 20)

    Returns:
        匹配的记忆列表 | List of matching memories

    Raises:
        APIError: API 调用失败 | API call failed

    Examples:
        >>> search_memories("爆款", category="抖音", limit=10)
        [MemorySchema(...), ...]
    """
    pass
```

### 错误处理 | Error Handling

```python
# ✅ 好的错误处理 | Good error handling
from app.core.exceptions import AppError

async def purchase_memory(memory_id: str, agent_id: str):
    """购买记忆 | Purchase memory"""
    # 验证输入
    # Validate input
    if not memory_id or not agent_id:
        raise AppError(
            code="INVALID_INPUT",
            message="记忆 ID 和 Agent ID 不能为空 | IDs cannot be empty",
            status_code=400
        )

    # 检查记忆是否存在
    # Check if memory exists
    memory = await get_memory(memory_id)
    if not memory:
        raise AppError(
            code="MEMORY_NOT_FOUND",
            message=f"记忆 {memory_id} 不存在 | Memory not found",
            status_code=404
        )

    # 检查余额
    # Check balance
    agent = await get_agent(agent_id)
    if agent.credits < memory.price:
        raise AppError(
            code="INSUFFICIENT_BALANCE",
            message=f"积分不足，需要 {memory.price}，当前 {agent.credits}",
            status_code=402
        )

    # 继续处理
    # Continue processing
    return await complete_purchase(memory_id, agent_id)

# ❌ 避免这样的错误处理 | Avoid this
async def purchase_memory(memory_id, agent_id):
    # 没有输入验证
    # 使用裸 except
    try:
        # ...
        pass
    except:
        pass  # 不要这样做！
```

### 类型注解 | Type Annotations

所有函数都应该有类型注解：

All functions should have type annotations:

```python
# ✅ 有类型注解 | With type annotations
from typing import List, Dict, Optional

def filter_memories(
    memories: List[Dict],
    min_score: float,
    platform: Optional[str] = None
) -> List[Dict]:
    """过滤记忆 | Filter memories"""
    result = []
    for m in memories:
        if m['score'] >= min_score:
            if platform is None or m['platform'] == platform:
                result.append(m)
    return result

# ❌ 没有类型注解 | Without type annotations
def filter_memories(memories, min_score, platform=None):
    # 不清楚参数和返回值类型
    pass
```

### 异步编程 | Async Programming

```python
# ✅ 好的异步模式 | Good async pattern
async def process_batch(memory_ids: List[str]) -> List[dict]:
    """批量处理记忆 | Process memories in batch"""
    # 并发获取
    # Fetch concurrently
    tasks = [get_memory(mid) for mid in memory_ids]
    memories = await asyncio.gather(*tasks, return_exceptions=True)

    # 过滤错误
    # Filter errors
    results = []
    for i, m in enumerate(memories):
        if isinstance(m, Exception):
            logger.error(f"获取记忆 {memory_ids[i]} 失败: {m}")
        elif m:
            results.append(m)

    return results

# ❌ 避免串行等待 | Avoid serial waiting
async def process_batch(memory_ids):
    # 不要这样做！
    # Don't do this!
    results = []
    for mid in memory_ids:
        m = await get_memory(mid)  # 串行执行
        results.append(m)
    return results
```

---

## 🧪 测试指南 | Testing Guidelines

### 测试结构 | Test Structure

```
tests/
├── unit/                      # 单元测试
│   ├── test_models.py         # 模型测试
│   ├── test_services/         # 服务测试
│   │   ├── test_agent_service.py
│   │   └── test_memory_service.py
│   └── test_search/           # 搜索测试
│       ├── test_semantic.py
│       ├── test_keyword.py
│       └── test_hybrid.py
│
├── integration/               # 集成测试
│   ├── test_api.py           # API 测试
│   ├── test_mcp.py           # MCP 测试
│   └── test_transactions.py  # 交易流程测试
│
├── conftest.py               # pytest 配置
└── fixtures.py               # 测试固件
```

### 编写测试 | Writing Tests

```python
# tests/unit/test_memory_service.py
import pytest
from app.services.memory_service import MemoryService
from app.models.schemas import MemoryCreate

class TestMemoryService:
    """记忆服务测试 | Memory service tests"""

    @pytest.fixture
    async def memory_service(self, db_session):
        """创建服务实例 | Create service instance"""
        return MemoryService(db_session)

    @pytest.fixture
    def sample_memory(self):
        """示例记忆数据 | Sample memory data"""
        return MemoryCreate(
            title="测试记忆",
            content="测试内容",
            category="测试/分类",
            platform="通用",
            price=100
        )

    @pytest.mark.asyncio
    async def test_create_memory(self, memory_service, sample_memory):
        """测试创建记忆 | Test creating memory"""
        result = await memory_service.create(sample_memory)

        assert result.id is not None
        assert result.title == sample_memory.title
        assert result.price == sample_memory.price

    @pytest.mark.asyncio
    async def test_search_memories(self, memory_service):
        """测试搜索记忆 | Test searching memories"""
        # 创建测试数据
        # Create test data
        await memory_service.create(sample_memory)

        # 搜索
        # Search
        results = await memory_service.search(
            query="测试",
            limit=10
        )

        assert len(results) > 0
        assert results[0].title == "测试记忆"

    @pytest.mark.asyncio
    async def test_purchase_memory_insufficient_balance(self, memory_service):
        """测试积分不足购买 | Test purchase with insufficient balance"""
        with pytest.raises(AppError) as exc_info:
            await memory_service.purchase(
                memory_id="mem_xxx",
                agent_id="agent_xxx"
            )

        assert exc_info.value.code == "INSUFFICIENT_BALANCE"
        assert exc_info.value.status_code == 402
```

### API 集成测试 | API Integration Tests

```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
class TestMemoryAPI:
    """记忆 API 测试 | Memory API tests"""

    async def test_search_memories(self, async_client: AsyncClient):
        """测试搜索 API | Test search API"""
        response = await async_client.get(
            "/api/v1/memories",
            params={
                "keyword": "爆款",
                "platform": "抖音"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_purchase_memory(self, async_client: AsyncClient, api_key: str):
        """测试购买 API | Test purchase API"""
        # 先创建记忆
        # First create memory
        memory = await async_client.post(
            "/api/v1/memories",
            json={...},
            headers={"X-API-Key": api_key}
        )

        memory_id = memory.json()["data"]["id"]

        # 购买
        # Purchase
        response = await async_client.post(
            f"/api/v1/memories/{memory_id}/purchase",
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["purchased"] is True
```

### 使用 Fixtures | Using Fixtures

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.main import app
from app.db.database import get_db
from app.models.tables import Base

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 | Create event loop"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session():
    """创建测试数据库会话 | Create test DB session"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = AsyncSession(engine)
    yield async_session

    await async_session.close()
    await engine.dispose()

@pytest.fixture
async def async_client(db_session):
    """创建异步测试客户端 | Create async test client"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

@pytest.fixture
def api_key():
    """提供测试 API Key | Provide test API key"""
    return "sk_test_demo_key_999999"
```

### 运行测试 | Running Tests

```bash
# 运行所有测试
# Run all tests
pytest tests/ -v

# 运行特定测试
# Run specific test
pytest tests/test_search.py::test_semantic_search -v

# 运行标记的测试
# Run marked tests
pytest tests/ -m integration -v

# 生成覆盖率报告
# Generate coverage report
pytest --cov=app --cov-report=html tests/

# 并行运行测试（需要 pytest-xdist）
# Run tests in parallel (requires pytest-xdist)
pytest tests/ -n auto

# 显示打印输出
# Show print output
pytest tests/ -s

# 在第一个失败时停止
# Stop on first failure
pytest tests/ -x
```

### 测试覆盖率要求 | Test Coverage Requirements

- **单元测试**: 核心业务逻辑覆盖率 > 80%
  | **Unit Tests**: Core business logic coverage > 80%
- **集成测试**: 主要 API 端点必须有测试
  | **Integration Tests**: Major API endpoints must have tests
- **新增功能**: 必须包含测试
  | **New Features**: Must include tests

---

## 📋 PR 流程 | Pull Request Workflow

### PR 检查清单 | PR Checklist

提交 PR 前请确认：

Before submitting PR, please confirm:

- [ ] 代码通过所有测试 | Code passes all tests
- [ ] 代码符合项目规范 | Code follows project style
- [ ] 添加了必要的测试 | Added necessary tests
- [ ] 更新了相关文档 | Updated relevant documentation
- [ ] 提交信息清晰 | Commit messages are clear
- [ ] 没有合并冲突 | No merge conflicts
- [ ] PR 描述完整 | PR description is complete

### PR 模板 | PR Template

```markdown
## 📝 描述 | Description
<!-- 简要描述这个 PR 的改动 | Brief description of changes -->
这个 PR 实现了什么功能？修复了什么问题？

## 🎯 类型 | Type
- [ ] Bug 修复 | Bug fix
- [ ] 新功能 | New feature
- [ ] 破坏性变更 | Breaking change
- [ ] 文档更新 | Documentation update
- [ ] 性能优化 | Performance improvement
- [ ] 代码重构 | Code refactoring

## 🔗 相关 Issue | Related Issue
Fixes #(issue number)
Relates to #(issue number)

## 📸 变更截图 | Screenshots
<!-- 如果适用，添加截图 | Add screenshots if applicable -->
### Before
![before](screenshot-before.png)

### After
![after](screenshot-after.png)

## ✅ 变更内容 | Changes
<!-- 详细列出所有改动 | List all changes in detail -->
- 实现了功能 X
- 修复了问题 Y
- 更新了文档 Z

## 🧪 测试 | Testing
- [ ] 单元测试通过 | Unit tests pass
- [ ] 集成测试通过 | Integration tests pass
- [ ] 手动测试通过 | Manual testing passed
- [ ] 添加了新测试 | Added new tests

### 测试步骤 | Test Steps
<!-- 描述如何测试这些改动 | Describe how to test these changes -->
1. 步骤一
2. 步骤二
3. 步骤三

## ⚠️ 破坏性变更 | Breaking Changes
<!-- 如果有破坏性变更，请描述 | If there are breaking changes, describe them -->
无

## 📚 文档 | Documentation
- [ ] 代码已注释 | Code is commented
- [ ] README 已更新 | README updated
- [ ] API 文档已更新 | API docs updated
- [ ] CHANGELOG 已更新 | CHANGELOG updated

## ✨ 额外信息 | Additional Info
<!-- 任何其他信息 | Any other information -->
```

```markdown
## 描述 | Description
简要描述这个 PR 的改动 | Brief description of changes

## 类型 | Type
- [ ] Bug 修复 | Bug fix
- [ ] 新功能 | New feature
- [ ] 破坏性变更 | Breaking change
- [ ] 文档更新 | Documentation update

## 相关 Issue | Related Issue
Fixes #xxx

## 变更内容 | Changes
- 详细列出所有改动 | List all changes in detail

## 测试 | Testing
- [ ] 已添加测试 | Tests added
- [ ] 所有测试通过 | All tests pass
- [ ] 手动测试通过 | Manual testing passed

## 检查清单 | Checklist
- [ ] 代码符合项目规范 | Code follows project style
- [ ] 文档已更新 | Documentation updated
- [ ] 提交信息清晰 | Commit messages are clear
```

---

## 🎨 代码规范 | Code Standards

### Python 代码风格 | Python Code Style

```python
# 好的示例 | Good example
from typing import Optional

async def get_memory(
    memory_id: str,
    include_purchased: bool = False
) -> Optional[dict]:
    """
    获取记忆详情 | Get memory details

    Args:
        memory_id: 记忆 ID | Memory ID
        include_purchased: 是否包含购买信息 | Include purchase info

    Returns:
        记忆数据或 None | Memory data or None
    """
    # 实现代码 | Implementation
    pass
```

### 文档字符串 | Docstrings

- 所有公共函数和类必须包含文档字符串
  All public functions and classes must have docstrings
- 使用 Google 风格或 NumPy 风格
  Use Google or NumPy style
- 中英文均可，保持一致性
  Chinese or English, but be consistent

### 错误处理 | Error Handling

```python
# 好的示例 | Good example
from app.core.exceptions import AppError

async def purchase_memory(memory_id: str, agent_id: str):
    memory = await get_memory(memory_id)
    if not memory:
        raise AppError(
            code="MEMORY_NOT_FOUND",
            message="记忆不存在 | Memory not found",
            status_code=404
        )
    # 继续处理 | Continue processing
```

---

## 🧪 测试指南 | Testing Guidelines

### 运行测试 | Run Tests

```bash
# 运行所有测试 | Run all tests
pytest tests/

# 运行特定测试文件 | Run specific test file
pytest tests/test_memory_service.py

# 显示测试覆盖率 | Show test coverage
pytest --cov=app tests/
```

### 编写测试 | Write Tests

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_search_memories():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/memories", params={
            "keyword": "抖音"
        })
    assert response.status_code == 200
    assert "data" in response.json()
```

---

## 📖 文档贡献 | Documentation Contributions

### 改进文档 | Improve Documentation

- 修正错别字和语法错误 | Fix typos and grammar errors
- 添加更多示例 | Add more examples
- 补充遗漏的内容 | Add missing content
- 翻译文档 | Translate documentation

### 文档位置 | Documentation Locations

- `README.md` - 项目介绍 | Project overview
- `README.en.md` - 英文介绍 | English overview
- `docs/` - 详细文档 | Detailed documentation
- 代码注释 | Code comments

---

## 🌍 国际化 | Internationalization

我们支持中英文双语文档。

We support bilingual Chinese and English documentation.

添加新功能时，请确保：
When adding new features, please ensure:
- API 错误消息支持双语 | API error messages support bilingual
- 文档提供中英文版本 | Documentation in both languages
- 代码注释可以使用任一语言，但保持一致性
  Code comments can use either language, but be consistent

---

## 📜 行为准则 | Code of Conduct

### 我们的承诺 | Our Pledge

我们致力于为每个人提供友好、安全的环境。
We are committed to providing a friendly and safe environment for everyone.

### 我们的期望 | Our Expectations

- 尊重不同的观点和经验 | Respect differing viewpoints and experiences
- 使用包容性语言 | Use inclusive language
- 优雅地接受建设性批评 | Gracefully accept constructive criticism
- 关注对社区最有利的事情 | Focus on what is best for the community
- 对其他社区成员表示同理心 | Show empathy towards other community members

---

## 🎁 贡献者 | Contributors

所有贡献者将被列入项目的贡献者列表。

All contributors will be listed in the project's contributors list.

### 如何成为贡献者 | How to Become a Contributor

只要你的 Pull Request 被合并，你就成为了贡献者！
Once your Pull Request is merged, you become a contributor!

---

## ❓ 常见问题 | FAQ

### Q: 我需要先签署协议吗？ | Do I need to sign an agreement?

A: 不需要。你在 GitHub 上提交贡献即表示你同意使用 MIT 许可证。
   No. By submitting contributions on GitHub, you agree to the MIT license.

### Q: 我的 PR 多久会被审查？ | How long until my PR is reviewed?

A: 我们通常在 1-3 天内审查，但复杂功能可能需要更长时间。
   We usually review within 1-3 days, but complex features may take longer.

### Q: 我可以提出大的功能改动吗？ | Can I propose major changes?

A: 可以！但请先创建 Issue 讨论，避免浪费你的时间。
   Yes! But please create an issue first to discuss, to avoid wasting your time.

### Q: 如何保持 Fork 同步？ | How to keep my fork synced?

```bash
git remote add upstream https://github.com/Timluogit/memory-market.git
git fetch upstream
git rebase upstream/main
git push origin feature-branch
```

---

## 📞 联系我们 | Contact Us

- **GitHub Issues**: https://github.com/Timluogit/memory-market/issues
- **Email**: your-email@example.com

---

**再次感谢你的贡献！ | Thanks again for your contribution!**
