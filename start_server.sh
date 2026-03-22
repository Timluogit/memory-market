#!/bin/bash

# Agent 记忆市场 - 快速启动脚本

echo "🚀 启动 Agent 记忆市场服务器..."

# 检查是否已经运行
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  服务器已经在运行 (端口 8000)"
    echo "💡 如需重启，请先运行: pkill -f uvicorn"
    exit 1
fi

# 启动服务器
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo "✅ 服务器已停止"
