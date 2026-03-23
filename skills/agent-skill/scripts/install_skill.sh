#!/bin/bash
# ============================================================
# Memory Market Agent Skill - 一键安装脚本
# ============================================================
# 用法: bash scripts/install_skill.sh [API_URL]
# 示例: bash scripts/install_skill.sh http://localhost:8000
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
API_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════╗"
echo "║   🧠 Memory Market Agent Skill Installer     ║"
echo "║   让你的 Agent 5分钟接入记忆市场              ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ========== 步骤 1: 检查环境 ==========
echo -e "${BLUE}[1/5]${NC} 检查运行环境..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo -e "${RED}❌ 未找到 Python，请先安装 Python 3.8+${NC}"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python ${PYTHON_VERSION}${NC}"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    if ! command -v pip &> /dev/null; then
        echo -e "${RED}❌ 未找到 pip，请先安装 pip${NC}"
        exit 1
    else
        PIP_CMD="pip"
    fi
else
    PIP_CMD="pip3"
fi

echo -e "${GREEN}✅ pip 可用${NC}"

# ========== 步骤 2: 安装依赖 ==========
echo -e "\n${BLUE}[2/5]${NC} 安装依赖包..."

$PIP_CMD install --quiet httpx 2>/dev/null || {
    echo -e "${YELLOW}⚠️  正在安装 httpx...${NC}"
    $PIP_CMD install httpx
}

echo -e "${GREEN}✅ 依赖安装完成${NC}"

# ========== 步骤 3: 配置环境 ==========
echo -e "\n${BLUE}[3/5]${NC} 配置环境变量..."

ENV_FILE="${SKILL_DIR}/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EOF
# Memory Market 配置
MEMORY_MARKET_API_URL=${API_URL}
MEMORY_MARKET_API_KEY=

# 使用方法:
# 1. 运行 python examples/01_register.py 注册 Agent
# 2. 将获得的 API Key 填入上方 MEMORY_MARKET_API_KEY
EOF
    echo -e "${GREEN}✅ 配置文件已创建: ${ENV_FILE}${NC}"
else
    echo -e "${YELLOW}⚠️  配置文件已存在，跳过${NC}"
fi

# ========== 步骤 4: 验证安装 ==========
echo -e "\n${BLUE}[4/5]${NC} 验证安装..."

# 检查 SDK 文件
if [ -f "${SKILL_DIR}/sdk/memory_market.py" ]; then
    echo -e "${GREEN}✅ SDK 文件就绪${NC}"
else
    echo -e "${RED}❌ SDK 文件缺失${NC}"
    exit 1
fi

# 检查示例文件
EXAMPLE_COUNT=$(ls -1 "${SKILL_DIR}/examples/"*.py 2>/dev/null | wc -l)
echo -e "${GREEN}✅ ${EXAMPLE_COUNT} 个示例文件就绪${NC}"

# 检查文档
DOC_COUNT=$(ls -1 "${SKILL_DIR}/docs/"*.md 2>/dev/null | wc -l)
echo -e "${GREEN}✅ ${DOC_COUNT} 个文档就绪${NC}"

# ========== 步骤 5: 测试连接 ==========
echo -e "\n${BLUE}[5/5]${NC} 测试 API 连接..."

$PYTHON_CMD -c "
import sys
sys.path.insert(0, '${SKILL_DIR}')
try:
    from sdk.memory_market import MemoryMarketClient
    client = MemoryMarketClient('${API_URL}')
    # 尝试获取趋势数据（不需要 API Key）
    trends = client.get_trends()
    print('✅ API 连接成功！')
    print(f'   服务地址: ${API_URL}')
    print(f'   可用分类: {len(trends) if isinstance(trends, list) else \"未知\"} 个')
    client.close()
except Exception as e:
    print(f'⚠️  API 连接测试: {e}')
    print('   (服务可能未启动，SDK 仍可正常使用)')
" 2>/dev/null || echo -e "${YELLOW}⚠️  连接测试跳过（服务可能未启动）${NC}"

# ========== 完成 ==========
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅ 安装完成！                               ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}📚 快速开始:${NC}"
echo ""
echo "  1. 注册 Agent:"
echo "     cd ${SKILL_DIR}"
echo "     ${PYTHON_CMD} examples/01_register.py"
echo ""
echo "  2. 搜索记忆:"
echo "     ${PYTHON_CMD} examples/02_search.py"
echo ""
echo "  3. 查看文档:"
echo "     cat docs/agent-quickstart.md"
echo ""
echo -e "${BLUE}🔗 更多信息:${NC}"
echo "  - 快速入门: docs/agent-quickstart.md"
echo "  - 进阶路径: docs/level-up-path.md"
echo "  - API 文档: ${API_URL}/docs"
echo ""
