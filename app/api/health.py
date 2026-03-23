"""Health check endpoints for HA deployment.

Provides liveness, readiness, and general health checks
used by Docker, Nginx, and monitoring systems.
"""
from fastapi import APIRouter
from datetime import datetime, timezone
import asyncio
import os
import platform

router = APIRouter(tags=["health"])

_start_time = datetime.now(timezone.utc)

# Track readiness state
_ready = False


def set_ready(state: bool):
    """Set readiness state (called from lifespan)."""
    global _ready
    _ready = state


def _uptime_seconds() -> float:
    return (datetime.now(timezone.utc) - _start_time).total_seconds()


# ---- Liveness: is the process alive? (Docker HEALTHCHECK) ----
@router.get("/health/live", summary="Liveness probe")
async def liveness():
    """Returns 200 if the process is running. Used by Docker HEALTHCHECK."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---- Readiness: can the app serve traffic? (Nginx / orchestrator) ----
@router.get("/health/ready", summary="Readiness probe")
async def readiness():
    """Returns 200 when all dependencies (DB, Redis) are reachable."""
    checks = {}
    all_ok = True

    # Database check
    try:
        from app.db.database import async_session
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        all_ok = False

    # Redis check (optional — degrade gracefully)
    try:
        from app.cache.redis_client import get_redis_client
        redis_client = await get_redis_client()
        if redis_client:
            await redis_client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_configured"
    except Exception:
        checks["redis"] = "unavailable"

    status_code = 200 if all_ok else 503
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---- General health: summary for monitoring ----
@router.get("/health", summary="Health summary")
async def health():
    """Comprehensive health check for monitoring dashboards."""
    return {
        "status": "healthy",
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "uptime_seconds": round(_uptime_seconds(), 1),
        "hostname": platform.node(),
        "pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
