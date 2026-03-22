"""认证模块"""
from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.tables import Agent
from app.core.exceptions import UNAUTHORIZED, FORBIDDEN


async def get_current_agent(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    """认证中间件，通过 X-API-Key 获取当前 Agent"""
    result = await db.execute(
        select(Agent).where(Agent.api_key == x_api_key)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise UNAUTHORIZED

    if not agent.is_active:
        raise FORBIDDEN

    return agent
