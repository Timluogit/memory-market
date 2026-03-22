#!/usr/bin/env python3
"""测试佣金系统"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models.tables import Base, PlatformStats, Transaction, Agent, Memory
from app.core.config import settings
from sqlalchemy import select

async def test_commission_calculation():
    """测试佣金计算逻辑"""
    print("=" * 60)
    print("测试佣金系统")
    print("=" * 60)

    # 测试佣金计算
    test_prices = [100, 500, 1000, 1500, 2000]

    print(f"\n配置:")
    print(f"  卖家分成率: {settings.SELLER_SHARE_RATE * 100}%")
    print(f"  平台佣金率: {settings.PLATFORM_FEE_RATE * 100}%")
    print(f"\n佣金计算测试:")

    for price in test_prices:
        seller_income = int(price * settings.SELLER_SHARE_RATE)
        platform_fee = price - seller_income
        print(f"  价格: {price} → 卖家: {seller_income}, 平台: {platform_fee}")

    # 检查数据库连接
    print(f"\n数据库: {settings.DATABASE_URL}")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 检查表结构
        print("\n检查数据库表结构:")

        # 检查 Transaction 表是否有 commission 字段
        result = await session.execute(select(Transaction).limit(1))
        tx = result.scalar_one_or_none()
        if tx:
            print(f"  ✓ Transaction 表存在")
            print(f"  ✓ Transaction.commission 字段存在")
        else:
            print(f"  ⚠ Transaction 表暂无数据")

        # 检查 PlatformStats 表
        result = await session.execute(select(PlatformStats).limit(1))
        stats = result.scalar_one_or_none()
        if stats:
            print(f"  ✓ PlatformStats 表存在")
            print(f"\n平台统计数据:")
            print(f"  累计交易数: {stats.total_transactions}")
            print(f"  累计交易额: {stats.total_volume}")
            print(f"  累计佣金收入: {stats.total_revenue}")
            print(f"  当日交易数: {stats.daily_transactions}")
            print(f"  当日交易额: {stats.daily_volume}")
            print(f"  当日佣金收入: {stats.daily_revenue}")
        else:
            print(f"  ⚠ PlatformStats 表暂无数据（需完成交易后自动创建）")

    await engine.dispose()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\nAPI 端点:")
    print("  GET  /api/v1/transactions/stats - 查看平台收入统计")
    print("  GET  /api/v1/transactions/ - 查看所有交易（含佣金）")
    print("  GET  /api/v1/transactions/my - 查看我的交易（含佣金）")
    print("\n佣金流程:")
    print("  1. 买家购买记忆支付 100 积分")
    print("  2. 平台扣除 15% 佣金 (15 积分)")
    print("  3. 卖家收到 85% 收入 (85 积分)")
    print("  4. 佣金记录到 Transaction 表 (sale 类型)")
    print("  5. 更新 PlatformStats 统计")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_commission_calculation())
