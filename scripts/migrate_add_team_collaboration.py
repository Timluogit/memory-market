"""
数据库迁移脚本：添加团队协作功能

此脚本添加以下新表和字段：
- teams（团队表）
- team_members（团队成员表）
- team_invite_codes（团队邀请码表）
- team_credit_transactions（团队积分交易表）
- 扩展 memories 表（添加 team_id, team_access_level, created_by_agent_id）

使用方法：
    python scripts/migrate_add_team_collaboration.py

或作为模块导入：
    from scripts.migrate_add_team_collaboration import migrate
    await migrate()

注意事项：
    - 此迁移是向后兼容的，所有新字段都是可选的
    - 现有代码不需要修改
    - 建议在执行前备份数据库
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.db.database import engine


async def migrate():
    """执行数据库迁移"""
    print("🔄 开始数据库迁移：添加团队协作功能...\n")

    async with engine.begin() as conn:
        try:
            # 1. 创建 teams 表
            print("📝 创建 teams 表...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(50) NOT NULL,
                    description TEXT,
                    owner_agent_id VARCHAR(50) NOT NULL,
                    member_count INTEGER DEFAULT 1,
                    memory_count INTEGER DEFAULT 0,
                    credits INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    archived_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_agent_id) REFERENCES agents(agent_id)
                )
            """))
            print("   ✅ teams 表创建成功")

            # 2. 创建 teams 表索引
            print("📝 创建 teams 表索引...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_teams_owner ON teams(owner_agent_id)
            """))
            print("   ✅ teams 表索引创建成功")

            # 3. 创建 team_members 表
            print("📝 创建 team_members 表...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id VARCHAR(50) NOT NULL,
                    agent_id VARCHAR(50) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'member',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    left_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id),
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
                    UNIQUE(team_id, agent_id)
                )
            """))
            print("   ✅ team_members 表创建成功")

            # 4. 创建 team_members 表索引
            print("📝 创建 team_members 表索引...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_members_agent ON team_members(agent_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_members_active ON team_members(team_id, is_active)
            """))
            print("   ✅ team_members 表索引创建成功")

            # 5. 创建 team_invite_codes 表
            print("📝 创建 team_invite_codes 表...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_invite_codes (
                    invite_code_id VARCHAR(50) PRIMARY KEY,
                    team_id VARCHAR(50) NOT NULL,
                    code VARCHAR(8) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    used_by_agent_id VARCHAR(50),
                    used_at TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id),
                    FOREIGN KEY (used_by_agent_id) REFERENCES agents(agent_id)
                )
            """))
            print("   ✅ team_invite_codes 表创建成功")

            # 6. 创建 team_invite_codes 表索引
            print("📝 创建 team_invite_codes 表索引...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_invite_codes_code ON team_invite_codes(code)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_invite_codes_team ON team_invite_codes(team_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_invite_codes_expires ON team_invite_codes(expires_at)
            """))
            print("   ✅ team_invite_codes 表索引创建成功")

            # 7. 创建 team_credit_transactions 表
            print("📝 创建 team_credit_transactions 表...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_credit_transactions (
                    tx_id VARCHAR(50) PRIMARY KEY,
                    team_id VARCHAR(50) NOT NULL,
                    agent_id VARCHAR(50),
                    tx_type VARCHAR(50) NOT NULL,
                    amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    related_id VARCHAR(50),
                    description VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(team_id),
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
                )
            """))
            print("   ✅ team_credit_transactions 表创建成功")

            # 8. 创建 team_credit_transactions 表索引
            print("📝 创建 team_credit_transactions 表索引...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_credit_tx_team ON team_credit_transactions(team_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_credit_tx_agent ON team_credit_transactions(agent_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_team_credit_tx_created ON team_credit_transactions(created_at)
            """))
            print("   ✅ team_credit_transactions 表索引创建成功")

            # 9. 扩展 memories 表（检查字段是否已存在）
            print("📝 扩展 memories 表...")

            # 检查 team_id 字段
            result = await conn.execute(text("""
                SELECT COUNT(*) as cnt FROM pragma_table_info('memories') WHERE name = 'team_id'
            """))
            team_id_exists = result.fetchone()[0] > 0

            if not team_id_exists:
                await conn.execute(text("""
                    ALTER TABLE memories ADD COLUMN team_id VARCHAR(50)
                """))
                print("   ✅ 添加 memories.team_id 字段")
            else:
                print("   ℹ️  memories.team_id 字段已存在")

            # 检查 team_access_level 字段
            result = await conn.execute(text("""
                SELECT COUNT(*) as cnt FROM pragma_table_info('memories') WHERE name = 'team_access_level'
            """))
            team_access_level_exists = result.fetchone()[0] > 0

            if not team_access_level_exists:
                await conn.execute(text("""
                    ALTER TABLE memories ADD COLUMN team_access_level VARCHAR(20) DEFAULT 'private'
                """))
                print("   ✅ 添加 memories.team_access_level 字段")
            else:
                print("   ℹ️  memories.team_access_level 字段已存在")

            # 检查 created_by_agent_id 字段
            result = await conn.execute(text("""
                SELECT COUNT(*) as cnt FROM pragma_table_info('memories') WHERE name = 'created_by_agent_id'
            """))
            created_by_exists = result.fetchone()[0] > 0

            if not created_by_exists:
                await conn.execute(text("""
                    ALTER TABLE memories ADD COLUMN created_by_agent_id VARCHAR(50)
                """))
                print("   ✅ 添加 memories.created_by_agent_id 字段")
            else:
                print("   ℹ️  memories.created_by_agent_id 字段已存在")

            # 10. 创建 memories 表索引
            print("📝 创建 memories 表新索引...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memories_team ON memories(team_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memories_access_level ON memories(team_access_level)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memories_team_access ON memories(team_id, team_access_level)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memories_created_by ON memories(created_by_agent_id)
            """))
            print("   ✅ memories 表索引创建成功")

            print("\n✅ 数据库迁移完成！")
            print("\n📊 迁移摘要:")
            print("   - 创建 4 个新表: teams, team_members, team_invite_codes, team_credit_transactions")
            print("   - 扩展 1 个表: memories (添加 3 个字段)")
            print("   - 创建 14 个索引")
            print("\n🎉 团队协作功能已就绪！")

        except Exception as e:
            print(f"\n❌ 迁移失败: {e}")
            raise


