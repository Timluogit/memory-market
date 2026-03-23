"""审计日志导出服务"""
import os
import csv
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.tables import AuditLog, AuditLogExport
from app.core.config import settings


class AuditExportService:
    """审计日志导出服务"""

    # 导出文件存储目录
    EXPORT_DIR = Path("exports/audit_logs")
    # 下载链接有效期（24小时）
    LINK_EXPIRY_HOURS = 24

    def __init__(self):
        """初始化导出服务"""
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    async def create_export(
        self,
        db: AsyncSession,
        exported_by_id: str,
        exported_by_name: str,
        export_format: str,
        filters: Dict[str, Any],
        record_count: int,
    ) -> AuditLogExport:
        """
        创建导出任务

        Args:
            db: 数据库会话
            exported_by_id: 导出者ID
            exported_by_name: 导出者名称
            export_format: 导出格式
            filters: 过滤条件
            record_count: 记录数量

        Returns:
            导出任务记录
        """
        export_id = f"exp_{uuid.uuid4().hex[:12]}"

        export = AuditLogExport(
            export_id=export_id,
            exported_by_agent_id=exported_by_id,
            exported_by_name=exported_by_name,
            export_format=export_format,
            filters=filters,
            record_count=record_count,
            status='pending',
            progress=0,
        )

        db.add(export)
        await db.commit()
        await db.refresh(export)

        return export

    async def count_records(
        self,
        db: AsyncSession,
        **filters
    ) -> int:
        """
        根据过滤条件统计记录数

        Args:
            db: 数据库会话
            **filters: 过滤条件

        Returns:
            记录数量
        """
        from sqlalchemy import func, or_

        conditions = []

        # 构建查询条件
        if 'start_date' in filters and filters['start_date']:
            conditions.append(AuditLog.created_at >= filters['start_date'])
        if 'end_date' in filters and filters['end_date']:
            conditions.append(AuditLog.created_at <= filters['end_date'])
        if 'action_type' in filters and filters['action_type']:
            conditions.append(AuditLog.action_type == filters['action_type'])
        if 'action_category' in filters and filters['action_category']:
            conditions.append(AuditLog.action_category == filters['action_category'])
        if 'target_type' in filters and filters['target_type']:
            conditions.append(AuditLog.target_type == filters['target_type'])
        if 'target_id' in filters and filters['target_id']:
            conditions.append(AuditLog.target_id == filters['target_id'])
        if 'actor_id' in filters and filters['actor_id']:
            conditions.append(AuditLog.actor_agent_id == filters['actor_id'])
        if 'status' in filters and filters['status']:
            conditions.append(AuditLog.status == filters['status'])
        if 'keyword' in filters and filters['keyword']:
            keyword = filters['keyword']
            conditions.append(
                or_(
                    AuditLog.target_name.ilike(f"%{keyword}%"),
                    AuditLog.endpoint.ilike(f"%{keyword}%"),
                )
            )

        # 查询总数
        query = select(func.count()).select_from(AuditLog)
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        return result.scalar()

    async def fetch_records(
        self,
        db: AsyncSession,
        **filters
    ) -> List[AuditLog]:
        """
        根据过滤条件获取记录

        Args:
            db: 数据库会话
            **filters: 过滤条件

        Returns:
            审计日志记录列表
        """
        from sqlalchemy import or_

        conditions = []

        # 构建查询条件（与 count_records 相同）
        if 'start_date' in filters and filters['start_date']:
            conditions.append(AuditLog.created_at >= filters['start_date'])
        if 'end_date' in filters and filters['end_date']:
            conditions.append(AuditLog.created_at <= filters['end_date'])
        if 'action_type' in filters and filters['action_type']:
            conditions.append(AuditLog.action_type == filters['action_type'])
        if 'action_category' in filters and filters['action_category']:
            conditions.append(AuditLog.action_category == filters['action_category'])
        if 'target_type' in filters and filters['target_type']:
            conditions.append(AuditLog.target_type == filters['target_type'])
        if 'target_id' in filters and filters['target_id']:
            conditions.append(AuditLog.target_id == filters['target_id'])
        if 'actor_id' in filters and filters['actor_id']:
            conditions.append(AuditLog.actor_agent_id == filters['actor_id'])
        if 'status' in filters and filters['status']:
            conditions.append(AuditLog.status == filters['status'])
        if 'keyword' in filters and filters['keyword']:
            keyword = filters['keyword']
            conditions.append(
                or_(
                    AuditLog.target_name.ilike(f"%{keyword}%"),
                    AuditLog.endpoint.ilike(f"%{keyword}%"),
                )
            )

        # 查询数据
        query = select(AuditLog)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(AuditLog.created_at))

        result = await db.execute(query)
        return result.scalars().all()

    async def perform_export(self, export_id: str):
        """
        执行导出任务（后台任务）

        Args:
            export_id: 导出任务ID
        """
        from app.db.database import async_session_maker

        async with async_session_maker() as db:
            # 获取导出任务
            result = await db.execute(
                select(AuditLogExport).where(AuditLogExport.export_id == export_id)
            )
            export = result.scalar_one_or_none()

            if not export:
                print(f"Export {export_id} not found")
                return

            # 更新状态为处理中
            export.status = 'processing'
            export.progress = 10
            await db.commit()

            try:
                # 获取记录
                records = await self.fetch_records(db, **export.filters)

                # 导出数据
                file_path = await self._export_data(
                    records=records,
                    export_format=export.export_format,
                    export_id=export_id,
                )

                # 更新导出任务
                export.status = 'completed'
                export.progress = 100
                export.file_path = str(file_path)
                export.file_size = file_path.stat().st_size
                export.completed_at = datetime.now()
                export.expires_at = datetime.now() + timedelta(hours=self.LINK_EXPIRY_HOURS)

                await db.commit()

                print(f"Export {export_id} completed successfully")

            except Exception as e:
                # 导出失败
                export.status = 'failed'
                export.error_message = str(e)
                await db.commit()
                print(f"Export {export_id} failed: {e}")

    async def _export_data(
        self,
        records: List[AuditLog],
        export_format: str,
        export_id: str,
    ) -> Path:
        """
        导出数据到文件

        Args:
            records: 审计日志记录
            export_format: 导出格式
            export_id: 导出任务ID

        Returns:
            导出文件路径
        """
        filename = f"audit_logs_{export_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
        file_path = self.EXPORT_DIR / filename

        if export_format == 'csv':
            await self._export_csv(records, file_path)
        elif export_format == 'json':
            await self._export_json(records, file_path)
        elif export_format == 'pdf':
            await self._export_pdf(records, file_path)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        return file_path

    async def _export_csv(self, records: List[AuditLog], file_path: Path):
        """
        导出为 CSV 格式

        Args:
            records: 审计日志记录
            file_path: 文件路径
        """
        # CSV 列名
        fieldnames = [
            'log_id',
            'actor_id',
            'actor_name',
            'action_type',
            'action_category',
            'target_type',
            'target_id',
            'target_name',
            'http_method',
            'endpoint',
            'ip_address',
            'status',
            'status_code',
            'error_message',
            'created_at',
        ]

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for record in records:
                row = {
                    'log_id': record.log_id,
                    'actor_id': record.actor_agent_id,
                    'actor_name': record.actor_name,
                    'action_type': record.action_type,
                    'action_category': record.action_category,
                    'target_type': record.target_type,
                    'target_id': record.target_id,
                    'target_name': record.target_name,
                    'http_method': record.http_method,
                    'endpoint': record.endpoint,
                    'ip_address': record.ip_address,
                    'status': record.status,
                    'status_code': record.status_code,
                    'error_message': record.error_message,
                    'created_at': record.created_at.isoformat() if record.created_at else None,
                }
                writer.writerow(row)

    async def _export_json(self, records: List[AuditLog], file_path: Path):
        """
        导出为 JSON 格式

        Args:
            records: 审计日志记录
            file_path: 文件路径
        """
        data = []
        for record in records:
            data.append({
                'log_id': record.log_id,
                'actor_id': record.actor_agent_id,
                'actor_name': record.actor_name,
                'action_type': record.action_type,
                'action_category': record.action_category,
                'target_type': record.target_type,
                'target_id': record.target_id,
                'target_name': record.target_name,
                'http_method': record.http_method,
                'endpoint': record.endpoint,
                'ip_address': record.ip_address,
                'user_agent': record.user_agent,
                'status': record.status,
                'status_code': record.status_code,
                'error_message': record.error_message,
                'request_data': record.request_data,
                'response_data': record.response_data,
                'changes': record.changes,
                'session_id': record.session_id,
                'request_id': record.request_id,
                'created_at': record.created_at.isoformat() if record.created_at else None,
            })

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def _export_pdf(self, records: List[AuditLog], file_path: Path):
        """
        导出为 PDF 格式

        Args:
            records: 审计日志记录
            file_path: 文件路径
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            raise ImportError("reportlab is required for PDF export. Install with: pip install reportlab")

        # 创建 PDF 文档
        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []

        # 样式
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1E3A8A'),
            alignment=TA_CENTER,
            spaceAfter=30,
        )

        # 标题
        elements.append(Paragraph("Audit Logs Export", title_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Paragraph(f"Total Records: {len(records)}", styles['Normal']))
        elements.append(Spacer(1, 24))

        # 表格数据
        table_data = [['ID', 'Actor', 'Action', 'Target', 'Status', 'Time']]
        for record in records:
            table_data.append([
                record.log_id[:16] + '...' if record.log_id else '',
                record.actor_name or 'N/A',
                f"{record.action_type} ({record.action_category})",
                f"{record.target_type or 'N/A'}:{record.target_id or ''}",
                record.status,
                record.created_at.strftime('%Y-%m-%d %H:%M') if record.created_at else 'N/A',
            ])

        # 创建表格
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))

        # 交替行颜色
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F3F4F6')),
                ]))

        elements.append(table)

        # 生成 PDF
        doc.build(elements)

    async def cleanup_expired_files(self):
        """清理过期的导出文件"""
        now = datetime.now()
        cleaned_count = 0

        for file_path in self.EXPORT_DIR.iterdir():
            if file_path.is_file():
                # 检查文件修改时间（超过48小时删除）
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (now - file_time) > timedelta(hours=48):
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                    except Exception as e:
                        print(f"Failed to delete expired file {file_path}: {e}")

        return cleaned_count
