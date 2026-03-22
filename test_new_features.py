"""
测试新增的 MCP 工具功能

这个脚本测试：
1. update_memory - 更新记忆
2. get_my_memories - 获取我的记忆列表
"""

import asyncio
from app.services.memory_service import update_memory, get_my_memories
from app.db.database import get_session


async def test_update_memory():
    """测试更新记忆功能"""
    print("=== 测试 update_memory ===")

    async with get_session() as db:
        # 测试场景1: 更新存在的记忆
        # 假设 memory_id 是 "mem_xxx", seller_id 是 "agent_yyy"
        memory_id = "mem_test123"
        seller_id = "agent_seller123"

        updates = {
            "title": "更新后的标题",
            "summary": "更新后的摘要",
            "price": 200  # 新价格
        }

        try:
            result = await update_memory(db, memory_id, seller_id, updates)
            if result:
                print(f"✅ 记忆更新成功: {result.title}")
            else:
                print("⚠️  记忆不存在")
        except PermissionError as e:
            print(f"❌ 权限错误: {e}")
        except Exception as e:
            print(f"❌ 错误: {e}")


async def test_get_my_memories():
    """测试获取我的记忆列表功能"""
    print("\n=== 测试 get_my_memories ===")

    async with get_session() as db:
        seller_id = "agent_seller123"

        try:
            result = await get_my_memories(db, seller_id, page=1, page_size=10)

            print(f"📦 总记忆数: {result['total']}")
            print(f"💰 统计数据:")
            print(f"   - 总销量: {result['stats']['total_sales']}")
            print(f"   - 总收入: {result['stats']['total_earned']}")

            print(f"\n📝 记忆列表 (显示 {len(result['items'])} 条):")
            for i, item in enumerate(result['items'], 1):
                print(f"{i}. {item['title']} - {item['category']}")
                print(f"   价格: {item['price']} | 销量: {item['purchase_count']}")
        except Exception as e:
            print(f"❌ 错误: {e}")


async def main():
    """运行所有测试"""
    await test_update_memory()
    await test_get_my_memories()


if __name__ == "__main__":
    asyncio.run(main())