async def rollback():
    """回滚数据库迁移（删除新表和字段）"""
    print("⚠️  开始回滚数据库迁移...\n")

    async with engine.begin() as conn:
        try:
            # 删除表（注意顺序：先删子表，再删父表）
            print("📝 删除 team_credit_transactions 表...")
            await conn.execute(text("DROP TABLE IF EXISTS team_credit_transactions"))
            print("   ✅ team_credit_transactions 表已删除")

            print("📝 删除 team_invite_codes 表...")
            await conn.execute(text("DROP TABLE IF EXISTS team_invite_codes"))
            print("   ✅ team_invite_codes 表已删除")

            print("📝 删除 team_members 表...")
            await conn.execute(text("DROP TABLE IF EXISTS team_members"))
            print("   ✅ team_members 表已删除")

            print("📝 删除 teams 表...")
            await conn.execute(text("DROP TABLE IF EXISTS teams"))
            print("   ✅ teams 表已删除")

            # SQLite 不支持直接删除列，这里只提示
            print("\n⚠️  注意: SQLite 不支持直接删除列。")
            print("   如果需要删除 memories 表的新字段，建议重建表。")
            print("   字段: team_id, team_access_level, created_by_agent_id")

            print("\n✅ 回滚完成！")

        except Exception as e:
            print(f"\n❌ 回滚失败: {e}")
            raise


async def verify():
    """验证数据库迁移结果"""
    print("🔍 验证数据库迁移...\n")

    async with engine.begin() as conn:
        try:
            # 检查表是否存在
            tables_to_check = [
                "teams",
                "team_members",
                "team_invite_codes",
                "team_credit_transactions",
            ]

            print("📋 检查新表:")
            for table in tables_to_check:
                result = await conn.execute(text(f"""
                    SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table' AND name='{table}'
                """))
                exists = result.fetchone()[0] > 0
                status = "✅" if exists else "❌"
                print(f"   {status} {table}")

            # 检查 memories 表字段
            print("\n📋 检查 memories 表字段:")
            fields_to_check = [
                "team_id",
                "team_access_level",
                "created_by_agent_id",
            ]

            for field in fields_to_check:
                result = await conn.execute(text(f"""
                    SELECT COUNT(*) as cnt FROM pragma_table_info('memories') WHERE name='{field}'
                """))
                exists = result.fetchone()[0] > 0
                status = "✅" if exists else "❌"
                print(f"   {status} memories.{field}")

            # 检查索引
            print("\n📋 检查索引:")
            indexes_to_check = [
                "idx_teams_name",
                "idx_teams_owner",
                "idx_team_members_team",
                "idx_team_members_agent",
                "idx_team_members_active",
                "idx_team_invite_codes_code",
                "idx_team_invite_codes_team",
                "idx_team_invite_codes_expires",
                "idx_team_credit_tx_team",
                "idx_team_credit_tx_agent",
                "idx_team_credit_tx_created",
                "idx_memories_team",
                "idx_memories_access_level",
                "idx_memories_team_access",
                "idx_memories_created_by",
            ]

            for index in indexes_to_check:
                result = await conn.execute(text(f"""
                    SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='index' AND name='{index}'
                """))
                exists = result.fetchone()[0] > 0
                status = "✅" if exists else "❌"
                print(f"   {status} {index}")

            print("\n✅ 验证完成！")

        except Exception as e:
            print(f"\n❌ 验证失败: {e}")
            raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "migrate":
            asyncio.run(migrate())
        elif command == "rollback":
            asyncio.run(rollback())
        elif command == "verify":
            asyncio.run(verify())
        else:
            print(f"❌ 未知命令: {command}")
            print("用法:")
            print("  python scripts/migrate_add_team_collaboration.py migrate  # 执行迁移")
            print("  python scripts/migrate_add_team_collaboration.py rollback  # 回滚迁移")
            print("  python scripts/migrate_add_team_collaboration.py verify    # 验证迁移")
    else:
        # 默认执行迁移
        asyncio.run(migrate())
