#!/bin/bash

# ==============================================================================
# HentAI LoRA 聊天体验脚本
# ==============================================================================
# 功能：抓取指定位置的 LoRA 产物，加载基座模型并打开 Web 聊天端。
# ==============================================================================

# --- 配置接口 (可复用) ---
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"
# 基座模型路径
MODEL_PATH="/root/local-nvme/train_env/models/Qwen3-14B-abliterated"
# LoRA 产物路径 (可指定收割后的目录或原始输出目录)
LORA_PATH="/root/workspace/HentAI/novel_data/lora_train_output/harvested_lora"

# 1. 环境激活
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
else
    echo "错误: 未找到虚拟环境 ${VENV_DIR}。"
    exit 1
fi

export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 检查 LoRA 路径
if [ ! -f "${LORA_PATH}/adapter_config.json" ]; then
    echo "错误: 在 ${LORA_PATH} 未找到有效的 LoRA 适配器文件。"
    echo "请先运行 ./collect_lora.sh 或检查训练输出。"
    exit 1
fi

# 3. 启动聊天 WebUI
echo "--- 正在启动聊天体验 WebUI ---"
echo "基座模型: ${MODEL_PATH}"
echo "LoRA 适配器: ${LORA_PATH}"

# 在后台尝试打开浏览器 (默认端口 7860)
(
  sleep 5
  python3 -m webbrowser "http://localhost:7860" 2>/dev/null || echo "请手动访问 http://localhost:7860"
) &

# 运行推理端
cd "${LLAMA_FACTORY_DIR}"
python -m llamafactory.cli webui \
    --model_name_or_path "${MODEL_PATH}" \
    --adapter_name_or_path "${LORA_PATH}" \
    --template qwen3 \
    --finetuning_type lora \
    --quantization_bit 4 \
    --infer_backend vllm
