"""用户画像 API

提供用户画像的查询、更新、管理接口
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.dependencies import get_db, get_current_agent
from app.models.tables import Agent
from app.services.user_profile_service import get_profile_service
from app.services.profile_extraction_service import get_extraction_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-profiles", tags=["user-profiles"])


# ============ 请求/响应模型 ============

class ProfileResponse(BaseModel):
    """用户画像响应"""
    profile_id: str
    agent_id: str
    real_name: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    language: str = "zh"
    editor: Optional[str] = None
    theme: str = "dark"
    ui_scale: str = "medium"
    work_hours: Optional[dict] = None
    work_days: Optional[list] = None
    preferred_command: Optional[str] = None
    skills: Optional[list] = None
    tech_stack: Optional[list] = None
    interests: Optional[list] = None
    research_areas: Optional[list] = None
    facts: dict = {}
    completeness_score: float = 0.0
    confidence_score: float = 0.5
    last_updated_at: str
    created_at: str


class ProfileUpdateRequest(BaseModel):
    """用户画像更新请求"""
    real_name: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    editor: Optional[str] = None
    theme: Optional[str] = None
    ui_scale: Optional[str] = None
    work_hours: Optional[dict] = None
    work_days: Optional[list] = None
    preferred_command: Optional[str] = None
    skills: Optional[list] = None
    tech_stack: Optional[list] = None
    interests: Optional[list] = None
    research_areas: Optional[list] = None


class FactResponse(BaseModel):
    """画像事实响应"""
    fact_id: str
    fact_type: str
    fact_key: str
    fact_value: any
    confidence: float
    source: str
    source_reference: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str
    is_valid: bool


class FactCreateRequest(BaseModel):
    """创建事实请求"""
    fact_type: str = Field(..., description="事实类型: personal/preference/habit/skill/interest")
    fact_key: str = Field(..., description="事实键: real_name/language/editor/skills等")
    fact_value: any = Field(..., description="事实值")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="置信度 0-1")


class ChangeResponse(BaseModel):
    """画像变更响应"""
    change_id: str
    change_type: str
    field_name: str
    old_value: any
    new_value: any
    source: str
    source_reference: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: str


class DynamicContextResponse(BaseModel):
    """动态上下文响应"""
    agent_id: str
    current_task: Optional[str] = None
    current_project: Optional[str] = None
    current_focus: Optional[str] = None
    work_state: str = "active"
    recent_activities: Optional[list] = None
    last_session_id: Optional[str] = None
    last_search_query: Optional[str] = None
    last_interacted_memory: Optional[str] = None
    recommended_categories: Optional[list] = None
    suggested_topics: Optional[list] = None
    session_count_today: int = 0
    search_count_today: int = 0
    last_updated_at: str
    created_at: str


class DynamicContextUpdateRequest(BaseModel):
    """动态上下文更新请求"""
    current_task: Optional[str] = None
    current_project: Optional[str] = None
    current_focus: Optional[str] = None
    work_state: Optional[str] = None
    recent_activities: Optional[list] = None
    last_session_id: Optional[str] = None
    last_search_query: Optional[str] = None
    last_interacted_memory: Optional[str] = None
    recommended_categories: Optional[list] = None
    suggested_topics: Optional[list] = None
    session_count_today: Optional[int] = None
    search_count_today: Optional[int] = None


class ExtractFromConversationRequest(BaseModel):
    """从对话提取画像请求"""
    conversation_text: str = Field(..., description="对话文本")
    conversation_id: Optional[str] = Field(None, description="对话ID，用于追溯")


class ExtractFromConversationResponse(BaseModel):
    """从对话提取画像响应"""
    facts: List[dict]
    total_extracted: int
    confidence: float
    extraction_time: str
    error: Optional[str] = None


# ============ API 端点 ============

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户画像"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    profile = await profile_service.get_profile(
        db,
        current_agent.agent_id,
        use_cache=True
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Create one first."
        )

    return ProfileResponse(**profile)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    req: ProfileUpdateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户画像"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()

    # 过滤 None 值
    profile_data = {k: v for k, v in req.dict().items() if v is not None}

    if not profile_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )

    profile = await profile_service.create_or_update_profile(
        db,
        current_agent.agent_id,
        profile_data,
        source="manual"
    )

    return ProfileResponse(**profile)


@router.get("/me/history", response_model=List[ChangeResponse])
async def get_profile_history(
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """获取画像变更历史"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    changes = await profile_service.get_changes(
        db,
        current_agent.agent_id,
        limit=limit
    )

    return [ChangeResponse(**change) for change in changes]


@router.get("/me/facts", response_model=List[FactResponse])
async def get_profile_facts(
    fact_type: Optional[str] = Query(None, description="事实类型过滤"),
    is_valid: bool = Query(True, description="是否只返回有效事实"),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """获取画像事实列表"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    facts = await profile_service.get_facts(
        db,
        current_agent.agent_id,
        fact_type=fact_type,
        is_valid=is_valid
    )

    return [FactResponse(**fact) for fact in facts]


@router.post("/me/facts", response_model=FactResponse)
async def add_profile_fact(
    req: FactCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """手动添加画像事实"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    fact = await profile_service.add_fact(
        db,
        current_agent.agent_id,
        fact_type=req.fact_type,
        fact_key=req.fact_key,
        fact_value=req.fact_value,
        confidence=req.confidence,
        source="manual"
    )

    return FactResponse(**fact)


@router.delete("/me/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_fact(
    fact_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """删除画像事实"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    success = await profile_service.delete_fact(
        db,
        current_agent.agent_id,
        fact_id
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Fact not found"
        )

    return None


@router.get("/me/context", response_model=DynamicContextResponse)
async def get_dynamic_context(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """获取动态上下文"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()
    context = await profile_service.get_dynamic_context(
        db,
        current_agent.agent_id,
        use_cache=True
    )

    if not context:
        raise HTTPException(
            status_code=404,
            detail="Dynamic context not found"
        )

    return DynamicContextResponse(**context)


@router.put("/me/context", response_model=DynamicContextResponse)
async def update_dynamic_context(
    req: DynamicContextUpdateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """更新动态上下文"""
    if not settings.PROFILE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Profile system is disabled"
        )

    profile_service = get_profile_service()

    # 过滤 None 值
    context_data = {k: v for k, v in req.dict().items() if v is not None}

    if not context_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )

    context = await profile_service.update_dynamic_context(
        db,
        current_agent.agent_id,
        context_data
    )

    return DynamicContextResponse(**context)


@router.post("/extract", response_model=ExtractFromConversationResponse)
async def extract_from_conversation(
    req: ExtractFromConversationRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """从对话中自动提取画像信息"""
    if not settings.PROFILE_ENABLED or not settings.PROFILE_AUTO_EXTRACTION:
        raise HTTPException(
            status_code=503,
            detail="Profile extraction is disabled"
        )

    extraction_service = get_extraction_service()
    result = await extraction_service.extract_from_conversation(
        db,
        current_agent.agent_id,
        req.conversation_text,
        req.conversation_id
    )

    return ExtractFromConversationResponse(
        facts=result.get('facts', []),
        total_extracted=result.get('total_extracted', 0),
        confidence=result.get('confidence', 0.0),
        extraction_time=result.get('extraction_time', '').isoformat(),
        error=result.get('error')
    )
