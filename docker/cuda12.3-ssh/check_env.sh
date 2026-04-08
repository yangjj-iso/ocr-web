#!/usr/bin/env bash
# ============================================
# 容器环境诊断脚本
# SSH 进入容器后执行: bash check_env.sh
# ============================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }
info() { echo -e "  ${YELLOW}→${NC} $*"; }

echo ""
echo "============================================"
echo "  CUDA 12.3 容器环境诊断"
echo "============================================"
echo ""

# 1. 操作系统
echo "[1] 操作系统"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    ok "$PRETTY_NAME"
else
    fail "无法识别操作系统"
fi

# 2. GPU / CUDA
echo "[2] GPU / CUDA"
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1)
    DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
    ok "nvidia-smi 可用"
    info "GPU: $GPU_NAME ($GPU_MEM)"
    info "驱动版本: $DRIVER"
else
    fail "nvidia-smi 不可用（容器可能未以 --gpus all 启动）"
fi

if command -v nvcc &>/dev/null; then
    ok "nvcc: $(nvcc --version 2>&1 | grep 'release' | awk '{print $NF}')"
else
    # 查找 nvcc
    FOUND=""
    for p in /usr/local/cuda/bin/nvcc /usr/local/cuda-12.3/bin/nvcc /usr/local/cuda-12/bin/nvcc; do
        if [ -f "$p" ]; then
            FOUND="$p"
            break
        fi
    done
    if [ -n "$FOUND" ]; then
        info "nvcc 存在但不在 PATH 中: $FOUND"
        info "版本: $($FOUND --version 2>&1 | grep 'release' | awk '{print $NF}')"
    else
        fail "nvcc 未找到"
    fi
fi

# 3. Python
echo "[3] Python"
if command -v python3 &>/dev/null; then
    ok "python3: $(python3 --version 2>&1)"
elif command -v python &>/dev/null; then
    ok "python: $(python --version 2>&1)"
else
    fail "Python 未安装"
fi

if command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
    PIP_CMD=$(command -v pip3 || command -v pip)
    ok "pip: $($PIP_CMD --version 2>&1 | awk '{print $2}')"
else
    fail "pip 未安装"
fi

# 4. Node.js
echo "[4] Node.js"
if command -v node &>/dev/null; then
    ok "node: $(node --version)"
    ok "npm: $(npm --version 2>/dev/null || echo '未安装')"
else
    fail "Node.js 未安装（构建前端需要）"
fi

# 5. PostgreSQL
echo "[5] PostgreSQL"
if command -v psql &>/dev/null; then
    ok "psql: $(psql --version 2>&1 | awk '{print $NF}')"
else
    fail "PostgreSQL 未安装"
fi

# 6. Redis
echo "[6] Redis"
if command -v redis-server &>/dev/null; then
    ok "redis-server: $(redis-server --version 2>&1 | awk '{print $3}')"
else
    fail "Redis 未安装"
fi

# 7. 磁盘空间
echo "[7] 磁盘空间"
AVAIL=$(df -h / | awk 'NR==2 {print $4}')
TOTAL=$(df -h / | awk 'NR==2 {print $2}')
USED_PCT=$(df -h / | awk 'NR==2 {print $5}')
info "总计: $TOTAL, 可用: $AVAIL, 已用: $USED_PCT"
# 需要约 15-20GB（依赖+模型+系统）
AVAIL_GB=$(df --output=avail / | awk 'NR==2 {printf "%.0f", $1/1024/1024}')
if [ "$AVAIL_GB" -ge 20 ]; then
    ok "磁盘空间充足 (≥20GB)"
elif [ "$AVAIL_GB" -ge 10 ]; then
    info "磁盘空间偏紧 (${AVAIL_GB}GB), 建议 ≥20GB"
else
    fail "磁盘空间不足 (${AVAIL_GB}GB), 需要 ≥15GB"
fi

# 8. 内存
echo "[8] 内存"
MEM_TOTAL=$(free -h | awk '/Mem:/ {print $2}')
MEM_AVAIL=$(free -h | awk '/Mem:/ {print $7}')
info "总计: $MEM_TOTAL, 可用: $MEM_AVAIL"

# 9. 网络
echo "[9] 网络连通性"
if curl -sI --max-time 5 https://mirrors.aliyun.com > /dev/null 2>&1; then
    ok "外网可达 (mirrors.aliyun.com)"
elif wget -q --spider --timeout=5 https://mirrors.aliyun.com 2>/dev/null; then
    ok "外网可达 (mirrors.aliyun.com via wget)"
else
    fail "无法连接外网（安装依赖需要网络）"
fi

# 10. 端口监听
echo "[10] 已监听端口"
if command -v ss &>/dev/null; then
    ss -tlnp 2>/dev/null | grep -E "LISTEN" | awk '{print $4}' | while read addr; do
        info "监听: $addr"
    done
elif command -v netstat &>/dev/null; then
    netstat -tlnp 2>/dev/null | grep -E "LISTEN" | awk '{print $4}' | while read addr; do
        info "监听: $addr"
    done
else
    info "ss/netstat 不可用，跳过端口检查"
fi

# 11. 项目文件
echo "[11] 项目文件"
if [ -d /root/OCR ]; then
    ok "项目目录存在: /root/OCR"
    FILE_COUNT=$(find /root/OCR -type f | wc -l)
    info "文件数: $FILE_COUNT"
else
    info "项目目录 /root/OCR 不存在（需要上传）"
fi

echo ""
echo "============================================"
echo "  诊断完成"
echo "============================================"
echo ""
