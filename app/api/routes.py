"""API路由"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.db.database import get_db
from app.models.schemas import *
from app.services.agent_service import *
from app.services.memory_service import *

router = APIRouter()

# ============ 认证依赖 ============

async def get_current_agent(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    """通过API Key认证Agent"""
    agent = await get_agent_by_api_key(db, x_api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    if not agent.is_active:
        raise HTTPException(status_code=403, detail="Agent disabled")
    return agent

# ============ Agent相关 ============

@router.post("/agents", response_model=AgentResponse, tags=["Agent"])
async def register_agent(req: AgentCreate, db: AsyncSession = Depends(get_db)):
    """注册新Agent，返回API Key"""
    agent = await create_agent(db, req)
    return agent

@router.get("/agents/me", response_model=AgentResponse, tags=["Agent"])
async def get_my_info(agent: Agent = Depends(get_current_agent)):
    """获取当前Agent信息"""
    return AgentResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        description=agent.description,
        credits=agent.credits,
        reputation_score=agent.reputation_score,
        total_sales=agent.total_sales,
        total_purchases=agent.total_purchases,
        created_at=agent.created_at
    )

@router.get("/agents/me/balance", response_model=AgentBalance, tags=["Agent"])
async def get_my_balance(agent: Agent = Depends(get_current_agent), db: AsyncSession = Depends(get_db)):
    """获取账户余额"""
    balance = await get_balance(db, agent.agent_id)
    if not balance:
        raise HTTPException(404, "Agent not found")
    return balance

# ============ 记忆相关 ============

@router.post("/memories", response_model=MemoryResponse, tags=["Memory"])
async def upload_memory_endpoint(
    req: MemoryCreate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """上传记忆"""
    try:
        memory = await upload_memory(db, agent.agent_id, req)
        return memory
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/memories", response_model=MemoryList, tags=["Memory"])
async def search_memories_endpoint(
    query: Optional[str] = Query("", description="搜索关键词"),
    category: Optional[str] = Query("", description="分类筛选"),
    platform: Optional[str] = Query("", description="平台筛选"),
    format_type: Optional[str] = Query("", description="类型筛选"),
    min_score: Optional[float] = Query(0, description="最低评分"),
    max_price: Optional[int] = Query(999999, description="最高价格（分）"),
    page: Optional[int] = Query(1, ge=1),
    page_size: Optional[int] = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """搜索记忆"""
    result = await search_memories(
        db, query=query, category=category, platform=platform,
        format_type=format_type, min_score=min_score, max_price=max_price,
        page=page, page_size=page_size
    )
    return result

@router.get("/memories/{memory_id}", response_model=MemoryDetail, tags=["Memory"])
async def get_memory_endpoint(
    memory_id: str,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """获取记忆详情（需购买）"""
    try:
        detail = await get_memory_detail(db, memory_id, agent.agent_id)
        if not detail:
            raise HTTPException(404, "Memory not found")
        return detail
    except PermissionError as e:
        raise HTTPException(403, str(e))

@router.post("/memories/{memory_id}/purchase", response_model=PurchaseResponse, tags=["Memory"])
async def purchase_memory_endpoint(
    memory_id: str,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """购买记忆"""
    result = await purchase_memory(db, agent.agent_id, memory_id)
    if not result.success:
        raise HTTPException(400, result.message)
    return result

@router.post("/memories/{memory_id}/rate", response_model=RateResponse, tags=["Memory"])
async def rate_memory_endpoint(
    memory_id: str,
    req: RateRequest,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """评价记忆"""
    req.memory_id = memory_id
    try:
        result = await rate_memory(db, agent.agent_id, req)
        return result
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

# ============ 市场数据 ============

@router.get("/market/trends", response_model=List[MarketTrend], tags=["Market"])
async def get_market_trends(
    platform: Optional[str] = Query("", description="平台筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取市场趋势"""
    # 简化实现：返回各分类统计
    from sqlalchemy import func
    from app.models.tables import Memory
    
    stmt = (
        select(
            Memory.category,
            func.count(Memory.memory_id).label("memory_count"),
            func.sum(Memory.purchase_count).label("total_sales"),
            func.avg(Memory.price).label("avg_price")
        )
        .where(Memory.is_active == True)
        .group_by(Memory.category)
        .order_by(desc("total_sales"))
        .limit(10)
    )
    
    if platform:
        stmt = stmt.where(Memory.category.startswith(platform))
    
    result = await db.execute(stmt)
    
    trends = []
    for row in result:
        trends.append(MarketTrend(
            category=row.category,
            memory_count=row.memory_count,
            total_sales=row.total_sales or 0,
            avg_price=float(row.avg_price or 0),
            trending_tags=[]  # TODO: 从tags统计
        ))
    
    return trends
