"""
外部数据源 API 端点
提供连接、同步、查询、断开等功能
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
import logging

from ..services.external_source_service import (
    external_source_service,
    SourceType,
    SourceConnection,
    SyncStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external-sources", tags=["External Sources"])


# ============ 请求/响应模型 ============

class ConnectSourceRequest(BaseModel):
    """连接数据源请求"""
    source_type: str = Field(..., description="数据源类型: google_drive, gmail, notion, onedrive, github")
    config: Dict[str, Any] = Field(..., description="配置参数（包含access_token等）")
    source_id: Optional[str] = Field(None, description="自定义源ID，自动生成如果未提供")


class ConnectSourceResponse(BaseModel):
    """连接数据源响应"""
    success: bool
    message: str
    source_id: str
    source_type: str
    status: str


class SyncSourceResponse(BaseModel):
    """同步数据源响应"""
    success: bool
    message: str
    source_id: str
    document_count: int
    sync_status: str
    last_sync: Optional[str]


class FilesListResponse(BaseModel):
    """文件列表响应"""
    source_id: str
    files: List[Dict[str, Any]]
    total: int


class SourceStatusResponse(BaseModel):
    """数据源状态响应"""
    source_id: str
    source_type: str
    enabled: bool
    sync_status: str
    last_sync: Optional[str]
    config: Dict[str, Any]


class SourcesListResponse(BaseModel):
    """数据源列表响应"""
    sources: List[Dict[str, Any]]
    total: int


# ============ API 端点 ============

@router.post("/connect", response_model=ConnectSourceResponse, status_code=status.HTTP_201_CREATED)
async def connect_source(request: ConnectSourceRequest):
    """
    连接外部数据源

    Args:
        request: 连接请求，包含source_type和config

    Returns:
        连接结果
    """
    try:
        # 解析数据源类型
        try:
            source_type = SourceType(request.source_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source type: {request.source_type}"
            )

        # 生成源ID（如果未提供）
        source_id = request.source_id or f"{source_type.value}_{int(datetime.utcnow().timestamp())}"

        # 连接数据源
        connection = await external_source_service.connect_source(
            source_id=source_id,
            source_type=source_type,
            config=request.config,
        )

        logger.info(f"Connected to source {source_id} ({source_type.value})")

        return ConnectSourceResponse(
            success=True,
            message=f"Successfully connected to {source_type.value}",
            source_id=connection.source_id,
            source_type=connection.source_type.value,
            status="connected",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to connect source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect: {str(e)}"
        )


@router.delete("/{source_id}/disconnect")
async def disconnect_source(source_id: str):
    """
    断开外部数据源

    Args:
        source_id: 数据源ID

    Returns:
        断开结果
    """
    try:
        success = await external_source_service.disconnect_source(source_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found: {source_id}"
            )

        logger.info(f"Disconnected source {source_id}")

        return {
            "success": True,
            "message": f"Successfully disconnected from {source_id}",
            "source_id": source_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect: {str(e)}"
        )


@router.post("/{source_id}/sync", response_model=SyncSourceResponse)
async def sync_source(source_id: str, force: bool = False):
    """
    手动同步数据源

    Args:
        source_id: 数据源ID
        force: 强制重新同步（即使正在同步）

    Returns:
        同步结果
    """
    try:
        documents = await external_source_service.sync_source(source_id, force=force)

        connection = await external_source_service.get_source_status(source_id)

        return SyncSourceResponse(
            success=True,
            message=f"Successfully synced {len(documents)} documents",
            source_id=source_id,
            document_count=len(documents),
            sync_status=connection.sync_status.value if connection else "unknown",
            last_sync=connection.last_sync.isoformat() if connection and connection.last_sync else None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to sync source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync: {str(e)}"
        )


@router.get("/{source_id}/files", response_model=FilesListResponse)
async def list_files(source_id: str, folder_id: Optional[str] = None, limit: int = 100):
    """
    列出数据源的文件

    Args:
        source_id: 数据源ID
        folder_id: 文件夹ID（可选）
        limit: 返回数量限制

    Returns:
        文件列表
    """
    try:
        files = await external_source_service.list_files(source_id, folder_id=folder_id, limit=limit)

        return FilesListResponse(
            source_id=source_id,
            files=[f.to_dict() for f in files],
            total=len(files),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/{source_id}/status", response_model=SourceStatusResponse)
async def get_source_status(source_id: str):
    """
    获取数据源状态

    Args:
        source_id: 数据源ID

    Returns:
        数据源状态
    """
    try:
        connection = await external_source_service.get_source_status(source_id)

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source not found: {source_id}"
            )

        return SourceStatusResponse(
            source_id=connection.source_id,
            source_type=connection.source_type.value,
            enabled=connection.enabled,
            sync_status=connection.sync_status.value,
            last_sync=connection.last_sync.isoformat() if connection.last_sync else None,
            config=connection.to_dict()["config"],  # 返回安全的配置（隐藏敏感信息）
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("", response_model=SourcesListResponse)
async def list_sources():
    """
    列出所有已连接的数据源

    Returns:
        数据源列表
    """
    try:
        connections = await external_source_service.list_sources()

        return SourcesListResponse(
            sources=[c.to_dict() for c in connections],
            total=len(connections),
        )

    except Exception as e:
        logger.error(f"Failed to list sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}"
        )


@router.post("/{source_id}/webhook")
async def handle_webhook(source_id: str, payload: Dict[str, Any], signature: Optional[str] = None):
    """
    处理Webhook事件

    Args:
        source_id: 数据源ID
        payload: Webhook负载
        signature: 签名（可选）

    Returns:
        处理结果
    """
    try:
        documents = await external_source_service.handle_webhook(source_id, payload, signature or "")

        logger.info(f"Processed webhook for {source_id}, {len(documents)} documents affected")

        return {
            "success": True,
            "message": f"Webhook processed, {len(documents)} documents affected",
            "source_id": source_id,
            "document_count": len(documents),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to handle webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to handle webhook: {str(e)}"
        )
