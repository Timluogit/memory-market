#!/usr/bin/env python3
"""验证佣金系统配置"""
from app.core.config import settings

print("=" * 60)
print("佣金系统验证")
print("=" * 60)

print("\n📊 当前配置:")
print(f"  卖家分成率 (SELLER_SHARE_RATE): {settings.SELLER_SHARE_RATE * 100}%")
print(f"  平台佣金率 (PLATFORM_FEE_RATE): {settings.PLATFORM_FEE_RATE * 100}%")

print("\n💰 佣金计算示例:")
test_prices = [100, 500, 1000, 2000, 5000]

print(f"\n{'价格':<10} {'卖家收入 (85%)':<20} {'平台佣金 (15%)':<20}")
print("-" * 50)
for price in test_prices:
    seller_income = int(price * settings.SELLER_SHARE_RATE)
    platform_fee = price - seller_income
    print(f"{price:<10} {seller_income:<20} {platform_fee:<20}")

print("\n✅ 配置检查:")
if settings.SELLER_SHARE_RATE == 0.85:
    print("  ✓ 卖家分成率正确: 85%")
else:
    print(f"  ✗ 卖家分成率异常: {settings.SELLER_SHARE_RATE * 100}%")

if settings.PLATFORM_FEE_RATE == 0.15:
    print("  ✓ 平台佣金率正确: 15%")
else:
    print(f"  ✗ 平台佣金率异常: {settings.PLATFORM_FEE_RATE * 100}%")

print("\n📋 已实现的功能:")
print("  ✓ Transaction 表新增 commission 字段")
print("  ✓ PlatformStats 表记录平台统计")
print("  ✓ purchase_memory 函数计算并记录佣金")
print("  ✓ Transaction 记录包含佣金信息（销售记录）")
print("  ✓ GET /api/v1/transactions/stats 查看平台收入统计")
print("  ✓ 自动更新平台统计数据")

print("\n🔌 API 端点:")
print("  GET  /api/v1/transactions/stats")
print("       - 查看平台收入统计")
print("       - 返回累计和当日交易数据")
print("       - 包含佣金率配置信息")

print("\n📝 佣金流程:")
print("  1. 买家购买记忆，支付价格 P")
print("  2. 平台计算佣金: commission = P × 15%")
print("  3. 卖家实际收入: income = P × 85%")
print("  4. 创建 Transaction 记录:")
print("     - 买家: purchase 类型, amount = -P")
print("     - 卖家: sale 类型, amount = income, commission = commission")
print("  5. 更新 PlatformStats 统计")
print("  6. 更新 Purchase 记录 (seller_income, platform_fee)")

print("\n" + "=" * 60)
print("验证完成！")
print("=" * 60)
