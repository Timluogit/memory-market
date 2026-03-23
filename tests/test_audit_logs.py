"""审计日志功能测试"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AuditLog, AuditLogExport, Agent
from app.core.sanitizer import Sanitizer, sanitize, sanitize_dict
from app.api.audit_middleware import log_audit_event
from app.services.audit_export_service import AuditExportService
from app.services.audit_retention_service import AuditRetentionService


# ============ 脱敏功能测试 ============

def test_sanitizer_password_masking():
    """测试密码脱敏"""
    sanitizer = Sanitizer()

    # 测试直接脱敏
    assert sanitizer.mask_value("password123", "password") == "***********"
    assert sanitizer.mask_value("test_pwd", "pwd") == "********"

    # 测试字典脱敏
    data = {
        "username": "test_user",
        "password": "secret123",
        "email": "test@example.com",
    }
    sanitized = sanitizer.sanitize_dict(data)

    assert sanitized["username"] == "test_user"
    assert sanitized["password"] == "***"
    # 邮箱会被部分脱敏（保留首字符和域名）
    # email 字段名会被检测为敏感，但邮箱内容会通过正则检测并部分脱敏


def test_sanitizer_api_key_masking():
    """测试 API Key 脱敏"""
    sanitizer = Sanitizer()

    data = {
        "api_key": "sk-1234567890abcdef",
        "name": "test",
    }
    sanitized = sanitizer.sanitize_dict(data)

    assert sanitized["api_key"] == "***"
    assert sanitized["name"] == "test"


def test_sanitizer_credit_card():
    """测试信用卡号脱敏"""
    sanitizer = Sanitizer()

    credit_card = "4111111111111111"
    masked = sanitizer._mask_sensitive_content(credit_card)

    # 应该保留最后4位
    assert masked.endswith("1111")
    assert masked.startswith("*")


def test_sanitizer_email():
    """测试邮箱脱敏"""
    sanitizer = Sanitizer()

    email = "testuser@example.com"
    masked = sanitizer._mask_sensitive_content(email)

    # 应该保留首字符和域名
    assert masked.startswith("t")
    assert "@" in masked
    assert "example.com" in masked


def test_sanitizer_json_body():
    """测试 JSON 请求体脱敏"""
    sanitizer = Sanitizer()

    json_body = '''
    {
        "username": "john",
        "password": "secret123",
        "email": "john@example.com",
        "data": {
            "token": "abc123def456",
            "value": "test"
        }
    }
    '''

    sanitized = sanitizer.sanitize_request_body(json_body)

    # 检查敏感字段是否被脱敏
    assert "secret123" not in str(sanitized)
    assert "abc123def456" not in str(sanitized)
    # 邮箱被部分脱敏（保留首字符和域名）
    assert "@example.com" in sanitized.get("email", "")  # 域名应该保留


def test_global_sanitize_functions():
    """测试全局脱敏函数"""
    # 测试字典
    data = {"password": "secret", "name": "test"}
    result = sanitize_dict(data)
    assert result["password"] == "***"
    assert result["name"] == "test"

    # 测试单个值
    assert sanitize("value", "password") == "*****"
    assert sanitize("normal", "name") == "normal"


# ============ 审计日志测试 ============

@pytest.mark.asyncio
async def test_create_audit_log(db: AsyncSession):
    """测试创建审计日志"""
    from app.db.database import async_session_maker

    # 创建测试用户
    agent = Agent(
        name="Test Agent",
        api_key="test_api_key_123",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # 创建审计日志
    log = await log_audit_event(
        db=db,
        actor_id=agent.agent_id,
        actor_name=agent.name,
        action_type="create",
        action_category="memory",
        target_type="memory",
        target_id="mem_test123",
        target_name="Test Memory",
        status="success",
        status_code=200,
        request_data={"title": "Test"},
        response_data={"id": "mem_test123"},
    )

    assert log.log_id is not None
    assert log.actor_agent_id == agent.agent_id
    assert log.action_type == "create"
    assert log.target_type == "memory"
    assert log.status == "success"

    await db.commit()


@pytest.mark.asyncio
async def test_audit_log_filtering(db: AsyncSession):
    """测试审计日志过滤"""
    # 创建多个审计日志
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)
    await db.commit()

    # 创建不同类型的日志
    logs_to_create = [
        {
            "action_type": "create",
            "action_category": "memory",
            "status": "success",
        },
        {
            "action_type": "update",
            "action_category": "memory",
            "status": "success",
        },
        {
            "action_type": "delete",
            "action_category": "memory",
            "status": "failure",
        },
    ]

    for log_data in logs_to_create:
        await log_audit_event(
            db=db,
            actor_id=agent.agent_id,
            actor_name=agent.name,
            **log_data,
        )

    await db.commit()

    # 测试过滤
    from sqlalchemy import select

    # 按操作类型过滤
    result = await db.execute(
        select(AuditLog).where(AuditLog.action_type == "create")
    )
    create_logs = result.scalars().all()
    assert len(create_logs) >= 1

    # 按状态过滤
    result = await db.execute(
        select(AuditLog).where(AuditLog.status == "success")
    )
    success_logs = result.scalars().all()
    assert len(success_logs) >= 2


# ============ 导出功能测试 ============

@pytest.mark.asyncio
async def test_export_service_count_records(db: AsyncSession):
    """测试导出服务统计记录"""
    export_service = AuditExportService()

    # 创建测试数据
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)

    for i in range(10):
        await log_audit_event(
            db=db,
            actor_id=agent.agent_id,
            actor_name=agent.name,
            action_type="create",
            action_category="memory",
            status="success",
        )

    await db.commit()

    # 测试统计
    count = await export_service.count_records(db)
    assert count >= 10

    # 测试带过滤条件的统计
    count_filtered = await export_service.count_records(db, action_type="create")
    assert count_filtered >= 10


@pytest.mark.asyncio
async def test_export_create_export_task(db: AsyncSession):
    """测试创建导出任务"""
    export_service = AuditExportService()

    # 创建测试用户
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)
    await db.commit()

    # 创建导出任务
    export = await export_service.create_export(
        db=db,
        exported_by_id=agent.agent_id,
        exported_by_name=agent.name,
        export_format="csv",
        filters={},
        record_count=0,
    )

    assert export.export_id is not None
    assert export.export_format == "csv"
    assert export.status == "pending"
    assert export.progress == 0


@pytest.mark.asyncio
async def test_export_csv(db: AsyncSession, tmp_path):
    """测试 CSV 导出"""
    from pathlib import Path

    # 创建测试数据
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)
    await db.commit()

    # 创建审计日志
    await log_audit_event(
        db=db,
        actor_id=agent.agent_id,
        actor_name=agent.name,
        action_type="create",
        action_category="memory",
        target_id="mem_test",
        target_name="Test Memory",
        status="success",
    )
    await db.commit()

    # 获取记录
    export_service = AuditExportService()
    records = await export_service.fetch_records(db)

    # 导出为 CSV
    import asyncio

    # 临时修改导出目录
    original_dir = export_service.EXPORT_DIR
    export_service.EXPORT_DIR = Path(tmp_path)

    try:
        file_path = await export_service._export_data(
            records=records,
            export_format="csv",
            export_id="test123",
        )

        # 验证文件存在
        assert file_path.exists()
        assert file_path.suffix == ".csv"

        # 验证内容
        import csv

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 1
            assert rows[0]['action_type'] == 'create'

    finally:
        # 恢复原始目录
        export_service.EXPORT_DIR = original_dir


# ============ 保留策略测试 ============

@pytest.mark.asyncio
async def test_retention_cleanup(db: AsyncSession):
    """测试保留清理"""
    retention_service = AuditRetentionService(retention_days=7)

    # 创建测试数据（包含过期记录）
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)

    # 创建10天前的日志（应该被删除）
    old_log = AuditLog(
        actor_agent_id=agent.agent_id,
        actor_name="Test",
        action_type="create",
        action_category="memory",
        status="success",
        created_at=datetime.now() - timedelta(days=10),
    )
    db.add(old_log)

    # 创建昨天的日志（应该保留）
    new_log = AuditLog(
        actor_agent_id=agent.agent_id,
        actor_name="Test",
        action_type="create",
        action_category="memory",
        status="success",
        created_at=datetime.now() - timedelta(days=1),
    )
    db.add(new_log)

    await db.commit()

    # 运行清理
    stats = await retention_service.cleanup_expired_logs(db)

    # 验证结果
    assert stats["deleted_count"] >= 1

    # 验证过期日志已被删除
    from sqlalchemy import select

    result = await db.execute(
        select(AuditLog).where(AuditLog.log_id == old_log.log_id)
    )
    assert result.scalar_one_or_none() is None

    # 验证新日志仍然存在
    result = await db.execute(
        select(AuditLog).where(AuditLog.log_id == new_log.log_id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_retention_stats(db: AsyncSession):
    """测试保留统计"""
    retention_service = AuditRetentionService(retention_days=90)

    # 创建测试数据
    agent = Agent(name="Test Agent", api_key="test_key")
    db.add(agent)

    # 创建不同时间的日志
    for days_ago in [1, 7, 30, 100]:
        log = AuditLog(
            actor_agent_id=agent.agent_id,
            actor_name="Test",
            action_type="create",
            action_category="memory",
            status="success",
            created_at=datetime.now() - timedelta(days=days_ago),
        )
        db.add(log)

    await db.commit()

    # 获取统计信息
    stats = await retention_service.get_retention_stats(db)

    assert stats["total_records"] >= 4
    assert stats["active_records"] >= 3  # 1, 7, 30天的
    assert stats["expired_records"] >= 1  # 100天的
    assert stats["retention_days"] == 90


# ============ 中间件测试（简化） ============

def test_action_type_mapping():
    """测试操作类型映射"""
    from app.api.audit_middleware import AuditMiddleware

    middleware = AuditMiddleware(app=None)

    # 测试 HTTP 方法映射
    assert 'GET' in middleware.ACTION_MAP
    assert 'POST' in middleware.ACTION_MAP
    assert 'PUT' in middleware.ACTION_MAP
    assert 'DELETE' in middleware.ACTION_MAP


def test_category_mapping():
    """测试操作类别映射"""
    from app.api.audit_middleware import AuditMiddleware

    middleware = AuditMiddleware(app=None)

    # 测试端点到类别的映射
    assert '/api/auth' in middleware.CATEGORY_MAP
    assert '/api/memories' in middleware.CATEGORY_MAP
    assert '/api/teams' in middleware.CATEGORY_MAP


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
