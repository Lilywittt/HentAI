#!/bin/bash

# ==============================================================================
# HentAI 公网分享启动脚本
# ==============================================================================
# 用法:
#   ./run_public_share.sh [LoRA路径] [用户名] [密码]
#
# 示例:
#   ./run_public_share.sh /root/local-nvme/train_output/checkpoint-1156 admin password
# ==============================================================================

VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"

# 1. 环境激活
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 参数处理
LORA_PATH=$1
USERNAME=${2:-"admin"}
PASSWORD=${3:-"hentai123"}

# 3. 检查路径有效性 (如果提供了路径)
if [ -n "$LORA_PATH" ]; then
    if [ ! -f "${LORA_PATH}/adapter_config.json" ]; then
        echo "错误: 在 ${LORA_PATH} 未找到有效的 LoRA 适配器。"
        exit 1
    fi
    LORA_ARG="--adapter_name_or_path ${LORA_PATH}"
fi

# 4. 启动服务
echo "--- 正在启动公网分享服务 ---"
echo "账号: $USERNAME"
echo "密码: $PASSWORD"
echo "----------------------------------------------------------------"

python public_share_chat.py \
    $LORA_ARG \
    --username "$USERNAME" \
    --password "$PASSWORD"
