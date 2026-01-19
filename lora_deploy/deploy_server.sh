#!/bin/bash
# ==============================================================================
# 脚本名称: deploy_server.sh
# 功能描述: 自动化部署 LLaMA-Factory 训练框架及基座模型
# 使用说明: 在 HentAI/lora_deploy 目录下执行，或在根目录通过路径执行
# ==============================================================================

# 设置错误时立即退出，确保安全
set -e

# --- 1. 路径配置 ---

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 获取 HentAI 项目根目录 (假设脚本在 HentAI/lora_deploy)
HENTAI_ROOT="$(dirname "$SCRIPT_DIR")"

# 获取工作区根目录 (HentAI 的上一级)，这是放置重资产的地方
WORKSPACE_ROOT="$(dirname "$HENTAI_ROOT")"

# --- 自动检测本地数据盘 (Local NVMe) ---
# 很多云服务器/容器会将高速数据盘挂载在 /root/local-nvme
LOCAL_DISK="/root/local-nvme"
if [ -d "$LOCAL_DISK" ] && [ -w "$LOCAL_DISK" ]; then
    echo "[Info] 检测到本地高速数据盘: $LOCAL_DISK，将优先部署至此处。"
    BASE_DEPLOY_DIR="$LOCAL_DISK"
else
    echo "[Warning] 未检测到本地数据盘，将部署至默认工作区根目录。注意：若系统盘空间不足可能导致下载失败。"
    BASE_DEPLOY_DIR="$WORKSPACE_ROOT"
fi

# 定义外部部署目录名称
TRAIN_ENV_DIR="$BASE_DEPLOY_DIR/train_env"
LLAMA_FACTORY_DIR="$TRAIN_ENV_DIR/LLaMA-Factory"
MODELS_DIR="$TRAIN_ENV_DIR/models"

# --- 配置区 (Configuration) ---
# 用户请在此处修改模型和仓库设置
# -----------------------------

# [重要] 基座模型来源
# 修改此变量以更换基座模型 (需为 HuggingFace 模型 ID)
# 示例: "stabilityai/stable-diffusion-xl-base-1.0" 或 "Qwen/Qwen2.5-7B-Instruct"
MODEL_REPO="huihui-ai/Qwen3-14B-abliterated"

# 国内用户可能需要配置 HF 镜像 (已启用)
export HF_ENDPOINT=https://hf-mirror.com

# 配置 Hugging Face 缓存路径到数据盘，防止撑爆系统盘
export HF_HOME="$TRAIN_ENV_DIR/.cache/huggingface"
mkdir -p "$HF_HOME"

# [可选] Hugging Face Access Token
# 下载受限模型或私有模型时需要。建议通过环境变量传入，也可在此处硬编码。
# export HF_TOKEN="your_token_here"

# 配置 pip 镜像源 (清华源)
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

echo "=== 开始部署流程 ==="
echo "工作区根目录: $WORKSPACE_ROOT"
echo "部署目标目录: $TRAIN_ENV_DIR"

# --- 2. 环境初始化 ---

# 创建部署目录
if [ ! -d "$TRAIN_ENV_DIR" ]; then
    echo "[Info] 创建部署目录: $TRAIN_ENV_DIR"
    mkdir -p "$TRAIN_ENV_DIR"
else
    echo "[Info] 部署目录已存在: $TRAIN_ENV_DIR"
fi

# 检查并安装系统依赖 (git-lfs, python3-venv)
echo "[Info] 检查系统依赖..."
PACKAGES_TO_INSTALL=""

if ! command -v git-lfs &> /dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL git-lfs"
fi

# 检查 venv 模块 (Debian/Ubuntu 常需单独安装 python3-venv)
if ! dpkg -s python3-venv &> /dev/null && command -v apt-get &> /dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL python3-venv"
fi

if [ ! -z "$PACKAGES_TO_INSTALL" ]; then
    echo "[Info] 正在安装缺失依赖: $PACKAGES_TO_INSTALL"
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y $PACKAGES_TO_INSTALL
        git lfs install
    else
        echo "[Error] 无法自动安装依赖，请手动安装: $PACKAGES_TO_INSTALL"
        exit 1
    fi
else
    echo "[Info] 系统依赖检查通过。"
    git lfs install
fi

# --- 3. 配置 Python 虚拟环境 (解决 externally-managed-environment 问题) ---

VENV_DIR="$TRAIN_ENV_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[Info] 创建 Python 虚拟环境: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "[Info] 虚拟环境已存在: $VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
# 升级 pip
pip install --upgrade pip

# --- 4. 部署 LLaMA-Factory 训练框架 ---
echo "--- 阶段 1: 部署 LLaMA-Factory ---"

if [ -d "$LLAMA_FACTORY_DIR" ]; then
    echo "[Info] LLaMA-Factory 已存在，跳过克隆。"
else
    echo "[Info] 正在克隆 LLaMA-Factory (使用 Gitee 镜像)..."
    git clone https://gitee.com/hiyouga/LLaMA-Factory.git "$LLAMA_FACTORY_DIR"
fi

# 安装依赖
echo "[Info] 正在安装 LLaMA-Factory 依赖..."
# 注意: 这里会安装到当前系统的 Python 环境。建议在虚拟环境中使用。
# 为简单起见，这里直接安装。
pip install -r "$LLAMA_FACTORY_DIR/requirements.txt"
# 安装 LLaMA-Factory 自身 (以支持 CLI 调用)
pip install -e "$LLAMA_FACTORY_DIR"

echo "[Success] LLaMA-Factory 部署完成。"

# --- 5. 部署基座模型 ---

echo "--- 阶段 2: 部署基座模型 ---"

# 创建模型存放目录
mkdir -p "$MODELS_DIR"

# 提取模型名称 (例如 Qwen2.5-7B-Instruct)
MODEL_NAME=$(basename "$MODEL_REPO")
TARGET_MODEL_PATH="$MODELS_DIR/$MODEL_NAME"

if [ -d "$TARGET_MODEL_PATH" ]; then
    echo "[Info] 模型目录已存在: $TARGET_MODEL_PATH"
    echo "       (若需重新下载，请手动删除该目录)"
else
    echo "[Info] 开始下载模型: $MODEL_REPO"
    echo "       存放路径: $TARGET_MODEL_PATH"
    echo "       (注意：模型文件较大，请耐心等待...)"
    
    # 优先尝试使用 huggingface-cli 下载 (更稳定)
    if command -v huggingface-cli &> /dev/null; then
        # 如果设置了 HF_TOKEN，huggingface-cli 会自动读取
        huggingface-cli download --resume-download "$MODEL_REPO" --local-dir "$TARGET_MODEL_PATH" --local-dir-use-symlinks False
    else
        # 回退到 git clone
        echo "[Info] 未找到 huggingface-cli，使用 git clone 下载..."
        cd "$MODELS_DIR"
        # 如果提供了 Token，则使用认证方式克隆
        if [ ! -z "$HF_TOKEN" ]; then
             git clone "https://user:$HF_TOKEN@huggingface.co/$MODEL_REPO"
        else
             git clone "https://huggingface.co/$MODEL_REPO"
        fi
    fi
fi

echo "[Success] 基座模型部署流程结束。"
echo "=== 所有部署任务已完成 ==="
