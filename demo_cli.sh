#!/bin/bash
# Memory Market CLI 演示脚本

echo "========================================"
echo "Memory Market CLI 功能演示"
echo "========================================"
echo ""

# 检查是否安装了 memory-market
if ! command -v memory-market &> /dev/null; then
    echo "⚠️  memory-market 未安装"
    echo "请先运行: pip install -e ."
    exit 1
fi

echo "✅ memory-market 已安装"
echo ""

# 1. 显示帮助
echo "=== 1. 显示帮助 ==="
memory-market --help
echo ""
read -p "按回车继续..."
echo ""

# 2. 配置管理
echo "=== 2. 配置管理 ==="
echo "显示当前配置:"
memory-market config --show
echo ""
read -p "按回车继续..."
echo ""

# 3. 搜索功能演示
echo "=== 3. 搜索记忆 ==="
echo "基础搜索:"
echo "  memory-market search '抖音投流'"
echo ""
echo "高级搜索:"
echo "  memory-market search '爆款' \\"
echo "    --category '抖音/美妆' \\"
echo "    --min-score 4.0 \\"
echo "    --max-price 500 \\"
echo "    --sort-by purchase_count"
echo ""
read -p "按回车继续..."
echo ""

# 4. 购买功能演示
echo "=== 4. 购买记忆 ==="
echo "购买记忆:"
echo "  memory-market purchase mem_xxx"
echo ""
read -p "按回车继续..."
echo ""

# 5. 上传功能演示
echo "=== 5. 上传记忆 ==="
echo "上传记忆:"
echo "  memory-market upload \\"
echo "    --title '抖音爆款3秒法则' \\"
echo "    --category '抖音/爆款' \\"
echo "    --summary '实战经验总结' \\"
echo "    --price 200 \\"
echo "    --tags '爆款,黄金法则'"
echo ""
read -p "按回车继续..."
echo ""

# 6. 查看账户信息
echo "=== 6. 查看账户信息 ==="
echo "查看余额:"
echo "  memory-market balance"
echo ""
echo "查看我的信息:"
echo "  memory-market me"
echo ""
read -p "按回车继续..."
echo ""

# 7. 市场趋势
echo "=== 7. 市场趋势 ==="
echo "查看市场趋势:"
echo "  memory-market trends"
echo ""
echo "查看特定平台趋势:"
echo "  memory-market trends --platform '抖音'"
echo ""
read -p "按回车继续..."
echo ""

# 8. JSON 输出格式
echo "=== 8. JSON 输出格式 ==="
echo "使用 JSON 格式输出:"
echo "  memory-market balance --json"
echo "  memory-market search '爆款' --json"
echo ""
read -p "按回车继续..."
echo ""

# 9. 常用命令组合
echo "=== 9. 常用命令组合 ==="
echo ""
echo "搜索并购买:"
echo "  memory-market search '抖音投流' --page-size 1"
echo "  memory-market purchase mem_xxx"
echo ""
echo "上传并查看:"
echo "  memory-market upload --title 'xxx' --category 'xxx' ..."
echo "  memory-market get mem_xxx"
echo ""
echo "查看销售情况:"
echo "  memory-market me"
echo "  memory-market me --history"
echo ""

echo "========================================"
echo "演示完成！"
echo "========================================"
echo ""
echo "提示: 使用 memory-market <command> --help 查看每个命令的详细帮助"
echo ""
echo "快速开始:"
echo "  1. 配置 API Key: memory-market config --set-api-key mk_xxx"
echo "  2. 搜索记忆: memory-market search '关键词'"
echo "  3. 购买记忆: memory-market purchase mem_xxx"
echo ""
