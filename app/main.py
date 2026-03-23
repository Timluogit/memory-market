"""Agent记忆市场 - 主应用"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.db.database import init_db
from app.api.routes import router
from app.core.exceptions import AppError

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库
    await init_db()

    # 初始化缓存系统
    if settings.CACHE_ENABLED:
        from app.api.search_cache_middleware import get_search_cache_middleware
        from app.services.cache_invalidation_service import get_cache_invalidation_service

        try:
            # 初始化搜索缓存中间件
            cache_middleware = await get_search_cache_middleware()
            print(f"✅ 搜索缓存中间件初始化成功 (TTL: {settings.CACHE_TTL}s)")

            # 初始化缓存失效服务
            invalidation_service = await get_cache_invalidation_service()
            print(f"✅ 缓存失效服务初始化成功")

        except Exception as e:
            print(f"⚠️  缓存系统初始化失败: {e}")
            print(f"💡 请确保Redis已启动: {settings.REDIS_URL}")

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动完成")
    yield
    # 关闭时清理
    print("👋 应用关闭")

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agent记忆市场 - 让AI Agent共享和交易工作经验",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 审计日志中间件
from app.api.audit_middleware import AuditMiddleware
app.add_middleware(AuditMiddleware)

# 注册路由
app.include_router(router, prefix="/api/v1")

# 注册交易路由
from app.api.transactions import router as transactions_router
app.include_router(transactions_router)

# 注册团队管理路由
from app.api.teams import router as teams_router
from app.api.team_members import router as team_members_router
from app.api.team_credits import router as team_credits_router

app.include_router(teams_router, prefix="/api")
app.include_router(team_members_router, prefix="/api")
app.include_router(team_credits_router, prefix="/api")

# 全局异常处理器
from fastapi.requests import Request

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """处理自定义应用异常"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "data": exc.data
            }
        }
    )

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 重定向根路径到首页
from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/static/home.html")

# 健康检查
@app.get("/health")
async def health_check():
    from app.core.exceptions import success_response
    return success_response({
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
