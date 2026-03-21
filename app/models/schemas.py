"""数据模型 - Pydantic schemas"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# ============ Agent/用户 ============

class AgentCreate(BaseModel):
    """注册Agent"""
    name: str = Field(..., min_length=2, max_length=50, description="Agent名称")
    description: Optional[str] = Field(None, max_length=500, description="Agent描述")

class AgentResponse(BaseModel):
    """Agent信息"""
    agent_id: str
    name: str
    description: Optional[str]
    api_key: Optional[str] = None  # 仅在注册时返回
    credits: int
    reputation_score: float
    total_sales: int
    total_purchases: int
    created_at: datetime

class AgentBalance(BaseModel):
    """账户余额"""
    agent_id: str
    credits: int
    total_earned: int
    total_spent: int

# ============ 记忆 ============

class MemoryContent(BaseModel):
    """记忆内容（结构化）"""
    title: str = Field(..., min_length=2, max_length=200)
    summary: str = Field(..., min_length=10, max_length=500)
    content: dict = Field(..., description="记忆具体内容（JSON）")
    format_type: str = Field(default="template", description="格式：template/strategy/data/case/warning")

class MemoryCreate(BaseModel):
    """上传记忆"""
    title: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., description="分类路径，如：抖音/美妆/爆款公式")
    tags: List[str] = Field(default=[], description="标签列表")
    content: dict = Field(..., description="记忆内容（JSON）")
    summary: str = Field(..., min_length=10, max_length=500)
    format_type: str = Field(default="template", description="类型：template/strategy/data/case/warning")
    price: int = Field(..., ge=0, description="价格（积分）")
    verification_data: Optional[dict] = Field(None, description="验证数据（可选）")
    expires_days: Optional[int] = Field(None, description="有效期天数（可选）")

class MemoryUpdate(BaseModel):
    """更新记忆"""
    content: Optional[dict] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    changelog: Optional[str] = None

class MemoryResponse(BaseModel):
    """记忆信息"""
    memory_id: str
    seller_agent_id: str
    seller_name: str
    seller_reputation: float
    title: str
    category: str
    tags: List[str]
    summary: str
    format_type: str
    price: int = Field(description="价格（积分）")
    purchase_count: int
    favorite_count: int
    avg_score: float
    verification_score: Optional[float]
    created_at: datetime
    updated_at: datetime

class MemoryDetail(MemoryResponse):
    """记忆详情（购买后）"""
    content: dict
    verification_data: Optional[dict]

class MemoryList(BaseModel):
    """记忆列表"""
    items: List[MemoryResponse]
    total: int
    page: int
    page_size: int

# ============ 交易 ============

class PurchaseRequest(BaseModel):
    """购买记忆"""
    memory_id: str

class PurchaseResponse(BaseModel):
    """购买结果"""
    success: bool
    message: str
    memory_id: str
    credits_spent: int
    remaining_credits: int
    memory_content: Optional[dict] = None

class RateRequest(BaseModel):
    """评价记忆"""
    memory_id: str
    score: int = Field(..., ge=1, le=5, description="评分1-5")
    comment: Optional[str] = Field(None, max_length=500)
    effectiveness: Optional[int] = Field(None, ge=1, le=5, description="实际效果1-5")

class RateResponse(BaseModel):
    """评价结果"""
    success: bool
    message: str
    new_avg_score: float

# ============ 市场 ============

class MarketTrend(BaseModel):
    """市场趋势"""
    category: str
    memory_count: int
    total_sales: int
    avg_price: float
    trending_tags: List[str]

class TrendResponse(BaseModel):
    """趋势响应"""
    trends: List[MarketTrend]
    period: str

# ============ API响应 ============

class APIResponse(BaseModel):
    """通用响应"""
    success: bool
    message: str
    data: Optional[dict] = None
