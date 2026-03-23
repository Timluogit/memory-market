"""
审计服务 - 权限操作审计日志查询和报告

支持：
- 审计日志记录
- 审计日志查询（多条件过滤）
- 审计报告生成
- 异常检测统计
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    PermissionAuditLog, AuditLog, Agent, PermissionPolicy,
    PolicyAttachment, UserPermission, ResourcePermission
)


class AuditService:
    """审计服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 审计日志查询 ==========

    async def query_permission_audit_logs(
        self,
        actor_agent_id: Optional[str] = None,
        action_type: Optional[str] = None,
        action_category: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        permission_code: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        查询权限审计日志

        Args:
            actor_agent_id: 操作者ID
            action_type: 操作类型 (grant/revoke/check)
            action_category: 操作分类 (permission/resource/role)
            target_type: 目标类型
            target_id: 目标ID
            permission_code: 权限代码
            status: 状态 (success/forbidden/error)
            start_time: 开始时间
            end_time: 结束时间
            page: 页码
            page_size: 每页数量

        Returns:
            Dict: 分页审计日志
        """
        query = select(PermissionAuditLog)

        # 构建过滤条件
        filters = []
        if actor_agent_id:
            filters.append(PermissionAuditLog.actor_agent_id == actor_agent_id)
        if action_type:
            filters.append(PermissionAuditLog.action_type == action_type)
        if action_category:
            filters.append(PermissionAuditLog.action_category == action_category)
        if target_type:
            filters.append(PermissionAuditLog.target_type == target_type)
        if target_id:
            filters.append(PermissionAuditLog.target_id == target_id)
        if permission_code:
            filters.append(PermissionAuditLog.permission_code == permission_code)
        if status:
            filters.append(PermissionAuditLog.status == status)
        if start_time:
            filters.append(PermissionAuditLog.created_at >= start_time)
        if end_time:
            filters.append(PermissionAuditLog.created_at <= end_time)

        if filters:
            query = query.where(and_(*filters))

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        # 分页
        query = query.order_by(desc(PermissionAuditLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        return {
            "logs": [
                {
                    "log_id": log.log_id,
                    "actor_agent_id": log.actor_agent_id,
                    "actor_name": log.actor_name,
                    "action_type": log.action_type,
                    "action_category": log.action_category,
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "target_name": log.target_name,
                    "permission_code": log.permission_code,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "status": log.status,
                    "extra_data": log.extra_data,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def query_general_audit_logs(
        self,
        actor_agent_id: Optional[str] = None,
        action_type: Optional[str] = None,
        action_category: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """查询通用审计日志"""
        query = select(AuditLog)

        filters = []
        if actor_agent_id:
            filters.append(AuditLog.actor_agent_id == actor_agent_id)
        if action_type:
            filters.append(AuditLog.action_type == action_type)
        if action_category:
            filters.append(AuditLog.action_category == action_category)
        if target_type:
            filters.append(AuditLog.target_type == target_type)
        if target_id:
            filters.append(AuditLog.target_id == target_id)
        if status:
            filters.append(AuditLog.status == status)
        if start_time:
            filters.append(AuditLog.created_at >= start_time)
        if end_time:
            filters.append(AuditLog.created_at <= end_time)

        if filters:
            query = query.where(and_(*filters))

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        query = query.order_by(desc(AuditLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        return {
            "logs": [
                {
                    "log_id": log.log_id,
                    "actor_agent_id": log.actor_agent_id,
                    "actor_name": log.actor_name,
                    "action_type": log.action_type,
                    "action_category": log.action_category,
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "status": log.status,
                    "http_method": log.http_method,
                    "endpoint": log.endpoint,
                    "ip_address": log.ip_address,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    # ========== 审计报告 ==========

    async def generate_permission_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        生成权限审计报告

        Returns:
            Dict: 包含各种统计数据的报告
        """
        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        if not end_time:
            end_time = datetime.now()

        report = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "summary": {},
            "permission_checks": {},
            "permission_changes": {},
            "top_actors": [],
            "top_permissions": [],
            "failure_analysis": {},
            "policy_statistics": {}
        }

        # 1. 总体摘要
        report["summary"] = await self._get_summary_stats(start_time, end_time)

        # 2. 权限检查统计
        report["permission_checks"] = await self._get_check_stats(start_time, end_time)

        # 3. 权限变更统计
        report["permission_changes"] = await self._get_change_stats(start_time, end_time)

        # 4. Top 操作者
        report["top_actors"] = await self._get_top_actors(start_time, end_time)

        # 5. Top 权限
        report["top_permissions"] = await self._get_top_permissions(start_time, end_time)

        # 6. 失败分析
        report["failure_analysis"] = await self._get_failure_analysis(start_time, end_time)

        # 7. 策略统计
        report["policy_statistics"] = await self._get_policy_stats()

        return report

    async def _get_summary_stats(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """获取总体统计"""
        # 权限审计日志总数
        query = select(func.count()).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time
            )
        )
        result = await self.db.execute(query)
        total_logs = result.scalar()

        # 成功率
        query = select(func.count()).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time,
                PermissionAuditLog.status == "success"
            )
        )
        result = await self.db.execute(query)
        success_count = result.scalar()

        # 唯一操作者数
        query = select(func.count(func.distinct(PermissionAuditLog.actor_agent_id))).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time
            )
        )
        result = await self.db.execute(query)
        unique_actors = result.scalar()

        return {
            "total_audit_logs": total_logs,
            "success_count": success_count,
            "failure_count": total_logs - success_count,
            "success_rate": round(success_count / total_logs * 100, 2) if total_logs > 0 else 0,
            "unique_actors": unique_actors
        }

    async def _get_check_stats(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """权限检查统计"""
        query = select(
            PermissionAuditLog.status,
            func.count().label("count")
        ).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time,
                PermissionAuditLog.action_type == "check"
            )
        ).group_by(PermissionAuditLog.status)

        result = await self.db.execute(query)
        stats = {row.status: row.count for row in result}

        return {
            "total_checks": sum(stats.values()),
            "success": stats.get("success", 0),
            "forbidden": stats.get("forbidden", 0),
            "error": stats.get("error", 0)
        }

    async def _get_change_stats(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """权限变更统计"""
        query = select(
            PermissionAuditLog.action_type,
            func.count().label("count")
        ).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time,
                PermissionAuditLog.action_type.in_(["grant", "revoke"])
            )
        ).group_by(PermissionAuditLog.action_type)

        result = await self.db.execute(query)
        stats = {row.action_type: row.count for row in result}

        return {
            "total_changes": sum(stats.values()),
            "grants": stats.get("grant", 0),
            "revokes": stats.get("revoke", 0)
        }

    async def _get_top_actors(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取 Top 操作者"""
        query = select(
            PermissionAuditLog.actor_agent_id,
            PermissionAuditLog.actor_name,
            func.count().label("action_count"),
            func.sum(
                case((PermissionAuditLog.status == "success", 1), else_=0)
            ).label("success_count")
        ).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time
            )
        ).group_by(
            PermissionAuditLog.actor_agent_id,
            PermissionAuditLog.actor_name
        ).order_by(desc("action_count")).limit(limit)

        result = await self.db.execute(query)
        return [
            {
                "actor_agent_id": row.actor_agent_id,
                "actor_name": row.actor_name,
                "action_count": row.action_count,
                "success_count": row.success_count,
                "success_rate": round(row.success_count / row.action_count * 100, 2) if row.action_count > 0 else 0
            }
            for row in result
        ]

    async def _get_top_permissions(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最常使用的权限"""
        query = select(
            PermissionAuditLog.permission_code,
            func.count().label("check_count"),
            func.sum(
                case((PermissionAuditLog.status == "success", 1), else_=0)
            ).label("success_count")
        ).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time,
                PermissionAuditLog.action_type == "check",
                PermissionAuditLog.permission_code.isnot(None)
            )
        ).group_by(
            PermissionAuditLog.permission_code
        ).order_by(desc("check_count")).limit(limit)

        result = await self.db.execute(query)
        return [
            {
                "permission_code": row.permission_code,
                "check_count": row.check_count,
                "success_count": row.success_count,
                "denial_rate": round(
                    (row.check_count - row.success_count) / row.check_count * 100, 2
                ) if row.check_count > 0 else 0
            }
            for row in result
        ]

    async def _get_failure_analysis(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """失败分析"""
        # 按原因分类失败
        query = select(
            PermissionAuditLog.extra_data,
            func.count().label("count")
        ).where(
            and_(
                PermissionAuditLog.created_at >= start_time,
                PermissionAuditLog.created_at <= end_time,
                PermissionAuditLog.status == "forbidden"
            )
        ).group_by(PermissionAuditLog.extra_data)

        result = await self.db.execute(query)
        reasons = {}
        for row in result:
            extra = row.extra_data or {}
            reason = extra.get("reason", "unknown")
            reasons[reason] = reasons.get(reason, 0) + row.count

        return {
            "total_failures": sum(reasons.values()),
            "by_reason": reasons
        }

    async def _get_policy_stats(self) -> Dict[str, Any]:
        """策略统计"""
        # 总策略数
        query = select(func.count()).where(PermissionPolicy.is_active == True)
        result = await self.db.execute(query)
        total_policies = result.scalar()

        # 按类型统计
        query = select(
            PermissionPolicy.policy_type,
            func.count().label("count")
        ).where(
            PermissionPolicy.is_active == True
        ).group_by(PermissionPolicy.policy_type)

        result = await self.db.execute(query)
        by_type = {row.policy_type: row.count for row in result}

        # 总附加数
        query = select(func.count())
        result = await self.db.execute(
            select(func.count()).select_from(PolicyAttachment)
        )
        total_attachments = result.scalar()

        return {
            "total_policies": total_policies,
            "by_type": by_type,
            "total_attachments": total_attachments
        }

    # ========== 实时审计记录 ==========

    async def log_permission_check(
        self,
        agent_id: str,
        permission_code: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        reason: Optional[str] = None,
        duration_ms: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """记录权限检查审计日志"""
        agent_name = await self._get_agent_name(agent_id)

        log = PermissionAuditLog(
            actor_agent_id=agent_id,
            actor_name=agent_name,
            action_type="check",
            action_category="permission",
            target_type=resource_type,
            target_id=resource_id,
            permission_code=permission_code,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            extra_data={
                "reason": reason,
                "duration_ms": duration_ms,
                "ip_address": ip_address
            }
        )
        self.db.add(log)
        # 注意：commit 应该由调用方负责

    async def log_permission_change(
        self,
        actor_agent_id: str,
        action_type: str,  # grant/revoke
        target_agent_id: Optional[str] = None,
        target_role_id: Optional[str] = None,
        permission_code: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录权限变更审计日志"""
        actor_name = await self._get_agent_name(actor_agent_id)

        log = PermissionAuditLog(
            actor_agent_id=actor_agent_id,
            actor_name=actor_name,
            action_type=action_type,
            action_category="permission",
            target_type="agent" if target_agent_id else ("role" if target_role_id else resource_type),
            target_id=target_agent_id or target_role_id or resource_id,
            permission_code=permission_code,
            resource_type=resource_type,
            resource_id=resource_id,
            status="success",
            extra_data=extra_data
        )
        self.db.add(log)

    async def _get_agent_name(self, agent_id: str) -> str:
        """获取用户名称"""
        query = select(Agent.name).where(Agent.agent_id == agent_id)
        result = await self.db.execute(query)
        name = result.scalar()
        return name or ""
