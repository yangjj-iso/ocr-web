#!/usr/bin/env bash
# ============================================================
# 在 CUDA 12.3 裸容器内一键部署 OCR 档案识别系统
# 适用于: nvidia/cuda:12.3.x-devel-ubuntu22.04 + SSH 的容器
#
# 使用方式:
#   1. 从本地打包项目:  tar -czf ocr-deploy.tar.gz --exclude=node_modules --exclude=.git --exclude=__pycache__ -C <项目父目录> OCR
#   2. 上传到容器:      scp -P <SSH端口> ocr-deploy.tar.gz root@<IP>:/root/
#   3. SSH 进入容器:    ssh -p <SSH端口> root@<IP>
#   4. 解压:            cd /root && tar -xzf ocr-deploy.tar.gz
#   5. 执行部署:        bash /root/OCR/docker/cuda12.3-ssh/setup_project.sh
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
log()  { echo -e "${GREEN}[部署]${NC} $*"; }
warn() { echo -e "${YELLOW}[提示]${NC} $*"; }
err()  { echo -e "${RED}[错误]${NC} $*"; }

PROJECT_DIR="/root/OCR"

if [ ! -d "$PROJECT_DIR" ]; then
    err "请先将项目源码上传到 $PROJECT_DIR"
    echo ""
    echo "操作步骤："
    echo "  [本地] tar -czf ocr-deploy.tar.gz --exclude=node_modules --exclude=.git --exclude=__pycache__ -C <项目父目录> OCR"
    echo "  [本地] scp -P <SSH端口> ocr-deploy.tar.gz root@<IP>:/root/"
    echo "  [容器] cd /root && tar -xzf ocr-deploy.tar.gz"
    echo "  [容器] bash /root/OCR/docker/cuda12.3-ssh/setup_project.sh"
    exit 1
fi

cd "$PROJECT_DIR"

TOTAL_STEPS=10

# ============================================================
# 第 1 步: 配置 CUDA 环境变量
# ============================================================
log "[1/$TOTAL_STEPS] 配置 CUDA 环境变量..."

# 确保 nvcc 在 PATH 中（裸容器可能没有配置）
if ! command -v nvcc &>/dev/null; then
    CUDA_PATHS=("/usr/local/cuda/bin" "/usr/local/cuda-12.3/bin" "/usr/local/cuda-12/bin")
    for p in "${CUDA_PATHS[@]}"; do
        if [ -f "$p/nvcc" ]; then
            export PATH="$p:$PATH"
            export LD_LIBRARY_PATH="${p%/bin}/lib64:${LD_LIBRARY_PATH:-}"
            echo "export PATH=$p:\$PATH" >> /etc/profile.d/cuda.sh
            echo "export LD_LIBRARY_PATH=${p%/bin}/lib64:\$LD_LIBRARY_PATH" >> /etc/profile.d/cuda.sh
            log "  已配置 CUDA PATH: $p"
            break
        fi
    done
fi

if command -v nvcc &>/dev/null; then
    log "  nvcc 版本: $(nvcc --version | grep 'release' | awk '{print $NF}')"
else
    warn "  nvcc 未找到，PaddlePaddle 可能无法使用 GPU"
fi

# ============================================================
# 第 2 步: 安装系统基础依赖
# ============================================================
log "[2/$TOTAL_STEPS] 安装系统基础依赖（Python 3.11、Node.js 20、Redis、PostgreSQL、系统库）..."
log "  这一步较慢，请耐心等待..."

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq

# 2a. 安装 Python 3.11
if ! command -v python3.11 &>/dev/null; then
    log "  安装 Python 3.11..."
    apt-get install -y -qq software-properties-common > /dev/null 2>&1
    add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3.11-distutils > /dev/null 2>&1
    # 设置为默认 python
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 > /dev/null 2>&1
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 > /dev/null 2>&1
    log "  Python 3.11 安装完成"
else
    log "  Python 3.11 已存在，跳过"
fi

# 2b. 安装 pip
if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
    log "  安装 pip..."
    apt-get install -y -qq curl > /dev/null 2>&1
    curl -sS https://bootstrap.pypa.io/get-pip.py | python > /dev/null 2>&1
    log "  pip 安装完成"
