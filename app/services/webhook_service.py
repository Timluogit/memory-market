"""
Webhook 服务
处理外部数据源的实时同步事件
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import asyncio
import json

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Webhook事件"""

    def __init__(
        self,
        event_id: str,
        source_id: str,
        event_type: str,
        payload: Dict[str, Any],
        received_at: datetime,
        processed_at: Optional[datetime] = None,
        status: str = "pending",
        error: Optional[str] = None,
    ):
        self.event_id = event_id
        self.source_id = source_id
        self.event_type = event_type
        self.payload = payload
        self.received_at = received_at
        self.processed_at = processed_at
        self.status = status  # pending, processing, completed, failed
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "received_at": self.received_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status,
            "error": self.error,
        }


class WebhookService:
    """Webhook服务"""

    def __init__(self):
        self._pending_events: List[WebhookEvent] = []
        self._processing_events: Dict[str, WebhookEvent] = {}
        self._max_retry = 3
        self._retry_delay = 5  # 秒

    async def receive_webhook(
        self,
        source_id: str,
        event_type: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> WebhookEvent:
        """
        接收Webhook事件

        Args:
            source_id: 数据源ID
            event_type: 事件类型
            payload: 事件负载
            signature: 签名（可选）

        Returns:
            Webhook事件
        """
        event_id = f"evt_{int(datetime.utcnow().timestamp() * 1000)}_{source_id}"

        event = WebhookEvent(
            event_id=event_id,
            source_id=source_id,
            event_type=event_type,
            payload=payload,
            received_at=datetime.utcnow(),
            status="pending",
        )

        self._pending_events.append(event)
        logger.info(f"Received webhook event {event_id} from {source_id}")

        # 异步处理事件
        asyncio.create_task(self._process_event(event))

        return event

    async def _process_event(self, event: WebhookEvent):
        """处理Webhook事件"""
        event.status = "processing"
        event.processed_at = datetime.utcnow()

        try:
            # 导入外部源服务
            from .external_source_service import external_source_service

            # 处理事件
            documents = await external_source_service.handle_webhook(
                event.source_id,
                event.payload,
                event.payload.get("signature", ""),
            )

            event.status = "completed"
            logger.info(f"Processed webhook event {event.event_id}, {len(documents)} documents")

        except Exception as e:
            event.status = "failed"
            event.error = str(e)
            logger.error(f"Failed to process webhook event {event.event_id}: {e}")

            # 重试逻辑
            if self._should_retry(event):
                await asyncio.sleep(self._retry_delay)
                event.status = "pending"
                self._pending_events.append(event)
                asyncio.create_task(self._process_event(event))

    def _should_retry(self, event: WebhookEvent) -> bool:
        """判断是否应该重试"""
        # 统计失败次数
        retry_count = sum(
            1 for e in self._pending_events + list(self._processing_events.values())
            if e.event_id == event.event_id and e.status == "failed"
        )

        return retry_count < self._max_retry

    async def get_event_status(self, event_id: str) -> Optional[WebhookEvent]:
        """获取事件状态"""
        # 检查待处理事件
        for event in self._pending_events:
            if event.event_id == event_id:
                return event

        # 检查处理中事件
        if event_id in self._processing_events:
            return self._processing_events[event_id]

        return None

    async def list_events(
        self,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[WebhookEvent]:
        """
        列出事件

        Args:
            source_id: 数据源ID过滤（可选）
            status: 状态过滤（可选）
            limit: 返回数量限制

        Returns:
            事件列表
        """
        all_events = self._pending_events + list(self._processing_events.values())

        # 过滤
        if source_id:
            all_events = [e for e in all_events if e.source_id == source_id]
        if status:
            all_events = [e for e in all_events if e.status == status]

        # 排序（最新优先）
        all_events.sort(key=lambda e: e.received_at, reverse=True)

        return all_events[:limit]

    async def retry_event(self, event_id: str) -> bool:
        """重试失败的事件"""
        event = await self.get_event_status(event_id)

        if not event:
            return False

        if event.status != "failed":
            return False

        # 重置状态
        event.status = "pending"
        event.error = None

        # 重新处理
        asyncio.create_task(self._process_event(event))

        logger.info(f"Retrying webhook event {event_id}")
        return True

    async def clear_old_events(self, older_than_hours: int = 24):
        """清理旧事件"""
        cutoff = datetime.utcnow().timestamp() - (older_than_hours * 3600)

        self._pending_events = [
            e for e in self._pending_events
            if e.received_at.timestamp() > cutoff
        ]

        self._processing_events = {
            k: v for k, v in self._processing_events.items()
            if v.received_at.timestamp() > cutoff
        }

        logger.info(f"Cleared old webhook events, cutoff: {older_than_hours}h")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pending_count = len(self._pending_events)
        processing_count = len(self._processing_events)

        # 统计各状态数量
        status_counts = {}
        for event in self._pending_events + list(self._processing_events.values()):
            status_counts[event.status] = status_counts.get(event.status, 0) + 1

        return {
            "pending_count": pending_count,
            "processing_count": processing_count,
            "total_count": pending_count + processing_count,
            "status_counts": status_counts,
        }


# 全局Webhook服务实例
webhook_service = WebhookService()
