#!/usr/bin/env python3
"""测试记忆版本管理功能"""
import asyncio
import sys
sys.path.insert(0, '/Users/sss/.openclaw/workspace/memory-market')

from app.db.database import engine as async_engine, Base, async_session
from app.models.tables import Memory, MemoryVersion, Agent
from app.services.memory_service import (
    upload_memory,
    update_memory,
    get_memory_versions,
    get_memory_version
)
from app.models.schemas import MemoryCreate
from sqlalchemy import select

async def setup_test_db():
    """初始化测试数据库表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 数据库表初始化完成")

async def test_version_management():
    """测试版本管理功能"""
    print("\n=== 测试记忆版本管理 ===\n")

    # 创建测试会话
    async with async_session() as db:
        # 1. 创建测试 Agent
        print("1. 创建测试 Agent...")
        import uuid
        agent = Agent(
            name="测试Agent",
            description="用于测试版本管理",
            api_key=f"test_version_key_{uuid.uuid4().hex[:8]}"
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        print(f"   ✓ Agent创建成功: {agent.agent_id}\n")

        # 2. 上传记忆（自动创建v1版本）
        print("2. 上传记忆（自动创建v1版本）...")
        memory_data = MemoryCreate(
            title="测试记忆版本管理",
            category="测试/版本管理",
            tags=["测试", "版本"],
            content={"test": "data", "version": 1},
            summary="这是一个用于测试版本管理功能的记忆，包含完整的版本历史记录",
            format_type="template",
            price=100,
            verification_data=None,
            expires_days=None
        )
        memory = await upload_memory(db, agent.agent_id, memory_data)
        print(f"   ✓ 记忆上传成功: {memory.memory_id}")
        print(f"   ✓ 标题: {memory.title}")
        print(f"   ✓ 价格: {memory.price}\n")

        # 3. 检查v1版本是否创建
        print("3. 检查v1版本...")
        versions = await get_memory_versions(db, memory.memory_id)
        print(f"   ✓ 版本总数: {versions['total']}")
        if versions['items']:
            v1 = versions['items'][0]
            print(f"   ✓ v{v1.version_number}: {v1.title}")
            print(f"   ✓ 创建时间: {v1.created_at}")
            print(f"   ✓ Changelog: {v1.changelog}\n")

        # 4. 更新记忆（创建v2版本）
        print("4. 更新记忆（创建v2版本）...")
        update_data = {
            "title": "测试记忆 v2",
            "content": {"test": "data", "version": 2},
            "price": 150,
            "changelog": "更新内容和价格"
        }
        updated_memory = await update_memory(db, memory.memory_id, agent.agent_id, update_data)
        print(f"   ✓ 记忆更新成功")
        print(f"   ✓ 新标题: {updated_memory.title}")
        print(f"   ✓ 新价格: {updated_memory.price}\n")

        # 5. 检查v2版本
        print("5. 检查所有版本...")
        versions = await get_memory_versions(db, memory.memory_id)
        print(f"   ✓ 版本总数: {versions['total']}")
        for v in versions['items']:
            print(f"   ✓ v{v.version_number}: {v.title} - {v.changelog}\n")

        # 6. 查看特定版本
        print("6. 查看v1版本详情...")
        v1_id = versions['items'][1].version_id  # v1是第二个（倒序）
        v1_detail = await get_memory_version(db, memory.memory_id, v1_id)
        print(f"   ✓ 版本ID: {v1_detail['version_id']}")
        print(f"   ✓ 版本号: {v1_detail['version_number']}")
        print(f"   ✓ 标题: {v1_detail['title']}")
        print(f"   ✓ 内容: {v1_detail['content']}")
        print(f"   ✓ 价格: {v1_detail['price']}\n")

        # 7. 再次更新（创建v3版本）
        print("7. 再次更新（创建v3版本）...")
        update_data2 = {
            "title": "测试记忆 v3",
            "summary": "这是第三个版本的测试记忆",
            "tags": ["测试", "版本", "v3"],
            "changelog": "添加新标签和更新摘要"
        }
        updated_memory2 = await update_memory(db, memory.memory_id, agent.agent_id, update_data2)
        print(f"   ✓ 记忆再次更新成功")
        print(f"   ✓ 最新标题: {updated_memory2.title}\n")

        # 8. 最终版本列表
        print("8. 最终版本列表...")
        final_versions = await get_memory_versions(db, memory.memory_id)
        print(f"   ✓ 总版本数: {final_versions['total']}")
        print("   版本历史:")
        for v in final_versions['items']:
            print(f"     • v{v.version_number}: {v.title}")
            print(f"       价格: {v.price}, 标签: {v.tags}")
            print(f"       Changelog: {v.changelog}")
            print(f"       创建时间: {v.created_at}\n")

        print("=== 测试完成 ✓ ===")

        # 清理测试数据
        print("\n清理测试数据...")
        await db.rollback()
        print("✓ 测试数据已清理")

if __name__ == "__main__":
    asyncio.run(setup_test_db())
    asyncio.run(test_version_management())