fi
# 确保 pip 命令可用
if ! command -v pip &>/dev/null && command -v pip3 &>/dev/null; then
    ln -sf "$(which pip3)" /usr/local/bin/pip
fi

# 2c. 安装 Node.js 20（构建前端用）
if ! command -v node &>/dev/null; then
    log "  安装 Node.js 20..."
    apt-get install -y -qq curl gnupg > /dev/null 2>&1
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null 2>&1
    log "  Node.js $(node --version) 安装完成"
else
    log "  Node.js $(node --version) 已存在，跳过"
fi

# 2d. 安装 Redis
if ! command -v redis-server &>/dev/null; then
    log "  安装 Redis..."
    apt-get install -y -qq redis-server > /dev/null 2>&1
    log "  Redis 安装完成"
else
    log "  Redis 已存在，跳过"
fi

# 2e. 安装 PostgreSQL
if ! command -v psql &>/dev/null; then
    log "  安装 PostgreSQL..."
    apt-get install -y -qq postgresql postgresql-contrib > /dev/null 2>&1
    log "  PostgreSQL 安装完成"
else
    log "  PostgreSQL 已存在，跳过"
fi

# 2f. 安装 OpenCV / PaddlePaddle 运行时系统库
log "  安装系统运行时库..."
apt-get install -y -qq \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 sudo > /dev/null 2>&1

