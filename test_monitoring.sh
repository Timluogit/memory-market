#!/bin/bash

# Memory Market 监控系统测试脚本

set -e

echo "========================================="
echo "Memory Market Monitoring Test Suite"
echo "========================================="
echo ""

# 检查是否在正确的目录
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this script from the memory-market directory"
    exit 1
fi

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 函数：打印成功消息
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 函数：打印警告消息
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 函数：打印错误消息
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 1. 检查 Python 版本
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python version: $PYTHON_VERSION"

# 2. 检查依赖
echo ""
echo "2. Checking dependencies..."
python3 -c "import opentelemetry; print_success 'OpenTelemetry installed'"
python3 -c "import prometheus_client; print_success 'Prometheus client installed'"
python3 -c "import structlog; print_success 'Structlog installed'"

# 3. 运行单元测试
echo ""
echo "3. Running unit tests..."
if python3 -m pytest tests/test_monitoring.py -v --tb=short; then
    print_success "Unit tests passed"
else
    print_error "Unit tests failed"
    exit 1
fi

# 4. 检查监控栈服务状态
echo ""
echo "4. Checking monitoring stack services..."

check_service() {
    local service_name=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        print_success "$service_name is running"
        return 0
    else
        print_warning "$service_name is not running (start with: docker-compose -f docker-compose.monitoring.yml up -d)"
        return 1
    fi
}

check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"
check_service "Jaeger" "http://localhost:16686/api/health"
check_service "Alertmanager" "http://localhost:9093/-/healthy"

# 5. 测试指标端点
echo ""
echo "5. Testing metrics endpoint..."
if curl -s http://localhost:9464/metrics > /dev/null 2>&1; then
    print_success "Prometheus metrics endpoint is accessible"
    echo "   Metrics available at: http://localhost:9464/metrics"
else
    print_warning "Prometheus metrics endpoint not accessible (is the app running?)"
fi

# 6. 性能开销测试
echo ""
echo "6. Running performance overhead test..."
if python3 -m pytest tests/test_monitoring.py::TestMonitoringIntegration::test_metric_recording_overhead -v -s; then
    print_success "Performance overhead test passed"
else
    print_warning "Performance overhead test failed"
fi

# 7. 总结
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo ""
echo "✓ Unit tests passed"
echo "✓ Dependencies installed"
echo ""

if check_service "Prometheus" "http://localhost:9090/-/healthy" 2>/dev/null; then
    echo "✓ Monitoring stack is running"
    echo ""
    echo "Access URLs:"
    echo "  - Grafana:    http://localhost:3000 (admin/admin123)"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Jaeger:     http://localhost:16686"
    echo "  - Alertmanager: http://localhost:9093"
else
    echo "⚠ Monitoring stack is not running"
    echo ""
    echo "Start monitoring stack with:"
    echo "  docker-compose -f docker-compose.monitoring.yml up -d"
fi

echo ""
echo "Next steps:"
echo "  1. Start the application: python -m uvicorn app.main_monitoring:app --reload"
echo "  2. Make some API calls to generate telemetry data"
echo "  3. View traces in Jaeger"
echo "  4. View metrics in Grafana"
echo ""
