#!/bin/bash
# Agent记忆市场 - 启动脚本

set -e

echo "🧠 Agent记忆市场启动中..."

# 检查数据目录
mkdir -p data

# 检查是否需要导入种子数据
if [ ! -f "data/memory_market.db" ]; then
    echo "📦 首次运行，导入种子数据..."
    python scripts/seed_memories.py || echo "⚠️ 种子数据导入失败，继续启动..."
fi

# 启动服务
echo "🚀 启动服务..."
python -m app.main
