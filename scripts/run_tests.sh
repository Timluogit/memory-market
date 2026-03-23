#!/bin/bash
# =============================================================================
# Agent Memory Market - 测试执行脚本
# 版本: v1.0
# 日期: 2026-03-23
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
PROJECT_DIR="/Users/sss/.openclaw/workspace/memory-market"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
REPORTS_DIR="$PROJECT_DIR/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 环境变量
export KEY_ENCRYPTION_SALT=73616c7431323334353637383930313233343536373839303132333435363738

# =============================================================================
# 函数定义
# =============================================================================

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Agent Memory Market - 测试执行脚本${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_section() {
    echo -e "${YELLOW}▶ $1${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

check_dependencies() {
    print_section "检查依赖"
    
    # 检查Python
    if [ ! -f "$PYTHON" ]; then
        print_error "Python虚拟环境未找到: $PYTHON"
        exit 1
    fi
    print_success "Python环境: $($PYTHON --version)"
    
    # 检查pytest
    if ! $PYTHON -m pytest --version &> /dev/null; then
        print_error "pytest未安装"
        exit 1
    fi
    print_success "pytest已安装"
    
    # 检查Redis (可选)
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping &> /dev/null; then
            print_success "Redis服务已启动"
        else
            print_warning "Redis服务未启动，部分测试可能失败"
        fi
    else
        print_warning "Redis未安装，部分测试可能失败"
    fi
    
    echo ""
}

run_unit_tests() {
    print_section "阶段1: 单元测试"
    
    cd "$PROJECT_DIR"
    
    $PYTHON -m pytest tests/ \
        -v \
        --tb=short \
        -x \
        -m "not integration" \
        --junitxml="$REPORTS_DIR/unit_tests_$TIMESTAMP.xml" \
        2>&1 | tee "$REPORTS_DIR/unit_tests_$TIMESTAMP.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "单元测试通过"
    else
        print_error "单元测试失败"
        return 1
    fi
    
    echo ""
}

run_integration_tests() {
    print_section "阶段2: 集成测试"
    
    cd "$PROJECT_DIR"
    
    $PYTHON -m pytest tests/ \
        -v \
        --tb=short \
        -k "integration" \
        --junitxml="$REPORTS_DIR/integration_tests_$TIMESTAMP.xml" \
        2>&1 | tee "$REPORTS_DIR/integration_tests_$TIMESTAMP.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "集成测试通过"
    else
        print_error "集成测试失败"
        return 1
    fi
    
    echo ""
}

run_performance_tests() {
    print_section "阶段3: 性能测试"
    
    cd "$PROJECT_DIR"
    
    # 运行性能测试脚本
    if [ -f "scripts/performance_test.py" ]; then
        $PYTHON scripts/performance_test.py \
            2>&1 | tee "$REPORTS_DIR/performance_tests_$TIMESTAMP.log"
        print_success "性能测试完成"
    else
        print_warning "性能测试脚本不存在"
    fi
    
    # 运行已有性能测试
    if [ -f "tests/performance_team.py" ]; then
        $PYTHON -m pytest tests/performance_team.py \
            -v \
            --tb=short \
            --junitxml="$REPORTS_DIR/performance_team_$TIMESTAMP.xml" \
            2>&1 | tee -a "$REPORTS_DIR/performance_tests_$TIMESTAMP.log"
    fi
    
    echo ""
}

run_e2e_tests() {
    print_section "阶段4: 端到端测试"
    
    cd "$PROJECT_DIR"
    
    if [ -f "tests/e2e_team_collab.py" ]; then
        $PYTHON -m pytest tests/e2e_team_collab.py \
            -v \
            --tb=short \
            --junitxml="$REPORTS_DIR/e2e_tests_$TIMESTAMP.xml" \
            2>&1 | tee "$REPORTS_DIR/e2e_tests_$TIMESTAMP.log"
        
        if [ ${PIPESTATUS[0]} -eq 0 ]; then
            print_success "端到端测试通过"
        else
            print_error "端到端测试失败"
            return 1
        fi
    else
        print_warning "端到端测试文件不存在"
    fi
    
    echo ""
}

run_coverage() {
    print_section "生成代码覆盖率报告"
    
    cd "$PROJECT_DIR"
    
    $PYTHON -m pytest tests/ \
        --cov=app \
        --cov-report=html:"$REPORTS_DIR/coverage_html_$TIMESTAMP" \
        --cov-report=xml:"$REPORTS_DIR/coverage_$TIMESTAMP.xml" \
        --cov-report=term \
        2>&1 | tee "$REPORTS_DIR/coverage_$TIMESTAMP.log"
    
    print_success "覆盖率报告已生成"
    echo "HTML报告: $REPORTS_DIR/coverage_html_$TIMESTAMP/index.html"
    
    echo ""
}

run_specific_module() {
    local module=$1
    print_section "运行特定模块测试: $module"
    
    cd "$PROJECT_DIR"
    
    $PYTHON -m pytest "tests/test_$module.py" \
        -v \
        --tb=short \
        2>&1 | tee "$REPORTS_DIR/module_${module}_$TIMESTAMP.log"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "模块 $module 测试通过"
    else
        print_error "模块 $module 测试失败"
        return 1
    fi
    
    echo ""
}

generate_summary() {
    print_section "生成测试摘要"
    
    cd "$PROJECT_DIR"
    
    # 统计测试结果
    total_tests=$(grep -c "PASSED\|FAILED\|ERROR" "$REPORTS_DIR/unit_tests_$TIMESTAMP.log" 2>/dev/null || echo "0")
    passed_tests=$(grep -c "PASSED" "$REPORTS_DIR/unit_tests_$TIMESTAMP.log" 2>/dev/null || echo "0")
    failed_tests=$(grep -c "FAILED" "$REPORTS_DIR/unit_tests_$TIMESTAMP.log" 2>/dev/null || echo "0")
    error_tests=$(grep -c "ERROR" "$REPORTS_DIR/unit_tests_$TIMESTAMP.log" 2>/dev/null || echo "0")
    
    # 生成摘要文件
    cat > "$REPORTS_DIR/summary_$TIMESTAMP.md" << EOF
# 测试执行摘要

## 执行时间
- 开始时间: $TIMESTAMP
- 执行环境: $(uname -s) $(uname -m)
- Python版本: $($PYTHON --version)

## 测试结果
- 总测试数: $total_tests
- 通过数: $passed_tests
- 失败数: $failed_tests
- 错误数: $error_tests
- 通过率: $(echo "scale=2; $passed_tests * 100 / $total_tests" | bc 2>/dev/null || echo "N/A")%

## 报告文件
- 单元测试: unit_tests_$TIMESTAMP.log
- 集成测试: integration_tests_$TIMESTAMP.log
- 性能测试: performance_tests_$TIMESTAMP.log
- E2E测试: e2e_tests_$TIMESTAMP.log
- 覆盖率: coverage_$TIMESTAMP.log
- HTML报告: coverage_html_$TIMESTAMP/index.html

## 下一步
1. 查看失败测试详情
2. 分析错误原因
3. 修复问题
4. 重新运行测试
EOF
    
    print_success "测试摘要已生成: $REPORTS_DIR/summary_$TIMESTAMP.md"
    
    echo ""
}

# =============================================================================
# 主菜单
# =============================================================================

show_menu() {
    echo -e "${BLUE}请选择操作:${NC}"
    echo "1. 运行所有测试"
    echo "2. 运行单元测试"
    echo "3. 运行集成测试"
    echo "4. 运行性能测试"
    echo "5. 运行E2E测试"
    echo "6. 运行特定模块测试"
    echo "7. 生成覆盖率报告"
    echo "8. 生成测试摘要"
    echo "9. 退出"
    echo ""
    read -p "请输入选择 (1-9): " choice
    echo ""
}

# =============================================================================
# 主程序
# =============================================================================

main() {
    print_header
    
    # 创建报告目录
    mkdir -p "$REPORTS_DIR"
    
    # 检查依赖
    check_dependencies
    
    # 显示菜单
    show_menu
    
    case $choice in
        1)
            run_unit_tests
            run_integration_tests
            run_performance_tests
            run_e2e_tests
            run_coverage
            generate_summary
            ;;
        2)
            run_unit_tests
            ;;
        3)
            run_integration_tests
            ;;
        4)
            run_performance_tests
            ;;
        5)
            run_e2e_tests
            ;;
        6)
            read -p "请输入模块名称 (例如: api, services, team_models): " module
            run_specific_module "$module"
            ;;
        7)
            run_coverage
            ;;
        8)
            generate_summary
            ;;
        9)
            echo "退出"
            exit 0
            ;;
        *)
            print_error "无效选择"
            exit 1
            ;;
    esac
    
    print_success "测试执行完成"
}

# 运行主程序
main
