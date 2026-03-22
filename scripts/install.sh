#!/bin/bash
#
# Memory Market 一键安装脚本 | Memory Market One-Click Install Script
# 支持 macOS 和 Linux | Supports macOS and Linux
#
# 使用方法 | Usage:
#   curl -fsSL https://raw.githubusercontent.com/Timluogit/memory-market/main/scripts/install.sh | bash
#
# 或者下载后执行 | Or download and run:
#   chmod +x install.sh
#   ./install.sh
#

set -e  # 遇到错误立即退出 | Exit on error

# 颜色定义 | Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数 | Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印带颜色的标题 | Print colored header
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  🧠 Memory Market 安装程序${NC}"
    echo -e "${BLUE}  Agent Memory Market Installer${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检测操作系统 | Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
    else
        log_error "不支持的操作系统: $OSTYPE | Unsupported OS: $OSTYPE"
        exit 1
    fi
    log_info "检测到操作系统 | Detected OS: $OS"
}

# 检查 Python 版本 | Check Python version
check_python() {
    log_info "检查 Python 版本 | Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        log_error "未找到 Python 3，请先安装 Python 3.11 或更高版本"
        log_error "Python 3 not found. Please install Python 3.11 or higher first"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    log_info "当前 Python 版本 | Current Python version: $PYTHON_VERSION"

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
        log_error "需要 Python 3.11 或更高版本 | Python 3.11 or higher required"
        log_error "当前版本 | Current version: $PYTHON_VERSION"
        exit 1
    fi

    log_success "Python 版本符合要求 | Python version OK"
}

# 检查 pip | Check pip
check_pip() {
    log_info "检查 pip | Checking pip..."

    if ! command -v pip3 &> /dev/null; then
        log_error "未找到 pip3 | pip3 not found"
        log_info "尝试安装 pip | Attempting to install pip..."

        if [[ "$OS" == "macOS" ]]; then
            python3 -m ensurepip --upgrade
        else
            sudo apt-get install python3-pip -y
        fi
    fi

    log_success "pip 已就绪 | pip is ready"
}

# 检查 Git | Check Git
check_git() {
    log_info "检查 Git | Checking Git..."

    if ! command -v git &> /dev/null; then
        log_error "未找到 Git | Git not found"
        log_info "请安装 Git | Please install Git:"

        if [[ "$OS" == "macOS" ]]; then
            echo "  brew install git"
        else
            echo "  sudo apt-get install git"
        fi

        exit 1
    fi

    log_success "Git 已就绪 | Git is ready"
}

# 设置安装目录 | Set installation directory
setup_install_dir() {
    log_info "设置安装目录 | Setting up installation directory..."

    # 默认安装目录 | Default installation directory
    INSTALL_DIR="$HOME/.memory-market"

    # 如果环境变量设置了安装目录，使用环境变量
    # Use env var if set
    if [ -n "$MEMORY_MARKET_DIR" ]; then
        INSTALL_DIR="$MEMORY_MARKET_DIR"
    fi

    log_info "安装目录 | Installation directory: $INSTALL_DIR"

    # 创建目录 | Create directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    log_success "安装目录已创建 | Installation directory created"
}

# 克隆仓库 | Clone repository
clone_repo() {
    log_info "克隆仓库 | Cloning repository..."

    if [ -d "memory-market" ]; then
        log_warning "目录已存在，正在更新 | Directory exists, updating..."
        cd memory-market
        git pull origin main
    else
        git clone https://github.com/Timluogit/memory-market.git
        cd memory-market
    fi

    log_success "仓库已准备就绪 | Repository ready"
}

# 创建虚拟环境 | Create virtual environment
create_venv() {
    log_info "创建虚拟环境 | Creating virtual environment..."

    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "虚拟环境已创建 | Virtual environment created"
    else
        log_info "虚拟环境已存在 | Virtual environment already exists"
    fi

    # 激活虚拟环境 | Activate virtual environment
    source venv/bin/activate

    # 升级 pip | Upgrade pip
    pip install --upgrade pip -q

    log_success "虚拟环境已激活 | Virtual environment activated"
}

# 安装依赖 | Install dependencies
install_dependencies() {
    log_info "安装依赖 | Installing dependencies..."
    log_info "这可能需要几分钟 | This may take a few minutes..."

    # 安装核心依赖 | Install core dependencies
    pip install -r requirements.txt -q

    # 安装 SDK/CLI（开发模式）| Install SDK/CLI (editable mode)
    pip install -e . -q

    log_success "依赖安装完成 | Dependencies installed"
}

# 初始化数据库 | Initialize database
init_database() {
    log_info "初始化数据库 | Initializing database..."

    # 创建数据目录 | Create data directory
    mkdir -p data

    # 初始化数据库（如果脚本存在）
    # Initialize database (if script exists)
    if [ -f "app/db/database.py" ]; then
        python -c "from app.db.database import init_db; import asyncio; asyncio.run(init_db())" 2>/dev/null || true
    fi

    log_success "数据库已初始化 | Database initialized"
}

