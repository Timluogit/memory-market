"""
OpenTelemetry Metrics 配置

提供指标收集能力，集成 Prometheus 作为指标导出后端。
"""

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server
from typing import Counter, Histogram, Gauge, ObservableGauge

from ..core.logging import get_logger

logger = get_logger(__name__)

# 全局指标实例
http_requests_total: Counter = None
http_request_duration: Histogram = None
active_users: Gauge = None
total_memories: Gauge = None
total_transactions: Gauge = None
search_latency: Histogram = None
qdrant_query_duration: Histogram = None
db_query_duration: Histogram = None


def setup_metrics(
    resource: Resource,
    prometheus_port: int = 9464
) -> MeterProvider:
    """
    配置 OpenTelemetry Metrics

    Args:
        resource: 服务资源标识
        prometheus_port: Prometheus metrics 端口

    Returns:
        MeterProvider 实例
    """
    # 创建 Prometheus exporter reader
    reader = PrometheusMetricReader()

    # 创建 meter provider
    provider = MeterProvider(metric_readers=[reader], resource=resource)

    return provider


def create_common_metrics(meter: metrics.Meter):
    """
    创建通用指标

    Args:
        meter: OpenTelemetry Meter 实例
    """
    global http_requests_total, http_request_duration, active_users
    global total_memories, total_transactions, search_latency
    global qdrant_query_duration, db_query_duration

    # HTTP 请求总数
    http_requests_total = meter.create_counter(
        name="http_requests_total",
        description="Total number of HTTP requests",
        unit="1"
    )

    # HTTP 请求延迟直方图
    http_request_duration = meter.create_histogram(
        name="http_request_duration_seconds",
        description="HTTP request latency",
        unit="s"
    )

    # 活跃用户数
    active_users = meter.create_up_down_counter(
        name="active_users_total",
        description="Number of active users",
        unit="1"
    )

    # 记忆总数
    total_memories = meter.create_up_down_counter(
        name="memories_total",
        description="Total number of memories",
        unit="1"
    )

    # 交易总数
    total_transactions = meter.create_counter(
        name="transactions_total",
        description="Total number of transactions",
        unit="1"
    )

    # 搜索延迟直方图
    search_latency = meter.create_histogram(
        name="search_duration_seconds",
        description="Search operation latency",
        unit="s"
    )

    # Qdrant 查询延迟
    qdrant_query_duration = meter.create_histogram(
        name="qdrant_query_duration_seconds",
        description="Qdrant query latency",
        unit="s"
    )

    # 数据库查询延迟
    db_query_duration = meter.create_histogram(
        name="db_query_duration_seconds",
        description="Database query latency",
        unit="s"
    )

    logger.info("Common metrics created")


# 业务指标包装函数
def increment_http_requests(method: str, path: str, status_code: int):
    """增加 HTTP 请求计数"""
    if http_requests_total:
        http_requests_total.add(
            1,
            {
                "method": method,
                "path": path,
                "status_code": str(status_code)
            }
        )


def record_http_request_duration(duration: float, method: str, path: str):
    """记录 HTTP 请求延迟"""
    if http_request_duration:
        http_request_duration.record(
            duration,
            {
                "method": method,
                "path": path
            }
        )


def set_active_users(count: int):
    """设置活跃用户数"""
    if active_users:
        active_users.add(count - _get_current_value("active_users"), {})


def set_total_memories(count: int):
    """设置记忆总数"""
    if total_memories:
        total_memories.add(count - _get_current_value("memories"), {})


def increment_transactions(transaction_type: str, amount: float = 0):
    """增加交易计数"""
    if total_transactions:
        total_transactions.add(
            1,
            {
                "type": transaction_type,
                "amount": str(amount)
            }
        )


def record_search_latency(duration: float, search_type: str):
    """记录搜索延迟"""
    if search_latency:
        search_latency.record(
            duration,
            {
                "search_type": search_type
            }
        )


def record_qdrant_query(duration: float, operation: str):
    """记录 Qdrant 查询延迟"""
    if qdrant_query_duration:
        qdrant_query_duration.record(
            duration,
            {
                "operation": operation
            }
        )


def record_db_query(duration: float, operation: str):
    """记录数据库查询延迟"""
    if db_query_duration:
        db_query_duration.record(
            duration,
            {
                "operation": operation
            }
        )


# 辅助函数：获取当前指标值（简化版）
def _get_current_value(metric_name: str) -> int:
    """
    获取指标当前值（简化实现）
    实际应该从 meter provider 获取
    """
    # TODO: 实现真实的指标值获取逻辑
    return 0


def create_custom_counter(meter: metrics.Meter, name: str, description: str, unit: str = "1") -> Counter:
    """
    创建自定义计数器指标

    Args:
        meter: Meter 实例
        name: 指标名称
        description: 指标描述
        unit: 指标单位

    Returns:
        Counter 实例
    """
    return meter.create_counter(name=name, description=description, unit=unit)


def create_custom_histogram(meter: metrics.Meter, name: str, description: str, unit: str = "s") -> Histogram:
    """
    创建自定义直方图指标

    Args:
        meter: Meter 实例
        name: 指标名称
        description: 指标描述
        unit: 指标单位

    Returns:
        Histogram 实例
    """
    return meter.create_histogram(name=name, description=description, unit=unit)


def create_custom_gauge(meter: metrics.Meter, name: str, description: str, unit: str = "1") -> Gauge:
    """
    创建自定义仪表指标

    Args:
        meter: Meter 实例
        name: 指标名称
        description: 指标描述
        unit: 指标单位

    Returns:
        Gauge 实例
    """
    return meter.create_up_down_counter(name=name, description=description, unit=unit)


# 装饰器：自动记录指标
def timed_histogram(metric_name: str, **labels):
    """
    装饰器：自动记录函数执行时间到直方图

    Args:
        metric_name: 指标名称
        **labels: 指标标签
    """
    import time
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if search_latency:  # 使用已存在的 metric
                    search_latency.record(duration, labels)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if search_latency:
                    search_latency.record(duration, labels)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# 导入 asyncio 用于判断协程函数
import asyncio
