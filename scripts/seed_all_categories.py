"""添加所有分类的种子数据"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session
from app.models.tables import Memory, Agent
import random


# 完整的分类数据
SEED_MEMORIES = [
    # 小红书分类
    {
        "title": "小红书爆款笔记标题公式",
        "category": "小红书/爆款公式",
        "tags": ["小红书", "爆款", "标题"],
        "summary": "10种高互动笔记标题模板，平均阅读量提升60%",
        "format_type": "template",
        "price": 50,
        "seller_name": "小红书运营专家"
    },
    {
        "title": "小红书种草文案写作技巧",
        "category": "小红书/文案",
        "tags": ["小红书", "种草", "文案"],
        "summary": "从0到1写出高转化种草文，包含5个万能模板",
        "format_type": "template",
        "price": 80,
        "seller_name": "小红书运营专家"
    },
    {
        "title": "小红书投放ROI优化策略",
        "category": "小红书/投流",
        "tags": ["小红书", "投放", "ROI"],
        "summary": "薯条投放最佳时段和出价策略，ROI提升40%",
        "format_type": "strategy",
        "price": 100,
        "seller_name": "小红书投流达人"
    },
    {
        "title": "小红书账号冷启动指南",
        "category": "小红书/运营",
        "tags": ["小红书", "冷启动", "涨粉"],
        "summary": "新账号前30天运营计划，快速突破1000粉",
        "format_type": "strategy",
        "price": 60,
        "seller_name": "小红书运营专家"
    },
    
    # 微信分类
    {
        "title": "公众号爆款文章选题方法",
        "category": "微信/爆款公式",
        "tags": ["微信", "公众号", "选题"],
        "summary": "5个选题来源渠道，让文章更容易被推荐",
        "format_type": "strategy",
        "price": 70,
        "seller_name": "微信运营老手"
    },
    {
        "title": "公众号阅读量提升技巧",
        "category": "微信/运营",
        "tags": ["微信", "公众号", "阅读量"],
        "summary": "从标题到排版的完整优化方案，打开率提升35%",
        "format_type": "template",
        "price": 60,
        "seller_name": "微信运营老手"
    },
    {
        "title": "私域流量转化话术模板",
        "category": "微信/私域",
        "tags": ["微信", "私域", "转化"],
        "summary": "20个高转化私域话术模板，适用于不同场景",
        "format_type": "template",
        "price": 90,
        "seller_name": "私域运营专家"
    },
    
    # B站分类
    {
        "title": "B站视频爆款封面设计",
        "category": "B站/运营",
        "tags": ["B站", "封面", "设计"],
        "summary": "5种高点击率封面模板，提升CTR 50%",
        "format_type": "template",
        "price": 50,
        "seller_name": "B站UP主运营"
    },
    {
        "title": "B站视频标题优化公式",
        "category": "B站/爆款公式",
        "tags": ["B站", "标题", "爆款"],
        "summary": "10个爆款标题公式，让视频更容易被推荐",
        "format_type": "template",
        "price": 40,
        "seller_name": "B站UP主运营"
    },
    
    # 通用分类
    {
        "title": "AI提示词工程最佳实践",
        "category": "通用/工具使用",
        "tags": ["AI", "提示词", "工具"],
        "summary": "10个场景的提示词模板，提升AI输出质量",
        "format_type": "template",
        "price": 80,
        "seller_name": "AI工具达人"
    },
    {
        "title": "数据分析避坑指南",
        "category": "通用/避坑指南",
        "tags": ["数据", "分析", "避坑"],
        "summary": "10个常见数据分析错误及解决方案",
        "format_type": "strategy",
        "price": 60,
        "seller_name": "数据分析老手"
    },
    {
        "title": "跨平台内容分发策略",
        "category": "通用/运营",
        "tags": ["跨平台", "内容", "分发"],
        "summary": "一套内容多平台分发的最佳实践，效率提升200%",
        "format_type": "strategy",
        "price": 70,
        "seller_name": "全平台运营"
    }
]


async def seed_data():
    """添加种子数据"""
    async with async_session() as db:
        # 获取所有 Agent
        from sqlalchemy import select
        result = await db.execute(select(Agent))
        agents = result.scalars().all()
        
        if not agents:
            print("❌ 没有找到 Agent，请先运行主程序初始化数据")
            return
        
        # 创建内存到 Agent 的映射
        agent_map = {}
        for agent in agents:
            agent_map[agent.name] = agent.agent_id
        
        added_count = 0
        for memory_data in SEED_MEMORIES:
            seller_name = memory_data.pop("seller_name")
            agent_id = agent_map.get(seller_name, agents[0].agent_id)
            
            # 检查是否已存在相同标题
            existing = await db.execute(
                select(Memory).where(Memory.title == memory_data["title"])
            )
            if existing.scalar_one_or_none():
                print(f"⏭️  已存在: {memory_data['title']}")
                continue
            
            # 创建记忆
            memory = Memory(
                memory_id=f"mem_{random.randbytes(6).hex()}",
                seller_agent_id=agent_id,
                content={"summary": memory_data["summary"]},
                **memory_data
            )
            db.add(memory)
            added_count += 1
            print(f"✅ 添加: {memory_data['title']}")
        
        await db.commit()
        print(f"\n🎉 成功添加 {added_count} 条新记忆！")


if __name__ == "__main__":
    asyncio.run(seed_data())
