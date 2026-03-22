# 多阶段构建：生产级 Dockerfile
# Stage 1: 构建依赖
FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖到临时目录
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: 运行时镜像
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # 应用路径
    APP_HOME=/app \
    # 数据库路径
    DATABASE_URL=sqlite+aiosqlite:////app/data/memory_market.db

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /root/.local /root/.local

# 确保脚本在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 设置工作目录
WORKDIR $APP_HOME

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建数据目录并设置权限
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# 切换到非 root 用户
USER appuser

# 暴露端口
# 8000: FastAPI 应用
# 8001: MCP SSE 端点
EXPOSE 8000 8001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
# 启动 FastAPI 应用（端口 8000）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
