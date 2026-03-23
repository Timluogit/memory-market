"""
OpenTelemetry 监控和可观测性系统

集成 Tracing、Metrics 和 Logs，提供完整的监控能力。
"""

from opentelemetry import trace
from opentelemetry import metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

from .tracing import setup_tracing
from .metrics import setup_metrics
from ..core.logging import get_logger

logger = get_logger(__name__)


def setup_telemetry(
    service_name: str = "memory-market",
    jaeger_endpoint: str = "http://localhost:4317",
    prometheus_port: int = 9464,
    environment: str = "production"
) -> tuple[TracerProvider, MeterProvider]:
    """
    配置完整的 OpenTelemetry 系统

    Args:
        service_name: 服务名称
        jaeger_endpoint: Jaeger collector 端点
        prometheus_port: Prometheus metrics 端口
        environment: 环境标识 (development/staging/production)

    Returns:
        (tracer_provider, meter_provider) 元组
    """
    # 创建资源标识
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "1.0.0",
        "deployment.environment": environment,
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "opentelemetry"
    })

    # 设置 Tracing
    tracer_provider = setup_tracing(
        resource=resource,
        jaeger_endpoint=jaeger_endpoint
    )
    logger.info(f"Tracing configured: Jaeger endpoint {jaeger_endpoint}")

    # 设置 Metrics
    meter_provider = setup_metrics(
        resource=resource,
        prometheus_port=prometheus_port
    )
    logger.info(f"Metrics configured: Prometheus port {prometheus_port}")

    # 设置全局 providers
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)

    logger.info("OpenTelemetry telemetry system initialized successfully")

    return tracer_provider, meter_provider


def get_tracer(name: str = __name__):
    """获取 tracer 实例"""
    return trace.get_tracer(name)


def get_meter(name: str = __name__):
    """获取 meter 实例"""
    return metrics.get_meter(name)


def shutdown_telemetry(tracer_provider: TracerProvider, meter_provider: MeterProvider):
    """关闭 OpenTelemetry 系统，确保数据导出完成"""
    logger.info("Shutting down telemetry system...")
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger.info("Telemetry system shutdown complete")
