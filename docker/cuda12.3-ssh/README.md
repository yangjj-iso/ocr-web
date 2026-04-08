# CUDA 12.3 容器部署指南

适用于已有 CUDA 12.3 + SSH 的容器环境，一键部署 OCR 档案识别系统。

## 快速部署（3 步）

### 第 1 步：本地打包项目

在开发机上执行（项目根目录的父目录）：

```bash
# Windows (PowerShell)
cd D:\
tar -czf ocr-deploy.tar.gz --exclude=node_modules --exclude=.git --exclude=__pycache__ --exclude=logs OCR

# Linux/Mac
tar -czf ocr-deploy.tar.gz --exclude=node_modules --exclude=.git --exclude=__pycache__ --exclude=logs -C /path/to/parent OCR
```

### 第 2 步：上传到服务器容器

```bash
# 上传压缩包（注意端口号要匹配你容器的 SSH 端口）
scp -P 8722 ocr-deploy.tar.gz root@222.198.105.68:/root/

# SSH 进入容器
ssh -p 8722 root@222.198.105.68
# 密码: root123

# 解压
cd /root
tar -xzf ocr-deploy.tar.gz
```

### 第 3 步：一键部署

```bash
# 执行部署脚本（自动安装所有依赖 + 模型下载 + 前端构建）
bash /root/OCR/docker/cuda12.3-ssh/setup_project.sh

# 部署完成后启动服务
cd /root/OCR
./start.sh
```

浏览器访问: `http://222.198.105.68:<容器映射的8000端口>`

## setup_project.sh 会自动完成

| 步骤 | 内容 | 耗时 |
|------|------|------|
| 1/10 | 配置 CUDA PATH | ~1s |
| 2/10 | 安装 Python 3.11 + Node.js 20 + Redis + PostgreSQL + 系统库 | ~5min |
| 3/10 | 配置 PostgreSQL 数据库 | ~5s |
| 4/10 | 启动 Redis | ~1s |
| 5/10 | 安装 PaddlePaddle GPU (CUDA 12.3) | ~5-10min |
| 6/10 | 安装项目 Python 依赖 | ~3min |
| 7/10 | 下载 3 个 OCR 模型 (~3-5GB) | ~10-30min |
| 8/10 | 构建 Vue.js 前端 | ~2min |
| 9/10 | 初始化数据库表 | ~3s |
| 10/10 | 创建启动/停止脚本 | ~1s |

总计约 30-50 分钟（取决于网速）。

## 日常操作

```bash
# 启动服务
cd /root/OCR && ./start.sh

# 停止服务
cd /root/OCR && ./stop_server.sh

# 查看日志
tail -f /root/OCR/logs/server.log

# 检查 GPU 状态
nvidia-smi
```

## 端口说明

| 容器内端口 | 用途 |
|------------|------|
| 22 | SSH 远程连接 |
| 8000 | 后端 API + 前端页面 |

> **重要**: 容器内的8000端口需要映射到宿主机才能从外部访问。
> 如果容器启动时没有映射 8000 端口，需要重建容器并加上 `-p 18000:8000` 等参数。

## 容器重启后

容器重启后 PostgreSQL、Redis 和后端服务不会自动启动，需要手动执行：

```bash
ssh -p 8722 root@222.198.105.68
cd /root/OCR && ./start.sh
```

## GPU 要求

- 宿主机 CUDA 驱动 ≥ 12.3
- 宿主机需安装 NVIDIA Container Toolkit
- 建议显存 ≥ 16GB
- 容器启动时需 `--gpus all` 参数
