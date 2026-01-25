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

# 3.5 自动映射：创建软链接以适配 WebUI 读取逻辑
# 即使直接传参，LlamaFactory WebUI 有时仍需在 saves 目录下有对应结构才能正确加载或显示
echo "--- 正在构建模型映射 ---"

# 智能生成链接名称 (处理 checkpoint-xxx 的情况)
LORA_DIR_NAME=$(basename "${LORA_PATH}")
if [[ "${LORA_DIR_NAME}" == checkpoint-* ]]; then
    PARENT_DIR=$(dirname "${LORA_PATH}")
    PARENT_NAME=$(basename "${PARENT_DIR}")
    LINK_NAME="${PARENT_NAME}_${LORA_DIR_NAME}"
else
    LINK_NAME="${LORA_DIR_NAME}"
fi

# 双向映射：同时映射到当前使用的模型目录 和 Qwen3-14B-Base (防止跨模型加载时的路径查找失败)
CURRENT_MODEL_NAME=$(basename "${MODEL_PATH}")
TARGET_MODELS=("${CURRENT_MODEL_NAME}" "Qwen3-14B-Base")
PREV_TARGET=""

for TARGET_MODEL in "${TARGET_MODELS[@]}"; do
    # 简单去重
    if [ "$TARGET_MODEL" == "$PREV_TARGET" ]; then continue; fi
    
    SAVES_DIR="${LLAMA_FACTORY_DIR}/saves/${TARGET_MODEL}/lora"
    mkdir -p "${SAVES_DIR}"
    
    LINK_PATH="${SAVES_DIR}/${LINK_NAME}"
    echo "创建映射 [${TARGET_MODEL}]: ${LINK_PATH} -> ${LORA_PATH}"
    rm -f "${LINK_PATH}"
    ln -sf "${LORA_PATH}" "${LINK_PATH}"
    
    PREV_TARGET="$TARGET_MODEL"
done

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
