#!/bin/bash

#############################################
# ClawHub 技能发布脚本
# 用于将 Memory Market 技能发布到 ClawHub 市场
#############################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_NAME="memory-market"
BUILD_DIR="${SCRIPT_DIR}/dist"
CLAWHUB_API="${CLAWHUB_API:-https://api.clawhub.dev}"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印标题
print_title() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装，请先安装 $1"
        exit 1
    fi
}

# 清理构建目录
clean_build() {
    print_info "清理构建目录..."
    rm -rf "${BUILD_DIR}"
    mkdir -p "${BUILD_DIR}"
}

# 验证文件结构
validate_structure() {
    print_info "验证文件结构..."

    required_files=(
        "SKILL.md"
        "clawhub.json"
        "README.md"
        "app/__init__.py"
        "app/main.py"
        "app/mcp/server.py"
    )

    for file in "${required_files[@]}"; do
        if [ ! -f "${SCRIPT_DIR}/${file}" ]; then
            print_error "缺少必需文件: ${file}"
            exit 1
        fi
    done

    print_success "文件结构验证通过"
}

# 验证 JSON 格式
validate_json() {
    print_info "验证 JSON 格式..."

    if ! python3 -m json.tool "${SCRIPT_DIR}/clawhub.json" > /dev/null 2>&1; then
        print_error "clawhub.json 格式错误"
        exit 1
    fi

    print_success "JSON 格式验证通过"
}

# 构建发布包
build_package() {
    print_title "开始构建发布包"

    # 创建临时目录
    TEMP_DIR="${BUILD_DIR}/${PACKAGE_NAME}"
    mkdir -p "${TEMP_DIR}"

    # 复制核心文件
    print_info "复制核心文件..."

    # 应用代码
    mkdir -p "${TEMP_DIR}/app"
    cp -r "${SCRIPT_DIR}/app/"* "${TEMP_DIR}/app/" 2>/dev/null || true

    # 技能配置
    mkdir -p "${TEMP_DIR}/skills/${PACKAGE_NAME}"
    cp "${SCRIPT_DIR}/skills/${PACKAGE_NAME}/SKILL.md" "${TEMP_DIR}/skills/${PACKAGE_NAME}/"

    # 配置文件
    cp "${SCRIPT_DIR}/clawhub.json" "${TEMP_DIR}/"
    cp "${SCRIPT_DIR}/README.md" "${TEMP_DIR}/"
    cp "${SCRIPT_DIR}/requirements.txt" "${TEMP_DIR}/"
    cp "${SCRIPT_DIR}/pyproject.toml" "${TEMP_DIR}/" 2>/dev/null || true

    # Docker 文件
    cp "${SCRIPT_DIR}/Dockerfile" "${TEMP_DIR}/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/docker-compose.yml" "${TEMP_DIR}/" 2>/dev/null || true

    # 脚本
    mkdir -p "${TEMP_DIR}/scripts"
    cp "${SCRIPT_DIR}/scripts/"*.sh "${TEMP_DIR}/scripts/" 2>/dev/null || true

    # 文档
    mkdir -p "${TEMP_DIR}/docs"
    cp "${SCRIPT_DIR}/docs/"* "${TEMP_DIR}/docs/" 2>/dev/null || true

    # 静态文件
    if [ -d "${SCRIPT_DIR}/app/static" ]; then
        mkdir -p "${TEMP_DIR}/app/static"
        cp -r "${SCRIPT_DIR}/app/static/"* "${TEMP_DIR}/app/static/"
    fi

    # 创建版本文件
    VERSION=$(python3 -c "import json; print(json.load(open('${SCRIPT_DIR}/clawhub.json'))['version'])")
    echo "${VERSION}" > "${TEMP_DIR}/VERSION"

    print_success "文件复制完成"
}

# 创建归档文件
create_archive() {
    print_info "创建发布归档..."

    cd "${BUILD_DIR}"
    tar -czf "${PACKAGE_NAME}-${VERSION}.tar.gz" "${PACKAGE_NAME}"
    cd "${SCRIPT_DIR}"

    print_success "归档创建完成: ${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
}

