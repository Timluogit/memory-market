"""记忆服务"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, and_, or_, desc
from app.models.tables import Agent, Memory, Purchase, Rating, Transaction
from app.models.schemas import (
    MemoryCreate, MemoryUpdate, MemoryResponse, MemoryDetail, 
    MemoryList, PurchaseResponse, RateRequest, RateResponse
)
from app.core.config import settings
import uuid

def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def memory_to_response(memory: Memory, seller_name: str = "", seller_reputation: float = 5.0) -> MemoryResponse:
    """转换为响应格式"""
    return MemoryResponse(
        memory_id=memory.memory_id,
        seller_agent_id=memory.seller_agent_id,
        seller_name=seller_name,
        seller_reputation=seller_reputation,
        title=memory.title,
        category=memory.category,
        tags=memory.tags or [],
        summary=memory.summary,
        format_type=memory.format_type,
        price=memory.price,
        purchase_count=memory.purchase_count,
        favorite_count=memory.favorite_count,
        avg_score=memory.avg_score,
        verification_score=memory.verification_score,
        created_at=memory.created_at,
        updated_at=memory.updated_at
    )

async def upload_memory(db: AsyncSession, seller_id: str, req: MemoryCreate) -> MemoryResponse:
    """上传记忆"""
    # 检查卖家
    seller = await db.execute(select(Agent).where(Agent.agent_id == seller_id))
    seller = seller.scalar_one_or_none()
    if not seller:
        raise ValueError("卖家不存在")
    
    memory = Memory(
        memory_id=gen_id("mem"),
        seller_agent_id=seller_id,
        title=req.title,
        category=req.category,
        tags=req.tags,
        summary=req.summary,
        content=req.content,
        format_type=req.format_type,
        price=req.price,
        verification_data=req.verification_data
    )
    
    # 计算验证分数
    if req.verification_data:
        memory.verification_score = _calc_verification_score(req.verification_data)
    
    # 设置过期时间
    if req.expires_days:
        from datetime import datetime, timedelta
        memory.expires_at = datetime.now() + timedelta(days=req.expires_days)
    
    db.add(memory)
    
    # 更新卖家统计
    seller.memories_uploaded += 1
    
    await db.commit()
    await db.refresh(memory)
    
    return memory_to_response(memory, seller.name, seller.reputation_score)

async def search_memories(
    db: AsyncSession,
    query: str = "",
    category: str = "",
    platform: str = "",
    format_type: str = "",
    min_score: float = 0,
    max_price: int = 999999,
    page: int = 1,
    page_size: int = 10
) -> MemoryList:
    """搜索记忆"""
    # 基础查询
    stmt = select(Memory, Agent.name, Agent.reputation_score).join(
        Agent, Memory.seller_agent_id == Agent.agent_id
    ).where(Memory.is_active == True)
    
    # 筛选条件
    if query:
        stmt = stmt.where(
            or_(
                Memory.title.ilike(f"%{query}%"),
                Memory.summary.ilike(f"%{query}%")
            )
        )
    
    if category:
        stmt = stmt.where(Memory.category.contains(category))
    
    if platform:
        stmt = stmt.where(Memory.category.startswith(platform))
    
    if format_type:
        stmt = stmt.where(Memory.format_type == format_type)
    
    if min_score > 0:
        stmt = stmt.where(Memory.avg_score >= min_score)
    
    if max_price < 999999:
        stmt = stmt.where(Memory.price <= max_price)
    
    # 计数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.execute(count_stmt)
    total = total.scalar() or 0
    
    # 分页 + 排序（按热度）
    stmt = stmt.order_by(desc(Memory.purchase_count)).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    items = []
    for row in rows:
        memory, seller_name, seller_reputation = row
        items.append(memory_to_response(memory, seller_name, seller_reputation))
    
    return MemoryList(items=items, total=total, page=page, page_size=page_size)

async def get_memory_detail(db: AsyncSession, memory_id: str, buyer_id: str = None) -> MemoryDetail:
    """获取记忆详情"""
    result = await db.execute(
        select(Memory, Agent.name, Agent.reputation_score).join(
            Agent, Memory.seller_agent_id == Agent.agent_id
        ).where(Memory.memory_id == memory_id)
    )
    row = result.first()
    if not row:
        return None
    
    memory, seller_name, seller_reputation = row
    
    # 检查是否已购买（免费记忆除外）
    if buyer_id and memory.price > 0:
        purchase = await db.execute(
            select(Purchase).where(
                and_(Purchase.buyer_agent_id == buyer_id, Purchase.memory_id == memory_id)
            )
        )
        if not purchase.scalar_one_or_none():
            raise PermissionError("未购买此记忆")
    
    return MemoryDetail(
        **memory_to_response(memory, seller_name, seller_reputation).model_dump(),
        content=memory.content,
        verification_data=memory.verification_data
    )

async def purchase_memory(db: AsyncSession, buyer_id: str, memory_id: str) -> PurchaseResponse:
    """购买记忆"""
    # 获取记忆
    result = await db.execute(select(Memory).where(Memory.memory_id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        return PurchaseResponse(success=False, message="记忆不存在", memory_id=memory_id, credits_spent=0, remaining_credits=0)
    
    # 检查是否已购买
    existing = await db.execute(
        select(Purchase).where(
            and_(Purchase.buyer_agent_id == buyer_id, Purchase.memory_id == memory_id)
        )
    )
    if existing.scalar_one_or_none():
        return PurchaseResponse(success=False, message="已购买此记忆", memory_id=memory_id, credits_spent=0, remaining_credits=0)
    
    # 检查是否是自己的记忆
    if memory.seller_agent_id == buyer_id:
        return PurchaseResponse(success=False, message="不能购买自己的记忆", memory_id=memory_id, credits_spent=0, remaining_credits=0)
    
    # 获取买家
    buyer = await db.execute(select(Agent).where(Agent.agent_id == buyer_id))
    buyer = buyer.scalar_one_or_none()
    if not buyer:
        return PurchaseResponse(success=False, message="买家不存在", memory_id=memory_id, credits_spent=0, remaining_credits=0)
    
    # MVP免费模式：跳过余额检查
    price = memory.price
    if settings.MVP_FREE_MODE:
        price = 0  # 免费！
    elif buyer.credits < price:
        return PurchaseResponse(success=False, message="积分不足", memory_id=memory_id, credits_spent=price, remaining_credits=buyer.credits)
    
    # 计算分配
    seller_income = int(price * settings.SELLER_SHARE_RATE)
    platform_fee = price - seller_income
    
    # 扣买家积分
    buyer.credits -= price
    buyer.total_spent += price
    buyer.total_purchases += 1
    
    # 加卖家积分
    seller = await db.execute(select(Agent).where(Agent.agent_id == memory.seller_agent_id))
    seller = seller.scalar_one_or_none()
    seller.credits += seller_income
    seller.total_earned += seller_income
    seller.total_sales += 1
    
    # 更新记忆统计
    memory.purchase_count += 1
    
    # 创建购买记录
    purchase = Purchase(
        purchase_id=gen_id("pur"),
        buyer_agent_id=buyer_id,
        seller_agent_id=memory.seller_agent_id,
        memory_id=memory_id,
        amount=price,
        seller_income=seller_income,
        platform_fee=platform_fee
    )
    db.add(purchase)
    
    # 创建交易流水
    tx_buyer = Transaction(
        agent_id=buyer_id,
        tx_type="purchase",
        amount=-price,
        balance_after=buyer.credits,
        related_id=memory_id,
        description=f"购买记忆: {memory.title}"
    )
    tx_seller = Transaction(
        agent_id=memory.seller_agent_id,
        tx_type="sale",
        amount=seller_income,
        balance_after=seller.credits,
        related_id=memory_id,
        description=f"销售记忆: {memory.title}"
    )
    db.add(tx_buyer)
    db.add(tx_seller)
    
    await db.commit()
    
    return PurchaseResponse(
        success=True,
        message="购买成功",
        memory_id=memory_id,
        credits_spent=price,
        remaining_credits=buyer.credits,
        memory_content=memory.content
    )

async def rate_memory(db: AsyncSession, buyer_id: str, req: RateRequest) -> RateResponse:
    """评价记忆"""
    # 检查是否购买过
    purchase = await db.execute(
        select(Purchase).where(
            and_(Purchase.buyer_agent_id == buyer_id, Purchase.memory_id == req.memory_id)
        )
    )
    if not purchase.scalar_one_or_none():
        raise PermissionError("未购买此记忆")
    
    # 检查是否已评价
    existing = await db.execute(
        select(Rating).where(
            and_(Rating.buyer_agent_id == buyer_id, Rating.memory_id == req.memory_id)
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("已评价此记忆")
    
    # 创建评价
    rating = Rating(
        rating_id=gen_id("rat"),
        memory_id=req.memory_id,
        buyer_agent_id=buyer_id,
        score=req.score,
        effectiveness=req.effectiveness,
        comment=req.comment
    )
    db.add(rating)
    
    # 更新记忆评分
    memory = await db.execute(select(Memory).where(Memory.memory_id == req.memory_id))
    memory = memory.scalar_one_or_none()
    memory.total_score += req.score
    memory.score_count += 1
    memory.avg_score = memory.total_score / memory.score_count
    
    await db.commit()
    
    return RateResponse(
        success=True,
        message="评价成功",
        new_avg_score=memory.avg_score
    )

def _calc_verification_score(data: dict) -> float:
    """计算验证分数（0-1）"""
    score = 0.0
    if data.get("sample_size"):
        score += min(data["sample_size"] / 1000, 0.3)
    if data.get("success_rate"):
        score += data["success_rate"] * 0.3
    if data.get("data_source"):
        score += 0.2
    if data.get("test_period_days"):
        score += min(data["test_period_days"] / 30, 0.2)
    return round(min(score, 1.0), 2)
