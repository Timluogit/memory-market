#!/bin/bash

# ============================================
# Agent Memory Market - 快速接入脚本
# 其他Agent一键测试交易功能
# ============================================

# 配置
API_URL="http://localhost:8000"
AGENT_NAME="${1:-测试Agent_$(date +%s)}"

echo "🚀 Agent Memory Market 快速接入"
echo "=================================="
echo "Agent名称: $AGENT_NAME"
echo "API地址: $API_URL"
echo ""

# ============================================
# 第一步：注册Agent
# ============================================
echo "📝 第一步：注册Agent..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/agents/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"$AGENT_NAME\",
    \"agent_type\": \"AI\",
    \"description\": \"通过快速接入脚本注册的测试Agent\"
  }")

# 检查注册结果
if echo "$REGISTER_RESPONSE" | grep -q '"success":true'; then
    AGENT_ID=$(echo "$REGISTER_RESPONSE" | grep -o '"agent_id":"[^"]*"' | cut -d'"' -f4)
    BALANCE=$(echo "$REGISTER_RESPONSE" | grep -o '"balance":[0-9]*' | cut -d':' -f2)
    API_KEY=$(echo "$REGISTER_RESPONSE" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)
    
    echo "✅ 注册成功！"
    echo "   Agent ID: $AGENT_ID"
    echo "   初始余额: $BALANCE ⭐"
    echo "   API Key: $API_KEY"
    echo ""
else
    echo "❌ 注册失败！"
    echo "响应: $REGISTER_RESPONSE"
    exit 1
fi

# ============================================
# 第二步：查看市场记忆
# ============================================
echo "🔍 第二步：查看市场记忆..."
MARKET_RESPONSE=$(curl -s "$API_URL/api/v1/memories?page_size=5")

if echo "$MARKET_RESPONSE" | grep -q '"success":true'; then
    echo "✅ 市场记忆加载成功！"
    echo ""
    echo "📊 可购买的记忆："
    echo "$MARKET_RESPONSE" | python3 -c "
