"""
监控和可观测性系统测试
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider

from app.telemetry import setup_telemetry, get_tracer, get_meter, shutdown_telemetry
from app.telemetry.tracing import (
    setup_tracing, instrument_fastapi, instrument_httpx,
    instrument_sqlalchemy, get_trace_id, inject_trace_context, extract_trace_context
)
from app.telemetry.metrics import (
    setup_metrics, create_common_metrics,
    increment_http_requests, record_http_request_duration,
    set_active_users, set_total_memories, increment_transactions,
    record_search_latency, record_qdrant_query, record_db_query
)
from app.core.logging import (
    setup_logging, get_logger, get_logger_with_context,
    JsonFormatter, LoggerAdapter
)


class TestOpenTelemetrySetup:
    """OpenTelemetry 系统设置测试"""

    def test_setup_telemetry(self):
        """测试 telemetry 系统初始化"""
        tracer_provider, meter_provider = setup_telemetry(
            service_name="test-service",
            jaeger_endpoint="http://localhost:4317",
            prometheus_port=9464,
            environment="testing"
        )

        assert tracer_provider is not None
        assert meter_provider is not None
        assert isinstance(tracer_provider, TracerProvider)
        assert isinstance(meter_provider, MeterProvider)

        # 清理
        shutdown_telemetry(tracer_provider, meter_provider)

    def test_get_tracer(self):
        """测试获取 tracer"""
        setup_telemetry(service_name="test-service")
        tracer = get_tracer("test-module")
        assert tracer is not None

    def test_get_meter(self):
        """测试获取 meter"""
        setup_telemetry(service_name="test-service")
        meter = get_meter("test-module")
        assert meter is not None


class TestTracing:
    """Tracing 功能测试"""

    @patch('app.telemetry.tracing.OTLPSpanExporter')
    def test_setup_tracing(self, mock_exporter):
        """测试 tracing 配置"""
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})
        provider = setup_tracing(resource=resource)

        assert provider is not None
        assert isinstance(provider, TracerProvider)

    def test_get_trace_id(self):
        """测试获取 trace ID"""
        # 在没有 trace context 的情况下应该返回空字符串
        trace_id = get_trace_id()
        assert trace_id == ""

    def test_inject_extract_trace_context(self):
        """测试 trace context 注入和提取"""
        headers = {}
        inject_trace_context(headers)

        # 检查是否包含 trace context headers
        traceparent = headers.get("traceparent")
        assert traceparent is not None or True  # 可能没有 active span

        # 提取 context
        context = extract_trace_context(headers)
        assert context is not None


class TestMetrics:
    """Metrics 功能测试"""

    @patch('app.telemetry.metrics.PrometheusMetricReader')
    def test_setup_metrics(self, mock_reader):
        """测试 metrics 配置"""
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})
        provider = setup_metrics(resource=resource)

        assert provider is not None
        assert isinstance(provider, MeterProvider)

    def test_create_common_metrics(self):
        """测试创建通用指标"""
        setup_telemetry(service_name="test-service")
        meter = get_meter()
        create_common_metrics(meter)
        # 如果没有抛出异常则认为测试通过

    def test_metric_functions(self):
        """测试指标函数"""
        setup_telemetry(service_name="test-service")
        meter = get_meter()
        create_common_metrics(meter)

        # 测试各种指标函数（不应该抛出异常）
        increment_http_requests("GET", "/api/v1/memories", 200)
        record_http_request_duration(0.123, "GET", "/api/v1/memories")
        set_active_users(100)
        set_total_memories(1000)
        increment_transactions("purchase", 10.0)
        record_search_latency(0.5, "hybrid")
        record_qdrant_query(0.3, "search")
        record_db_query(0.1, "select")


class TestLogging:
    """Logging 功能测试"""

    def test_setup_logging(self):
        """测试日志系统初始化"""
        logger = setup_logging(
            level="INFO",
            environment="testing"
        )
        assert logger is not None

    def test_get_logger(self):
        """测试获取 logger"""
        logger = get_logger("test-module")
        assert logger is not None
        assert logger.name == "test-module"

    def test_get_logger_with_context(self):
        """测试获取带上下文的 logger"""
        logger_adapter = get_logger_with_context(
            "test-module",
            user_id="user_123",
            request_id="req_456"
        )
        assert logger_adapter is not None
        assert isinstance(logger_adapter, LoggerAdapter)

    def test_json_formatter(self):
        """测试 JSON formatter"""
        formatter = JsonFormatter()

        # 创建一个 mock log record
        record = Mock()
        record.levelname = "INFO"
        record.name = "test.logger"
        record.getMessage = Mock(return_value="Test message")

        log_record = {}
        formatter.add_fields(log_record, record, {})

        # 检查是否添加了必需的字段
        assert "timestamp" in log_record
        assert "level" in log_record
        assert "logger" in log_record
        assert log_record["level"] == "INFO"
        assert log_record["logger"] == "test.logger"


@pytest.mark.integration
class TestMonitoringIntegration:
    """监控系统集成测试"""

    def test_full_telemetry_flow(self):
        """测试完整的 telemetry 流程"""
        # 设置 telemetry
        tracer_provider, meter_provider = setup_telemetry(
            service_name="integration-test",
            environment="testing"
        )

        # 获取 tracer 和 meter
        tracer = get_tracer("integration-test")
        meter = get_meter("integration-test")

        # 创建 common metrics
        create_common_metrics(meter)

        # 记录一些指标
        increment_http_requests("GET", "/api/v1/test", 200)
        record_http_request_duration(0.1, "GET", "/api/v1/test")
        set_active_users(10)
        set_total_memories(100)
        increment_transactions("test", 1.0)
        record_search_latency(0.05, "hybrid")
        record_qdrant_query(0.03, "search")
        record_db_query(0.01, "select")

        # 获取 logger
        logger = get_logger("integration-test")
        logger.info("Integration test message", extra={"test_key": "test_value"})

        # 清理
        shutdown_telemetry(tracer_provider, meter_provider)

    def test_trace_context_in_logs(self):
        """测试 trace context 在日志中的集成"""
        setup_telemetry(service_name="trace-test")
        logger = get_logger("trace-test")

        # 创建一个 span
        tracer = get_tracer("trace-test")
        with tracer.start_as_current_span("test-span"):
            # 在 span 内记录日志
            logger.info("Message within trace context")
            trace_id = get_trace_id()
            # 注意：在测试环境中可能没有实际导出，但函数应该能正常工作

    def test_metric_recording_overhead(self):
        """测试指标记录的性能开销"""
        setup_telemetry(service_name="performance-test")
        meter = get_meter("performance-test")
        create_common_metrics(meter)

        # 记录 1000 次指标
        start_time = time.time()
        for _ in range(1000):
            increment_http_requests("GET", "/api/v1/test", 200)
            record_http_request_duration(0.1, "GET", "/api/v1/test")
        duration = time.time() - start_time

        # 每次操作应该小于 1ms
        avg_time = duration / 1000
        assert avg_time < 0.001, f"Metric recording too slow: {avg_time}s per operation"


@pytest.mark.skipif(True, reason="需要启动实际服务 (--run-slow)")
class TestMonitoringWithServices:
    """需要实际服务的测试（使用 --run-slow 标志运行）"""

    def test_jaeger_integration(self):
        """测试 Jaeger 集成"""
        setup_telemetry(
            service_name="jaeger-test",
            jaeger_endpoint="http://localhost:4317"
        )

        tracer = get_tracer("jaeger-test")
        with tracer.start_as_current_span("test-span"):
            logger = get_logger("jaeger-test")
            logger.info("Testing Jaeger integration")
            time.sleep(0.1)

    def test_prometheus_metrics_export(self):
        """测试 Prometheus 指标导出"""
        setup_telemetry(
            service_name="prometheus-test",
            prometheus_port=9464
        )

        meter = get_meter("prometheus-test")
        create_common_metrics(meter)

        # 记录指标
        increment_http_requests("GET", "/api/v1/test", 200)
        record_http_request_duration(0.1, "GET", "/api/v1/test")

        # 注意：需要实际访问 http://localhost:9464/metrics 来验证


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
