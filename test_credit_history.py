"""测试积分流水记录功能"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.tables import Base, Transaction, Agent
from app.models.schemas import AgentCreate, CreditHistoryList
from app.services.agent_service import create_agent, get_credit_history
from app.core.config import settings

async def test_credit_history():
    """测试积分流水"""
    # 创建测试数据库连接
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. 创建一个新Agent（会自动记录初始积分流水）
        print("=== 1. 创建新Agent ===")
        agent_req = AgentCreate(
            name="测试Agent",
            description="用于测试积分流水"
        )
        agent = await create_agent(db, agent_req)
        print(f"✓ Agent创建成功: {agent.name}")
        print(f"  初始积分: {agent.credits}")
        print(f"  Agent ID: {agent.agent_id}")

        # 2. 获取积分流水
        print("\n=== 2. 获取积分流水 ===")
        history = await get_credit_history(db, agent.agent_id, page=1, page_size=10)
        print(f"✓ 流水记录总数: {history.total}")
        print(f"  当前页记录数: {len(history.items)}")

        # 3. 打印流水详情
        print("\n=== 3. 流水详情 ===")
        for idx, tx in enumerate(history.items, 1):
            print(f"\n记录 #{idx}:")
            print(f"  交易ID: {tx.tx_id}")
            print(f"  类型: {tx.tx_type}")
            print(f"  金额: {tx.amount}")
            print(f"  余额: {tx.balance_after}")
            print(f"  描述: {tx.description}")
            print(f"  时间: {tx.created_at}")

    print("\n✓ 测试完成！")

if __name__ == "__main__":
    asyncio.run(test_credit_history())
