"""统一异常处理"""
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from typing import Any


class AppError(Exception):
    """应用基础异常类"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        data: Any = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


# ============ 常见错误定义 ============

# 4xx 客户端错误
NOT_FOUND = AppError("NOT_FOUND", "资源不存在", 404)
UNAUTHORIZED = AppError("UNAUTHORIZED", "请先登录", 401)
FORBIDDEN = AppError("FORBIDDEN", "无权限访问", 403)
INVALID_PARAMS = AppError("INVALID_PARAMS", "参数错误", 400)
ALREADY_EXISTS = AppError("ALREADY_EXISTS", "资源已存在", 409)
INSUFFICIENT_BALANCE = AppError("INSUFFICIENT_BALANCE", "余额不足", 400)
NOT_PURCHASED = AppError("NOT_PURCHASED", "未购买该记忆", 403)
SELF_PURCHASE_FORBIDDEN = AppError("SELF_PURCHASE_FORBIDDEN", "不能购买自己的记忆", 400)

# 5xx 服务器错误
INTERNAL_ERROR = AppError("INTERNAL_ERROR", "服务器内部错误", 500)
DATABASE_ERROR = AppError("DATABASE_ERROR", "数据库错误", 500)


# ============ 辅助函数 ============

def success_response(data: Any = None) -> dict:
    """统一成功响应格式"""
    return {
        "success": True,
        "data": data
    }


def error_response(code: str, message: str, status_code: int = 400, data: Any = None) -> dict:
    """统一错误响应格式"""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "data": data
        }
    }