apt-get clean && rm -rf /var/lib/apt/lists/*
log "  系统依赖安装完成"
log "  Python: $(python --version 2>&1), pip: $(pip --version 2>&1 | awk '{print $2}'), Node: $(node --version), npm: $(npm --version)"

# ============================================================
# 第 3 步: 启动并配置 PostgreSQL
# ============================================================
log "[3/$TOTAL_STEPS] 配置 PostgreSQL..."
service postgresql start
sudo -u postgres psql -c "CREATE USER ocruser WITH PASSWORD 'ocr123456';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE ocr_db OWNER ocruser;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ocr_db TO ocruser;" 2>/dev/null || true
log "  PostgreSQL 已就绪 (ocruser/ocr_db)"

# ============================================================
# 第 4 步: 启动 Redis
# ============================================================
log "[4/$TOTAL_STEPS] 启动 Redis..."
redis-cli ping > /dev/null 2>&1 || redis-server --daemonize yes --maxmemory 512mb --maxmemory-policy allkeys-lru
log "  Redis 已就绪"

# ============================================================
# 第 5 步: 安装 PaddlePaddle GPU
# ============================================================
log "[5/$TOTAL_STEPS] 安装 PaddlePaddle GPU（CUDA 12.3）..."
log "  这一步可能需要 5-10 分钟..."
pip install paddlepaddle-gpu==3.1.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu123/ 2>&1 | tail -5
log "  PaddlePaddle 安装完成"

# 验证 PaddlePaddle GPU
python -c "
import paddle
print(f'  PaddlePaddle {paddle.__version__}')
print(f'  GPU 可用: {paddle.device.cuda.device_count() > 0}')
print(f'  GPU 数量: {paddle.device.cuda.device_count()}')
" 2>/dev/null || warn "  PaddlePaddle GPU 验证失败，后续可能需要排查"

# ============================================================
# 第 6 步: 安装项目 Python 依赖
# ============================================================
log "[6/$TOTAL_STEPS] 安装项目 Python 依赖..."
pip install --no-cache-dir -r "$PROJECT_DIR/requirements.docker.txt" -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 | tail -5
log "  Python 依赖安装完成"

# ============================================================
# 第 7 步: 预下载 OCR 模型
# ============================================================
log "[7/$TOTAL_STEPS] 预下载 3 个 OCR 模型（PP-OCRv5 / PP-StructureV3 / PaddleOCR-VL-1.5）..."
log "  这一步需要下载约 3-5GB 模型文件，请保持网络通畅..."
export PADDLE_PDX_CACHE_HOME="$PROJECT_DIR/.cache/paddlex"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export PADDLE_PDX_MODEL_SOURCE=bos
export FLAGS_json_format_model=0
export HF_HOME="$PROJECT_DIR/.cache/huggingface"
python "$PROJECT_DIR/scripts/prefetch_models.py"
log "  模型预下载完成"

# ============================================================
# 第 8 步: 构建前端
# ============================================================
log "[8/$TOTAL_STEPS] 构建前端..."
cd "$PROJECT_DIR/frontend"
npm ci --prefer-offline 2>&1 | tail -3
VITE_OUTPUT_DIR=dist npm run build 2>&1 | tail -5
cd "$PROJECT_DIR"
log "  前端构建完成"

# ============================================================
# 第 9 步: 初始化数据库表
# ============================================================
log "[9/$TOTAL_STEPS] 初始化数据库表..."
export DATABASE_URL="postgresql+asyncpg://ocruser:ocr123456@localhost:5432/ocr_db"
export REDIS_URL="redis://localhost:6379/0"
export UPLOAD_DIR="$PROJECT_DIR/uploads"
export CACHE_DIR="$PROJECT_DIR/.cache"
export OCR_DEVICE="gpu:0"
export OCR_LANG="ch"
export AUTH_ENABLED="false"
python -c "
import asyncio
from app.db.database import init_db
asyncio.run(init_db())
print('  数据库表创建完成')
"
log "  数据库已就绪"

# ============================================================
# 第 10 步: 创建启动/停止脚本
# ============================================================
log "[10/$TOTAL_STEPS] 创建启动/停止脚本..."

mkdir -p "$PROJECT_DIR/uploads" "$PROJECT_DIR/.cache" "$PROJECT_DIR/logs"

cat > "$PROJECT_DIR/start.sh" << 'STARTEOF'
#!/bin/bash
# ============================================
# 启动 OCR 档案识别系统全部服务
# 用法: cd /root/OCR && ./start.sh
# ============================================
set -e

echo "[启动] 检查并启动 PostgreSQL..."
service postgresql start 2>/dev/null || true
echo "[启动] 检查并启动 Redis..."
redis-cli ping > /dev/null 2>&1 || redis-server --daemonize yes --maxmemory 512mb --maxmemory-policy allkeys-lru

# 配置 CUDA PATH（如果需要）
if [ -f /etc/profile.d/cuda.sh ]; then
    source /etc/profile.d/cuda.sh
fi

export DATABASE_URL="postgresql+asyncpg://ocruser:ocr123456@localhost:5432/ocr_db"
export REDIS_URL="redis://localhost:6379/0"
export UPLOAD_DIR="/root/OCR/uploads"
export CACHE_DIR="/root/OCR/.cache"
export PADDLE_PDX_CACHE_HOME="/root/.paddlex"
export HF_HOME="/root/.cache/huggingface"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export FLAGS_json_format_model=0
export OCR_DEVICE="gpu:0"
export OCR_LANG="ch"
export OCR_VL_BACKEND="local"
export AUTH_ENABLED="false"

cd /root/OCR

# 终止旧进程（如果有）
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1

nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 > /root/OCR/logs/server.log 2>&1 &
echo ""
echo "============================================"
echo "  OCR 系统已启动!"
echo "============================================"
echo "  后端 PID: $!"
echo "  访问地址: http://<服务器IP>:8000"
echo "  查看日志: tail -f /root/OCR/logs/server.log"
echo "  停止服务: cd /root/OCR && ./stop_server.sh"
echo "============================================"
STARTEOF
chmod +x "$PROJECT_DIR/start.sh"

cat > "$PROJECT_DIR/stop_server.sh" << 'STOPEOF'
#!/bin/bash
pkill -f "uvicorn main:app" 2>/dev/null && echo "[停止] 后端已停止" || echo "[提示] 后端未在运行"
STOPEOF
chmod +x "$PROJECT_DIR/stop_server.sh"

# 创建容器重启后的自动恢复脚本
cat > /etc/profile.d/ocr_hint.sh << 'HINTEOF'
echo ""
echo "  OCR 档案识别系统已部署"
echo "  启动: cd /root/OCR && ./start.sh"
echo "  停止: cd /root/OCR && ./stop_server.sh"
echo ""
HINTEOF

log "  脚本创建完成"

# ============================================================
# 部署完成
# ============================================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  启动服务:  cd /root/OCR && ./start.sh"
echo "  停止服务:  cd /root/OCR && ./stop_server.sh"
echo "  查看日志:  tail -f /root/OCR/logs/server.log"
echo ""
echo "  GPU 状态:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "  (无法检测 GPU)"
echo ""
echo "  提示: 容器重启后需要重新执行 ./start.sh"
echo ""