# 计算校验和
calculate_checksum() {
    print_info "计算文件校验和..."

    cd "${BUILD_DIR}"
    if command -v sha256sum &> /dev/null; then
        sha256sum "${PACKAGE_NAME}-${VERSION}.tar.gz" > "${PACKAGE_NAME}-${VERSION}.tar.gz.sha256"
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "${PACKAGE_NAME}-${VERSION}.tar.gz" > "${PACKAGE_NAME}-${VERSION}.tar.gz.sha256"
    else
        print_warning "无法计算 SHA256 校验和"
    fi
    cd "${SCRIPT_DIR}"

    print_success "校验和计算完成"
}

# 上传到 ClawHub
upload_to_clawhub() {
    print_title "上传到 ClawHub"

    # 检查是否已登录
    if [ -z "${CLAWHUB_TOKEN}" ]; then
        print_error "未设置 CLAWHUB_TOKEN 环境变量"
        print_info "请先登录: clawhub login"
        exit 1
    fi

    print_info "上传发布包..."

    # 获取归档文件路径
    ARCHIVE_PATH="${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"

    # 上传
    response=$(curl -s -X POST \
        -H "Authorization: Bearer ${CLAWHUB_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"package\":\"${PACKAGE_NAME}\",\"version\":\"${VERSION}\",\"file\":\"$(base64 < "${ARCHIVE_PATH}")\"}" \
        "${CLAWHUB_API}/v1/packages/publish")

    # 检查响应
    if echo "${response}" | grep -q '"success":true'; then
        print_success "上传成功！"

        # 获取包 URL
        package_url=$(echo "${response}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('url', ''))" 2>/dev/null)
        if [ -n "${package_url}" ]; then
            print_info "包地址: ${package_url}"
        fi
    else
        print_error "上传失败"
        echo "${response}"
        exit 1
    fi
}

# 生成本地发布包（用于测试）
build_local() {
    print_title "构建本地发布包"

    clean_build
    validate_structure
    validate_json
    build_package
    create_archive
    calculate_checksum

    print_success "本地发布包构建完成！"
    print_info "发布包路径: ${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"

    # 显示包信息
    echo ""
    echo "📦 包信息:"
    echo "  名称: ${PACKAGE_NAME}"
    echo "  版本: ${VERSION}"
    echo "  大小: $(du -h "${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz" | cut -f1)"
    echo "  路径: ${BUILD_DIR}/${PACKAGE_NAME}-${VERSION}.tar.gz"
    echo ""
}

# 发布到 ClawHub
publish() {
    print_title "发布到 ClawHub"

    # 先构建本地包
    build_local

    # 询问是否继续上传
    if [ "${SKIP_CONFIRM}" != "true" ]; then
        read -p "是否上传到 ClawHub？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "已取消上传"
            exit 0
        fi
    fi

    # 上传
    upload_to_clawhub

    print_success "发布完成！"
}

# 显示帮助信息
show_help() {
    cat << EOF
ClawHub 技能发布脚本

用法:
    $0 [命令] [选项]

命令:
    build       构建本地发布包（不上传）
    publish     构建并发布到 ClawHub
    validate    验证文件结构和配置
    clean       清理构建目录
    help        显示此帮助信息

选项:
    --skip-confirm  跳过确认提示
    --api-url       指定 ClawHub API 地址（默认: https://api.clawhub.dev）

环境变量:
    CLAWHUB_TOKEN   ClawHub 认证令牌（发布时必需）
    CLAWHUB_API     ClawHub API 地址

示例:
    # 构建本地发布包
    $0 build

    # 发布到 ClawHub
    $0 publish

    # 跳过确认直接发布
    SKIP_CONFIRM=true $0 publish

    # 使用自定义 API 地址
    $0 publish --api-url https://staging.clawhub.dev

EOF
}

# 主函数
main() {
    print_title "ClawHub 技能发布工具"

    # 检查必需命令
    check_command python3
    check_command curl
    check_command tar

    # 解析参数
    COMMAND="${1:-help}"
    shift || true

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-confirm)
                SKIP_CONFIRM=true
                shift
                ;;
            --api-url)
                CLAWHUB_API="$2"
                shift 2
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 执行命令
    case "${COMMAND}" in
        build)
            build_local
            ;;
        publish)
            publish
            ;;
        validate)
            validate_structure
            validate_json
            print_success "验证通过"
            ;;
        clean)
            clean_build
            print_success "清理完成"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: ${COMMAND}"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
