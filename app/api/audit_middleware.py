"""审计日志中间件"""
import json
import time
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.db.database import get_db
from app.models.tables import AuditLog, Agent
from app.core.auth import get_current_agent
from app.core.sanitizer import sanitize_request_body, sanitize_response_body


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件"""

    # 不需要审计的端点
    SKIP_ENDPOINTS = {
        '/health',
        '/metrics',
        '/docs',
        '/openapi.json',
    }

    # 操作类型映射
    ACTION_MAP = {
        'GET': 'read',
        'POST': 'create',
        'PUT': 'update',
        'PATCH': 'update',
        'DELETE': 'delete',
    }

    # 操作类别映射
    CATEGORY_MAP = {
        '/api/auth': 'auth',
        '/api/agents': 'agent',
        '/api/memories': 'memory',
        '/api/purchases': 'transaction',
        '/api/transactions': 'transaction',
        '/api/teams': 'team',
        '/api/team-members': 'team',
        '/api/team-activity': 'team',
        '/api/team-stats': 'team',
        '/api/team-credits': 'team',
        '/api/audit-logs': 'system',
    }

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._write_queue = []  # 异步写入队列
        self._queue_size = 100  # 队列大小

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录审计日志"""

        # 跳过不需要审计的端点
        if request.url.path in self.SKIP_ENDPOINTS:
            return await call_next(request)

        # 生成请求追踪ID
        request_id = str(uuid.uuid4())

        # 提取请求信息
        start_time = time.time()
        http_method = request.method
        endpoint = request.url.path
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get('user-agent', '')

        # 获取当前用户
        agent: Optional[Agent] = None
        try:
            # 尝试从请求中获取当前用户（不抛出异常）
            # 注意：这里需要依赖注入，中间件中难以实现
            # 我们将在请求处理函数中获取用户信息
            agent_id = getattr(request.state, 'agent_id', None)
            if agent_id:
                # 从数据库获取用户信息
                async for db in get_db():
                    result = await db.execute(
                        select(Agent).where(Agent.agent_id == agent_id)
                    )
                    agent = result.scalar_one_or_none()
                    break
        except Exception:
            pass

        # 读取请求体（仅支持 JSON）
        request_body = None
        try:
            if request.method in ['POST', 'PUT', 'PATCH']:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes.decode())
                    # 重新设置 request.body 以便后续处理
                    # 注意：FastAPI 的 request.body 只能读取一次
                    # 这里我们使用 request.state 存储脱敏后的数据
                    request.state.raw_body = body_bytes
        except Exception:
            pass

        # 处理请求
        try:
            response = await call_next(request)
            status_code = response.status_code
            status = 'success' if 200 <= status_code < 300 else 'failure'
            error_message = None

            # 尝试读取响应体
            response_body = None
            try:
                if response.body:
                    body_bytes = await response.body()
                    response_body = json.loads(body_bytes.decode())
            except Exception:
                pass

        except Exception as e:
            # 捕获异常
            status_code = 500
            status = 'error'
            error_message = str(e)
            response = Response(
                content=json.dumps({'error': error_message}),
                status_code=status_code,
                media_type='application/json'
            )
            response_body = None

        # 计算处理时间
        duration = time.time() - start_time

        # 异步写入审计日志（不阻塞响应）
        if duration < 5.0:  # 只记录处理时间小于5秒的请求
            self._queue_audit_log(
                request_id=request_id,
                agent=agent,
                http_method=http_method,
                endpoint=endpoint,
                ip_address=ip_address,
                user_agent=user_agent,
                request_body=request_body,
                response_body=response_body,
                status=status,
                status_code=status_code,
                error_message=error_message,
                duration=duration,
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头部
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip

        return request.client.host if request.client else 'unknown'

    def _queue_audit_log(
        self,
        request_id: str,
        agent: Optional[Agent],
        http_method: str,
        endpoint: str,
        ip_address: str,
        user_agent: str,
        request_body: Optional[dict],
        response_body: Optional[dict],
        status: str,
        status_code: int,
        error_message: Optional[str],
        duration: float,
    ):
        """将审计日志加入队列（异步写入）"""

        def get_action_type(endpoint: str, method: str) -> str:
            """从端点和方法推断操作类型"""
            for path_prefix, action in self.CATEGORY_MAP.items():
                if endpoint.startswith(path_prefix):
                    # 根据HTTP方法和端点特征判断具体操作
                    if 'login' in endpoint:
                        return 'login'
                    elif 'logout' in endpoint:
                        return 'logout'
                    elif 'export' in endpoint:
                        return 'export'
                    elif method in self.ACTION_MAP:
                        return self.ACTION_MAP[method]
            return 'unknown'

        def get_action_category(endpoint: str) -> str:
            """从端点推断操作类别"""
            for path_prefix, category in self.CATEGORY_MAP.items():
                if endpoint.startswith(path_prefix):
                    return category
            return 'system'

        # 解析目标对象
        target_type, target_id = self._parse_target(endpoint)

        action_type = get_action_type(endpoint, http_method)
        action_category = get_action_category(endpoint)

        # 脱敏请求数据
        sanitized_request = sanitize_request_body(request_body)
        sanitized_response = sanitize_response_body(response_body)

        # 创建日志记录
        log_entry = {
            'actor_agent_id': agent.agent_id if agent else None,
            'actor_name': agent.name if agent else 'system',
            'action_type': action_type,
            'action_category': action_category,
            'target_type': target_type,
            'target_id': target_id,
            'http_method': http_method,
            'endpoint': endpoint,
            'ip_address': ip_address,
            'user_agent': user_agent[:500] if user_agent else None,
            'status': status,
            'status_code': status_code,
            'error_message': error_message,
            'request_data': sanitized_request,
            'response_data': sanitized_response,
            'session_id': request_id,
            'request_id': request_id,
        }

        # 添加到队列
        self._write_queue.append(log_entry)

        # 队列满时批量写入
        if len(self._write_queue) >= self._queue_size:
            self._flush_queue()

    def _parse_target(self, endpoint: str) -> tuple:
        """
        从端点解析目标对象

        Args:
            endpoint: API端点，如 /api/memories/mem_xxx123

        Returns:
            (target_type, target_id) 元组
        """
        parts = endpoint.strip('/').split('/')
        if len(parts) >= 2:
            # 第二部分通常是资源类型
            resource_type = parts[1]
            # 第三部分（如果有）通常是资源ID
            if len(parts) >= 3:
                resource_id = parts[2]
                # 将资源类型转换为模型类型
                type_map = {
                    'agents': 'agent',
                    'memories': 'memory',
                    'purchases': 'purchase',
                    'transactions': 'transaction',
                    'teams': 'team',
                    'team-members': 'team_member',
                }
                return type_map.get(resource_type, resource_type), resource_id
        return None, None

    def _flush_queue(self):
        """批量写入队列中的日志（同步）"""
        if not self._write_queue:
            return

        # 注意：这里应该使用后台任务或异步写入
        # 为了简化，我们使用数据库会话
        import asyncio
        try:
            # 获取事件循环
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_flush_queue())
        except RuntimeError:
            pass

    async def _async_flush_queue(self):
        """异步批量写入队列中的日志"""
        if not self._write_queue:
            return

        logs_to_write = self._write_queue.copy()
        self._write_queue.clear()

        try:
            async for db in get_db():
                # 批量插入
                for log_data in logs_to_write:
                    try:
                        await db.execute(insert(AuditLog).values(**log_data))
                    except Exception as e:
                        # 单条记录失败不影响其他记录
                        print(f"Failed to write audit log: {e}")

                await db.commit()
                break

        except Exception as e:
            print(f"Failed to flush audit log queue: {e}")


