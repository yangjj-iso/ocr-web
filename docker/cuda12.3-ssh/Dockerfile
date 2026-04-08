# ============================================
# CUDA 12.3 + SSH 最小镜像
# 只含 CUDA 基础运行时 + SSH，体积最小
# ============================================
FROM docker.m.daocloud.io/nvidia/cuda:12.3.2-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Shanghai

# ========== 安装 SSH + 基础工具 ==========
RUN apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
    openssh-server \
    curl \
    wget \
    ca-certificates \
    || (apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    openssh-server curl wget ca-certificates) \
    && rm -rf /var/lib/apt/lists/*

# ========== 配置 SSH ==========
RUN mkdir -p /var/run/sshd \
    && echo 'root:root123' | chpasswd \
    && sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config \
    && echo "export VISIBLE=now" >> /etc/profile

WORKDIR /root
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
