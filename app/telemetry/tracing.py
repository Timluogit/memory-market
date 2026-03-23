"""
OpenTelemetry Tracing 配置

提供分布式链路追踪能力，集成 Jaeger 作为追踪后端。
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI
import httpx
import sqlalchemy

from ..core.logging import get_logger

logger = get_logger(__name__)


def setup_tracing(
    resource: Resource,
    jaeger_endpoint: str = "http://localhost:4317",
    sample_rate: float = 0.1
) -> TracerProvider:
    """
    配置 OpenTelemetry Tracing

    Args:
        resource: 服务资源标识
        jaeger_endpoint: Jaeger OTLP collector 端点
        sample_rate: 采样率 (0.0-1.0)，生产环境建议 0.1

    Returns:
        TracerProvider 实例
    """
    # 创建 tracer provider
    provider = TracerProvider(resource=resource)

    # 配置采样率
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    sampler = TraceIdRatioBased(sample_rate)
    provider.sampler = sampler

    # 创建 OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=jaeger_endpoint,
        insecure=True
    )

    # 添加 batch processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    return provider


def instrument_fastapi(app: FastAPI, excluded_urls: list[str] | None = None):
    """
    为 FastAPI 应用添加自动追踪

    Args:
        app: FastAPI 应用实例
        excluded_urls: 排除追踪的 URL 路径列表
    """
    # 配置要排除的路径
    excluded = set(excluded_urls) if excluded_urls else {
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    }

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=trace.get_tracer_provider(),
        excluded_urls=list(excluded)
    )

    logger.info("FastAPI tracing instrumentation enabled")


def instrument_httpx():
    """为 HTTPX 客户端添加追踪"""
    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX client tracing instrumentation enabled")


def instrument_sqlalchemy(engine: sqlalchemy.engine.Engine):
    """
    为 SQLAlchemy 添加数据库查询追踪

    Args:
        engine: SQLAlchemy 引擎实例
    """
    SQLAlchemyInstrumentor().instrument(
        engine=engine,
        tracer_provider=trace.get_tracer_provider()
    )
    logger.info("SQLAlchemy tracing instrumentation enabled")


def get_trace_id() -> str:
    """
    获取当前 trace ID

    Returns:
        当前 trace ID 字符串，如果没有活跃 trace 则返回空字符串
    """
    current_span = trace.get_current_span()
    if current_span is not None and current_span.context is not None:
        return format(current_span.context.trace_id, '032x')
    return ""


def inject_trace_context(headers: dict) -> dict:
    """
    将 trace context 注入到 HTTP headers 中

    Args:
        headers: 目标 headers 字典

    Returns:
        更新后的 headers 字典
    """
    propagator = TraceContextTextMapPropagator()
    propagator.inject(headers)
    return headers


def extract_trace_context(headers: dict) -> dict:
    """
    从 HTTP headers 中提取 trace context

    Args:
        headers: HTTP headers 字典

    Returns:
        trace context 字典
    """
    propagator = TraceContextTextMapPropagator()
    context = propagator.extract(headers)
    return context


class TraceContextMiddleware(BaseHTTPMiddleware):
    """
    自定义中间件：确保 trace context 在请求间传播
    """

    async def dispatch(self, request: Request, call_next):
        # 提取传入的 trace context
        headers = dict(request.headers)
        extract_trace_context(headers)

        # 添加 trace ID 到请求 state，供日志使用
        trace_id = get_trace_id()
        if trace_id:
            request.state.trace_id = trace_id

        # 处理请求
        response = await call_next(request)

        # 将 trace ID 添加到响应头
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id

        return response


def add_tracing_middleware(app: FastAPI):
    """
    为 FastAPI 应用添加追踪中间件

    Args:
        app: FastAPI 应用实例
    """
    app.add_middleware(TraceContextMiddleware)
    logger.info("Trace context middleware added to FastAPI")