# 导入种子数据（可选）| Import seed data (optional)
import_seed_data() {
    if [ "$SKIP_SEED_DATA" = "true" ]; then
        log_info "跳过种子数据导入 | Skipping seed data import"
        return
    fi

    log_info "是否导入种子数据？| Import seed data?"
    read -p "导入示例记忆数据？| Import sample memory data? [y/N] " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "导入种子数据 | Importing seed data..."

        python scripts/seed_all_categories.py 2>/dev/null || true
        python scripts/seed_more_memories.py 2>/dev/null || true

        log_success "种子数据导入完成 | Seed data imported"
    fi
}

# 创建配置文件 | Create config file
create_config() {
    log_info "创建配置文件 | Creating configuration..."

    CONFIG_DIR="$HOME/.config/memory-market"
    mkdir -p "$CONFIG_DIR"

    CONFIG_FILE="$CONFIG_DIR/config.json"

    if [ ! -f "$CONFIG_FILE" ]; then
        cat > "$CONFIG_FILE" << EOF
{
  "base_url": "http://localhost:8000",
  "api_key": "",
  "log_level": "INFO"
}
EOF
        log_success "配置文件已创建 | Configuration created: $CONFIG_FILE"
    else
        log_info "配置文件已存在 | Configuration already exists: $CONFIG_FILE"
    fi
}

# 创建启动脚本 | Create start script
create_start_script() {
    log_info "创建启动脚本 | Creating start script..."

    cat > "$INSTALL_DIR/memory-market/start.sh" << 'EOF'
#!/bin/bash
# Memory Market 启动脚本

cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 启动服务
python -m app.main
EOF

    chmod +x "$INSTALL_DIR/memory-market/start.sh"

    log_success "启动脚本已创建 | Start script created"
}

# 创建 CLI 快捷命令（可选）| Create CLI shortcut (optional)
create_cli_alias() {
    log_info "创建 CLI 快捷命令 | Creating CLI shortcut..."

    # 检查 shell 类型 | Check shell type
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    # 添加 alias | Add alias
    ALIAS_LINE="alias memory-market='$INSTALL_DIR/memory-market/venv/bin/python -m memory_market.cli'"

    if ! grep -q "memory-market" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Memory Market CLI" >> "$SHELL_RC"
        echo "$ALIAS_LINE" >> "$SHELL_RC"

        log_success "CLI 快捷命令已添加到 | CLI shortcut added to: $SHELL_RC"
        log_info "请运行以下命令使配置生效 | Please run to apply changes:"
        echo "  source $SHELL_RC"
    else
        log_info "CLI 快捷命令已存在 | CLI shortcut already exists"
    fi
}

# 打印安装摘要 | Print installation summary
print_summary() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✅ 安装完成！| Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}📁 安装目录 | Installation Directory:${NC}"
    echo "   $INSTALL_DIR/memory-market"
    echo ""
    echo -e "${BLUE}🔧 快速启动 | Quick Start:${NC}"
    echo ""
    echo "   1. 启动服务器 | Start server:"
    echo "      cd $INSTALL_DIR/memory-market"
    echo "      ./start.sh"
    echo ""
    echo "   2. 访问 Web UI | Access Web UI:"
    echo "      http://localhost:8000"
    echo ""
    echo "   3. 访问 API 文档 | Access API Docs:"
    echo "      http://localhost:8000/docs"
    echo ""
    echo -e "${BLUE}💻 使用 CLI | Use CLI:${NC}"
    echo "   memory-market search \"爆款\""
    echo "   memory-market balance"
    echo ""
    echo -e "${BLUE}🐳 使用 Docker | Use Docker:${NC}"
    echo "   cd $INSTALL_DIR/memory-market"
    echo "   docker-compose up -d"
    echo ""
    echo -e "${BLUE}📚 查看文档 | Documentation:${NC}"
    echo "   cat $INSTALL_DIR/memory-market/README.md"
    echo ""
    echo -e "${BLUE}❓ 获取帮助 | Get Help:${NC}"
    echo "   memory-market --help"
    echo ""
    echo -e "${GREEN}感谢使用 Memory Market! | Thanks for using Memory Market!${NC}"
    echo ""
}

# 主函数 | Main function
main() {
    print_header

    # 检查环境 | Check environment
    detect_os
    check_python
    check_pip
    check_git

    # 安装 | Install
    setup_install_dir
    clone_repo
    create_venv
    install_dependencies
    init_database
    import_seed_data
    create_config
    create_start_script
    create_cli_alias

    # 完成 | Complete
    print_summary
}

# 运行主函数 | Run main
main