# 辅助函数：记录特定操作的审计日志
async def log_audit_event(
    db: AsyncSession,
    actor_id: str,
    actor_name: str,
    action_type: str,
    action_category: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    status: str = 'success',
    status_code: int = 200,
    error_message: Optional[str] = None,
    request_data: Optional[dict] = None,
    response_data: Optional[dict] = None,
    changes: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AuditLog:
    """
    记录审计日志事件

    Args:
        db: 数据库会话
        actor_id: 操作者ID
        actor_name: 操作者名称
        action_type: 操作类型
        action_category: 操作类别
        target_type: 目标类型
        target_id: 目标ID
        target_name: 目标名称
        status: 状态
        status_code: 状态码
        error_message: 错误消息
        request_data: 请求数据
        response_data: 响应数据
        changes: 变更详情
        ip_address: IP地址
        user_agent: 用户代理
        session_id: 会话ID

    Returns:
        创建的审计日志记录
    """
    request_id = str(uuid.uuid4())

    # 脱敏数据
    sanitized_request = sanitize_request_body(request_data)
    sanitized_response = sanitize_response_body(response_data)

    # 创建审计日志
    audit_log = AuditLog(
        actor_agent_id=actor_id,
        actor_name=actor_name,
        action_type=action_type,
        action_category=action_category,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        status=status,
        status_code=status_code,
        error_message=error_message,
        request_data=sanitized_request,
        response_data=sanitized_response,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        session_id=session_id or request_id,
        request_id=request_id,
    )

    db.add(audit_log)
    await db.flush()  # 获取 log_id 但不提交

    return audit_log
