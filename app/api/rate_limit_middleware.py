"""API Rate Limiting Middleware"""
import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的内存限流中间件"""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {ip: [(timestamp, ...), ...]}
        self.request_counts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"

        # 清理过期记录
        now = time.time()
        cutoff = now - self.window_seconds
        self.request_counts[client_ip] = [
            ts for ts in self.request_counts[client_ip] if ts > cutoff
        ]

        # 检查是否超限
        if len(self.request_counts[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"请求过于频繁，每分钟最多{self.max_requests}次请求",
                        "data": {"retry_after": self.window_seconds}
                    }
                },
                headers={"Retry-After": str(self.window_seconds)}
            )

        # 记录本次请求
        self.request_counts[client_ip].append(now)

        response = await call_next(request)
        return response
