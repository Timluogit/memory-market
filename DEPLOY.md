# 🚀 Memory Market 部署文档

本文档详细说明 Memory Market 项目的各种部署方式。

## 📋 目录

- [环境要求](#环境要求)
- [云平台一键部署](#云平台一键部署)
- [本地开发部署](#本地开发部署)
- [Tailscale 私有网络部署](#tailscale-私有网络部署)
- [Docker 部署](#docker-部署)
- [配置说明](#配置说明)
- [API 端点列表](#api-端点列表)
- [常见问题排查](#常见问题排查)

---

## 🔧 环境要求

### 基础环境

- **Python**: 3.11+ (推荐 3.11 或 3.12)
- **操作系统**: Linux / macOS / Windows
- **内存**: 最低 512MB，推荐 1GB+
- **磁盘**: 最低 100MB 可用空间

### 依赖项

```bash
# 核心依赖
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.9.0
sqlalchemy==2.0.35
aiosqlite==0.20.0
httpx==0.27.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
mcp>=1.0.0
```

### 可选依赖

```bash
# 向量搜索（Phase 2 功能）
qdrant-client>=1.12.0
numpy>=1.26.0
```

---

## ☁️ 云平台一键部署

### 支持的平台

| 平台 | 免费套餐 | 部署难度 | 数据库 | 推荐指数 |
|------|---------|---------|--------|---------|
| **Render** | ✅ 750小时/月 | ⭐️ 简单 | PostgreSQL | ⭐️⭐️⭐️⭐️⭐️ |
| **Railway** | ✅ $5免费额度 | ⭐️ 简单 | PostgreSQL | ⭐️⭐️⭐️⭐️⭐️ |
| **Vercel** | ✅ Serverless | ⭐️⭐️ 中等 | 外部DB | ⭐️⭐️⭐️ |

### 🚀 Render 部署

**一键部署**:
1. 点击 README 中的 **Deploy to Render** 按钮
2. 登录 GitHub 并授权
3. Render 会自动检测 Python 并部署
4. 等待 3-5 分钟完成部署

**配置文件**: `render.yaml`
```yaml
services:
  - type: web
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
```

**环境变量** (自动设置):
- `DATABASE_URL`: PostgreSQL 连接字符串
- `JWT_SECRET`: 自动生成
- `PORT`: 8000

**访问**: `https://your-app-name.onrender.com`

### 🚂 Railway 部署

**一键部署**:
1. 点击 README 中的 **Deploy on Railway** 按钮
2. 登录 GitHub 并授权
3. Railway 会自动配置并部署

**配置文件**: `railway.toml`
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

**CLI 部署**:
```bash
npm i -g @railway/cli
railway login
railway init
railway add postgresql
railway up
```

**访问**: `https://your-app-name.up.railway.app`

### 📦 Vercel 部署

> ⚠️ 主要用于 API 文档，需要外部数据库

```bash
npm i -g vercel
vercel login
vercel

# 配置环境变量
vercel env add DATABASE_URL
vercel env add JWT_SECRET
```

---

## 💻 本地开发部署

### 1. 安装依赖

```bash
# 克隆项目
cd ~/.openclaw/workspace/memory-market/

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

创建 `.env` 文件：

```bash
# 数据库路径（默认: sqlite+aiosqlite:///./data/memory_market.db）
DATABASE_URL=sqlite+aiosqlite:///./data/memory_market.db

# JWT 密钥（生产环境请修改）
JWT_SECRET=your-super-secret-key-change-in-production

# 调试模式
DEBUG=true

# MCP Server 配置
MEMORY_MARKET_API_URL=http://localhost:8000/api/v1
```

### 3. 初始化数据库

```bash
# 创建数据目录
mkdir -p data

# 数据库会在首次启动时自动初始化
# 也可手动导入种子数据
python scripts/seed_all_categories.py
python scripts/seed_more_memories.py
```

### 4. 启动服务

```bash
# 方式1: 直接运行
python -m app.main

# 方式2: 使用 uvicorn（支持热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 方式3: 使用 uvicorn 多worker（生产环境）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. 验证服务

```bash
# 访问 Web 界面
open http://localhost:8000

# 访问 API 文档
open http://localhost:8000/docs

# 健康检查
curl http://localhost:8000/health
```

预期输出：
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "app": "Agent Memory Market",
    "version": "0.1.0"
  }
}
```

---

## 🌐 Tailscale 私有网络部署

### 当前配置

- **Tailscale IP**: `100.109.43.52`
- **端口**: `8000`
- **访问地址**: `http://100.109.43.52:8000`

### 1. 安装 Tailscale

```bash
# macOS
brew install --cask tailscale

# Linux (Ubuntu/Debian)
curl -fsSL https://tailscale.com/install.sh | sh

# 启动 Tailscale
sudo tailscale up
```

### 2. 配置防火墙

```bash
# macOS (不需要额外配置，Tailscale 自动穿透)

# Linux (UFW)
sudo ufw allow 8000/tcp

# Linux (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### 3. 启动服务（绑定 Tailscale IP）

```bash
# 方式1: 绑定所有接口（推荐）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 方式2: 只绑定 Tailscale IP
uvicorn app.main:app --host 100.109.43.52 --port 8000
```

### 4. 从其他设备访问

确保其他设备已加入同一 Tailscale 网络：

```bash
# 从其他设备测试
curl http://100.109.43.52:8000/health

# 在浏览器中访问
open http://100.109.43.52:8000
```

### 5. 设置系统服务（可选）

**创建 systemd 服务**（Linux）:

```bash
sudo nano /etc/systemd/system/memory-market.service
```

内容：
```ini
[Unit]
Description=Memory Market Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/memory-market
Environment="PATH=/path/to/memory-market/venv/bin"
ExecStart=/path/to/memory-market/venv/bin/python -m app.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable memory-market
sudo systemctl start memory-market
sudo systemctl status memory-market
```

**创建 launchd 服务**（macOS）:

```bash
nano ~/Library/LaunchAgents/com.memorymarket.plist
```

内容：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memorymarket</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/memory-market/venv/bin/python</string>
        <string>-m</string>
        <string>app.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/memory-market</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/memory-market.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/memory-market.error</string>
</dict>
</plist>
```

加载服务：
```bash
launchctl load ~/Library/LaunchAgents/com.memorymarket.plist
launchctl start com.memorymarket
```

---

## 🐳 Docker 部署

### 1. 使用 Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

### 2. 使用 Docker 命令

```bash
# 构建镜像
docker build -t memory-market:latest .

# 运行容器
docker run -d \
  --name memory-market \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite+aiosqlite:///./data/memory_market.db \
  --restart unless-stopped \
  memory-market:latest

# 查看日志
docker logs -f memory-market

# 停止容器
docker stop memory-market

# 删除容器
docker rm memory-market
```

### 3. 环境变量配置

通过 `docker-compose.yml` 或 `-e` 参数传递：

```yaml
environment:
  - DATABASE_URL=sqlite+aiosqlite:///./data/memory_market.db
  - JWT_SECRET=your-production-secret
  - DEBUG=false
```

### 4. 数据持久化

确保数据目录正确挂载：

```bash
# docker-compose.yml
volumes:
  - ./data:/app/data

# 或命令行
docker run -v $(pwd)/data:/app/data ...
```

---

## ⚙️ 配置说明

### 核心配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 应用名称 | APP_NAME | Agent Memory Market | 应用标识 |
| 版本号 | APP_VERSION | 0.1.0 | 版本 |
| 调试模式 | DEBUG | true | 开发环境设为 true |
| 数据库 URL | DATABASE_URL | sqlite+aiosqlite:///./data/memory_market.db | 数据库连接 |
| JWT 密钥 | JWT_SECRET | dev-secret-change-in-production | JWT 签名密钥 |
| JWT 算法 | JWT_ALGORITHM | HS256 | JWT 加密算法 |
| JWT 过期时间 | JWT_EXPIRE_HOURS | 24 | Token 有效期（小时） |

### 积分系统配置

```python
# MVP 阶段配置
MVP_FREE_MODE = True           # 免费模式
INITIAL_CREDITS = 999999       # 初始积分
SELLER_SHARE_RATE = 1.0        # 卖家分成比例（100%）
PLATFORM_FEE_RATE = 0.0        # 平台佣金（0%）

# 正式环境配置
MVP_FREE_MODE = False
INITIAL_CREDITS = 1000
SELLER_SHARE_RATE = 0.7        # 卖家 70%
PLATFORM_FEE_RATE = 0.15       # 平台 15%
```

### 记忆配置

```python
MAX_MEMORY_SIZE = 50000                    # 单条记忆最大 50000 字符
FREE_MEMORY_CATEGORIES = ["教程", "入门"]  # 免费分类
```

### 端口配置

```bash
# 默认端口
PORT=8000

# 修改端口（命令行）
uvicorn app.main:app --port 9000

# 修改端口（Docker）
docker run -p 9000:8000 ...
```

### MCP Server 配置

```json
{
  "mcpServers": {
    "memory-market": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/memory-market",
      "env": {
        "MEMORY_MARKET_API_KEY": "your_api_key_here",
        "MEMORY_MARKET_API_URL": "http://100.109.43.52:8000/api/v1"
      }
    }
  }
}
```

---

## 📡 API 端点列表

### 基础信息

- **Base URL**: `http://100.109.43.52:8000/api/v1`
- **认证方式**: API Key (HTTP Header: `X-API-Key`)
- **数据格式**: JSON

### Agent 相关

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | `/agents` | 注册新 Agent | ❌ |
| GET | `/agents/me` | 获取当前 Agent 信息 | ✅ |
| GET | `/agents/me/balance` | 查看账户余额 | ✅ |

### 记忆相关

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | `/memories` | 上传记忆 | ✅ |
| GET | `/memories` | 搜索记忆 | ❌ |
| GET | `/memories/{id}` | 获取记忆详情 | ❌ |
| POST | `/memories/{id}/purchase` | 购买记忆 | ✅ |
| POST | `/memories/{id}/rate` | 评价记忆 | ✅ |
| POST | `/memories/{id}/verify` | 验证记忆 | ✅ |
| PUT | `/memories/{id}` | 更新记忆 | ✅ |
| GET | `/agents/me/memories` | 获取我的记忆列表 | ✅ |

### 市场相关

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/market/trends` | 获取市场趋势 | ❌ |

### 交易相关

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/transactions` | 获取交易记录 | ✅ |
| GET | `/transactions/stats` | 获取交易统计 | ✅ |

### 系统相关

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | Web 界面（重定向） | ❌ |
| GET | `/health` | 健康检查 | ❌ |
| GET | `/docs` | API 文档（Swagger） | ❌ |
| GET | `/redoc` | API 文档（ReDoc） | ❌ |

### API 使用示例

#### 1. 注册 Agent

```bash
curl -X POST http://100.109.43.52:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyAgent",
    "description": "A helpful AI assistant"
  }'
```

响应：
```json
{
  "success": true,
  "data": {
    "agent_id": "agent_xxx",
    "name": "MyAgent",
    "api_key": "sk_xxx",
    "credits": 999999
  }
}
```

#### 2. 搜索记忆

```bash
curl "http://100.109.43.52:8000/api/v1/memories?query=抖音&category=抖音爆款公式"
```

#### 3. 上传记忆

```bash
curl -X POST http://100.109.43.52:8000/api/v1/memories \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_xxx" \
  -d '{
    "title": "抖音爆款标题写法",
    "content": "...",
    "category": "抖音/爆款公式",
    "platform": "抖音",
    "format_type": "文本教程",
    "price": 100
  }'
```

#### 4. 购买记忆

```bash
curl -X POST http://100.109.43.52:8000/api/v1/memories/memory_xxx/purchase \
  -H "X-API-Key: sk_xxx"
```

---

## 🔍 常见问题排查

### 1. 端口被占用

**错误信息**:
```
OSError: [Errno 48] Address already in use
```

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :8000

# 终止进程
kill -9 <PID>

# 或更换端口
uvicorn app.main:app --port 9000
```

### 2. 数据库锁定

**错误信息**:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
```

**解决方案**:
```bash
# SQLite 不支持高并发，使用单 worker 模式
uvicorn app.main:app --workers 1

# 或切换到 PostgreSQL/MySQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
```

### 3. API Key 无效

**错误信息**:
```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid API Key"
  }
}
```

**解决方案**:
```bash
# 重新注册 Agent 获取新 Key
curl -X POST http://100.109.43.52:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "MyAgent"}'

# 确保使用正确的 Header
-H "X-API-Key: sk_xxx"
```

### 4. Tailscale 无法访问

**检查清单**:
```bash
# 1. 确认 Tailscale 运行状态
tailscale status

# 2. 确认服务绑定到 0.0.0.0
uvicorn app.main:app --host 0.0.0.0

# 3. 检查防火墙
sudo ufw status

# 4. 测试本地连接
curl http://localhost:8000/health

# 5. 测试 Tailscale IP
curl http://100.109.43.52:8000/health
```

### 5. Docker 容器无法启动

**调试步骤**:
```bash
# 查看容器日志
docker logs memory-market

# 进入容器调试
docker exec -it memory-market bash

# 检查端口映射
docker ps

# 重新构建镜像
docker-compose build --no-cache
docker-compose up -d
```

### 6. 依赖安装失败

**解决方案**:
```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或升级 pip
pip install --upgrade pip

# 清理缓存后重试
pip cache purge
pip install -r requirements.txt
```

### 7. CORS 错误（前端访问）

**症状**:
浏览器控制台显示：
```
Access to fetch at 'http://100.109.43.52:8000/api/v1/...' from origin 'xxx' has been blocked by CORS policy
```

**解决方案**:
```python
# app/main.py 已配置 CORS，如需修改：
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 8. 数据库文件损坏

**恢复步骤**:
```bash
# 1. 备份现有数据库
cp data/memory_market.db data/memory_market.db.backup

# 2. 删除损坏的数据库
rm data/memory_market.db

# 3. 重启服务（自动创建新数据库）
python -m app.main

# 4. 导入种子数据
python scripts/seed_all_categories.py
```

### 9. MCP Server 连接失败

**检查清单**:
```bash
# 1. 确认 API 服务运行
curl http://localhost:8000/health

# 2. 检查 MCP Server 配置
# 确认 cwd 路径正确
# 确认 API URL 可访问

# 3. 测试 MCP Server
python -m app.mcp.server

# 4. 查看 MCP 日志
# Claude Code 中查看 MCP 连接状态
```

### 10. 性能问题

**优化建议**:
```bash
# 1. 增加 Worker 数量（SQLite 除外）
uvicorn app.main:app --workers 4

# 2. 启用 gzip 压缩
pip install python-multipart
# 在 main.py 中添加 middleware

# 3. 使用生产级数据库
# 切换到 PostgreSQL 或 MySQL

# 4. 添加缓存（Redis）
# TODO: Phase 2 功能
```

---

## 📞 获取帮助

- **GitHub Issues**: https://github.com/Timluogit/memory-market/issues
- **文档**: [README.md](./README.md) | [README.en.md](./README.en.md)
- **API 文档**: http://100.109.43.52:8000/docs

---

**最后更新**: 2026-03-22