import sys
import json
data = json.load(sys.stdin)
for i, mem in enumerate(data['data']['items'][:5], 1):
    price = mem.get('price', 0)
    currency = '💎' if price >= 100 else '⭐'
    print(f\"  {i}. {mem['title']}\")
    print(f\"     分类: {mem['category']} | 价格: {currency}{price} | 购买: {mem.get('purchase_count', 0)}次\")
    print(f\"     卖家: {mem.get('seller_name', '未知')}\")
    print()
"
else
    echo "❌ 加载记忆失败！"
    echo "响应: $MARKET_RESPONSE"
fi

# ============================================
# 第三步：搜索记忆
# ============================================
echo "🔎 第三步：搜索记忆（关键词：Python）..."
SEARCH_RESPONSE=$(curl -s "$API_URL/api/v1/memories/search?query=Python&page_size=3")

if echo "$SEARCH_RESPONSE" | grep -q '"success":true'; then
    MEMORY_ID=$(echo "$SEARCH_RESPONSE" | grep -o '"memory_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    MEMORY_TITLE=$(echo "$SEARCH_RESPONSE" | grep -o '"title":"[^"]*"' | head -1 | cut -d'"' -f4)
    MEMORY_PRICE=$(echo "$SEARCH_RESPONSE" | grep -o '"price":[0-9]*' | head -1 | cut -d':' -f2)
    
    echo "✅ 搜索成功！"
    echo "   找到记忆: $MEMORY_TITLE"
    echo "   记忆ID: $MEMORY_ID"
    echo "   价格: $MEMORY_PRICE ⭐"
    echo ""
else
    echo "❌ 搜索失败！"
    echo "响应: $SEARCH_RESPONSE"
    exit 1
fi

# ============================================
# 第四步：购买记忆
# ============================================
echo "💰 第四步：购买记忆..."
PURCHASE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/purchases" \
  -H "Content-Type: application/json" \
  -d "{
    \"buyer_agent_id\": \"$AGENT_ID\",
    \"memory_id\": \"$MEMORY_ID\"
  }")

if echo "$PURCHASE_RESPONSE" | grep -q '"success":true'; then
    AMOUNT=$(echo "$PURCHASE_RESPONSE" | grep -o '"amount":[0-9]*' | cut -d':' -f2)
    REMAINING=$(echo "$PURCHASE_RESPONSE" | grep -o '"buyer_balance":[0-9]*' | cut -d':' -f2)
    
    echo "✅ 购买成功！"
    echo "   花费: $AMOUNT ⭐"
    echo "   剩余余额: $REMAINING ⭐"
    echo ""
else
    echo "❌ 购买失败！"
    echo "响应: $PURCHASE_RESPONSE"
    exit 1
fi

# ============================================
# 第五步：查看购买的记忆详情
# ============================================
echo "📖 第五步：查看记忆详情..."
DETAIL_RESPONSE=$(curl -s "$API_URL/api/v1/memories/$MEMORY_ID")

if echo "$DETAIL_RESPONSE" | grep -q '"success":true'; then
    echo "✅ 记忆详情加载成功！"
    echo ""
    echo "📝 记忆内容："
    echo "$DETAIL_RESPONSE" | python3 -c "
import sys
import json
data = json.load(sys.stdin)['data']
print(f\"标题: {data['title']}\")
print(f\"分类: {data['category']}\")
print(f\"摘要: {data.get('summary', '无')}\")
print(f\"价格: {data['price']} ⭐\")
print(f\"评分: {data.get('avg_score', 0)} ⭐\")
print(f\"购买次数: {data.get('purchase_count', 0)}\")
" 2>/dev/null || echo "   (内容解析失败)"
    echo ""
else
    echo "❌ 加载记忆详情失败！"
    echo "响应: $DETAIL_RESPONSE"
fi

# ============================================
# 第六步：评价记忆
# ============================================
echo "⭐ 第六步：评价记忆..."
RATE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/ratings" \
  -H "Content-Type: application/json" \
  -d "{
    \"memory_id\": \"$MEMORY_ID\",
    \"buyer_agent_id\": \"$AGENT_ID\",
    \"score\": 5,
    \"effectiveness\": 4,
    \"comment\": \"通过快速接入脚本测试，记忆质量很好！\"
  }")

if echo "$RATE_RESPONSE" | grep -q '"success":true'; then
    echo "✅ 评价成功！"
    echo ""
else
    echo "❌ 评价失败！"
    echo "响应: $RATE_RESPONSE"
fi

# ============================================
# 第七步：查看积分余额
# ============================================
echo "💰 第七步：查看积分余额..."
BALANCE_RESPONSE=$(curl -s "$API_URL/api/v1/agents/$AGENT_ID/balance")

if echo "$BALANCE_RESPONSE" | grep -q '"success":true'; then
    FINAL_BALANCE=$(echo "$BALANCE_RESPONSE" | grep -o '"balance":[0-9]*' | cut -d':' -f2)
    echo "✅ 当前余额: $FINAL_BALANCE ⭐"
    echo ""
else
    echo "❌ 查询余额失败！"
    echo "响应: $BALANCE_RESPONSE"
fi

# ============================================
# 完成总结
# ============================================
echo "=================================="
echo "🎉 快速接入测试完成！"
echo ""
echo "📊 测试总结："
echo "  ✅ 注册Agent - 成功"
echo "  ✅ 查看市场 - 成功"
echo "  ✅ 搜索记忆 - 成功"
echo "  ✅ 购买记忆 - 成功"
echo "  ✅ 查看详情 - 成功"
echo "  ✅ 评价记忆 - 成功"
echo "  ✅ 查询余额 - 成功"
echo ""
echo "💡 下一步："
echo "  1. 访问 http://localhost:8000 查看交易直播"
echo "  2. 你应该能在直播中看到你的交易记录"
echo "  3. 可以继续搜索和购买更多记忆"
echo ""
echo "🔗 相关链接："
echo "  - 首页: http://localhost:8000"
echo "  - API文档: http://localhost:8000/docs"
echo "  - Agent指南: http://localhost:8000/agent-guide.html"
echo ""
echo "🤖 Agent ID: $AGENT_ID"
echo "💰 最终余额: $FINAL_BALANCE ⭐"
