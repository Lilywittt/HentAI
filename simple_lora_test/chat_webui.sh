#!/bin/bash

# ==============================================================================
# HentAI LoRA 聊天体验脚本 (灵活接口优化版)
# ==============================================================================
# 功能：
# 1. 自动环境配置与进程清理
# 2. 支持参数传入外部 LoRA 目录，默认为项目收割目录
# 3. 显式 0.0.0.0 监听，确保外部访问
# 4. 支持 Ctrl+C 平滑退出，清理残留进程
# ==============================================================================

# --- 配置接口 ---
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"
MODEL_PATH="/root/local-nvme/train_env/models/Qwen3-14B-abliterated"
DEFAULT_LORA_PATH="/root/workspace/HentAI/novel_data/lora_train_output/harvested_lora"

# 0. 信号捕获逻辑：实现 Ctrl+C 平滑退出
cleanup() {
    echo -e "\n--- 正在关闭聊天体验服务 ---"
    pkill -f "llamafactory.cli webui" || true
    echo "清理完毕，脚本已退出。"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. 接口处理：获取 LoRA 路径
INPUT_PATH=$1
if [ -n "$INPUT_PATH" ]; then
    if [[ "$INPUT_PATH" != /* ]]; then
        LORA_PATH="$(realpath "$INPUT_PATH")"
    else
        LORA_PATH="$INPUT_PATH"
    fi
    echo "提示: 正在使用外部 LoRA 路径: $LORA_PATH"
else
    LORA_PATH="$DEFAULT_LORA_PATH"
    echo "提示: 正在使用默认收割目录: $LORA_PATH"
fi

# 2. 环境激活
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 3. 检查 LoRA 路径有效性
if [ ! -f "${LORA_PATH}/adapter_config.json" ]; then
    echo "错误: 在 ${LORA_PATH} 未找到有效的 LoRA 适配器 (adapter_config.json)。"
    exit 1
fi

# 4. 启动聊天 WebUI
echo "--- 正在启动 HentAI 聊天 WebUI ---"
cd "${LLAMA_FACTORY_DIR}"
# 强制清理可能残留的进程
pkill -f "llamafactory.cli webui" || true

echo "----------------------------------------------------------------"
echo "聊天环境已准备就绪。如需退出，请按下 Ctrl+C。"
echo "----------------------------------------------------------------"

# 显式指定 0.0.0.0 监听，利用 Gradio 原生浏览器管理
GRADIO_SERVER_NAME="0.0.0.0" python -m llamafactory.cli webui \
    --model_name_or_path "${MODEL_PATH}" \
    --adapter_name_or_path "${LORA_PATH}" \
    --template qwen3 \
    --finetuning_type lora \
    --quantization_bit 4 \
    --infer_backend vllm
