#!/bin/bash

# ==============================================================================
# HentAI LLaMA-Factory 自动化训练脚本 (直接路径接口版)
# ==============================================================================
# 功能：
# 1. 自动环境配置
# 2. 直接接受数据集路径作为参数
# 3. 自动根据输入路径生成索引、同步数据、调整 YAML 配置
# 4. 强制静默载入 HentAI 预设参数，100% 自动生效
# 5. 支持 Ctrl+C 平滑退出，清理残留进程
# ==============================================================================

# --- 配置接口 ---
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"
HENTAI_CONFIG_TEMPLATE="/root/workspace/HentAI/simple_lora_test/configs/hentai_webui_config.yaml"
DEFAULT_DATA_DIR="/root/workspace/HentAI/novel_data/lora_train_dataset"

# 0. 信号捕获逻辑：实现 Ctrl+C 平滑退出
cleanup() {
    echo -e "\n--- 正在平滑关闭 HentAI 训练环境 ---"
    pkill -f "llamafactory.cli webui" || true
    echo "环境清理完毕，脚本已安全退出。"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. 环境激活
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 数据集路径接口处理
RAW_INPUT_PATH=$1

if [ -z "$RAW_INPUT_PATH" ]; then
    SELECTED_PATH=$(ls -t "${DEFAULT_DATA_DIR}"/*.jsonl 2>/dev/null | head -n 1)
    echo "--- 自动载入默认数据集 ---"
    echo "提示: 未指定路径，已为您自动选择最新产出的语料: $(basename "$SELECTED_PATH")"
else
    if [[ "$RAW_INPUT_PATH" = /* ]]; then
        SELECTED_PATH="$RAW_INPUT_PATH"
    elif [ -f "$RAW_INPUT_PATH" ]; then
        SELECTED_PATH="$(realpath "$RAW_INPUT_PATH")"
    elif [ -f "${DEFAULT_DATA_DIR}/$RAW_INPUT_PATH" ]; then
        SELECTED_PATH="${DEFAULT_DATA_DIR}/$RAW_INPUT_PATH"
    else
        echo "错误: 无法定位数据集文件: $RAW_INPUT_PATH"
        exit 1
    fi
fi

if [ -z "$SELECTED_PATH" ] || [ ! -f "$SELECTED_PATH" ]; then
    echo "错误: 未找到任何有效的数据集文件。"
    exit 1
fi

DATASET_FILENAME=$(basename "$SELECTED_PATH")
DATASET_KEY="${DATASET_FILENAME%.*}"
echo "--- 数据集就绪 ---"
echo "路径: ${SELECTED_PATH}"

# 3. 深度清理历史映射与索引
echo "--- 正在清理历史环境 ---"
find "${LLAMA_FACTORY_DIR}/data/" -maxdepth 1 -type l -lname "/root/workspace/*" -delete
rm -f "${LLAMA_FACTORY_DIR}/data/dataset_info.json"

# 4. 动态挂载、生成索引
echo "--- 正在同步环境与索引 ---"
ln -sf "${SELECTED_PATH}" "${LLAMA_FACTORY_DIR}/data/${DATASET_FILENAME}"
cat <<EOF > "${LLAMA_FACTORY_DIR}/data/dataset_info.json"
{
  "${DATASET_KEY}": {
    "file_name": "${DATASET_FILENAME}",
    "columns": { "prompt": "instruction", "query": "input", "response": "output" }
  }
}
EOF

# 强化 Checkpoint 可见性：将数据盘上的原始产物目录软链到 LLaMA-Factory 内部
# 修正：软链名称改为极其明确的 data_disk_raw_checkpoints，避免与“收割”混淆
mkdir -p "${LLAMA_FACTORY_DIR}/saves/Qwen3-14B-Base/lora"
rm -f "${LLAMA_FACTORY_DIR}/saves/Qwen3-14B-Base/lora/harvested_results" # 彻底清理旧的误导性名称

# 生成带时间戳的输出路径，防止覆盖
TIMESTAMP=$(date +"%Y-%m-%d-%H-%M-%S")
OUTPUT_DIR="/root/local-nvme/train_output/hentai_lora_results_${DATASET_KEY}_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

# 动态创建指向当前任务输出目录的软链，方便在 WebUI 中查看历史 Checkpoint
# 同时更新一个 latest 软链方便快速访问
ln -sf "${OUTPUT_DIR}" "${LLAMA_FACTORY_DIR}/saves/Qwen3-14B-Base/lora/${DATASET_KEY}_${TIMESTAMP}_checkpoints"
ln -sf "${OUTPUT_DIR}" "${LLAMA_FACTORY_DIR}/saves/Qwen3-14B-Base/lora/${DATASET_KEY}_latest_checkpoints"

# 5. 自动调整 YAML 配置并静默注入
echo "--- 正在注入训练配置 ---"
# TIMESTAMP 已在上方定义
rm -f "${LLAMA_FACTORY_DIR}/llamaboard_config"/*.yaml

TEMP_CONFIG_FILE="${LLAMA_FACTORY_DIR}/llamaboard_config/hentai_auto_${TIMESTAMP}.yaml"
mkdir -p "$(dirname "$TEMP_CONFIG_FILE")"

cp "${HENTAI_CONFIG_TEMPLATE}" "$TEMP_CONFIG_FILE"
sed -i "s/- lora_train_dataset/- ${DATASET_KEY}/g" "$TEMP_CONFIG_FILE"
# 动态修改输出目录，使用带时间戳的路径
sed -i "s|train.output_dir: .*|train.output_dir: ${OUTPUT_DIR}|g" "$TEMP_CONFIG_FILE"

mkdir -p "${LLAMA_FACTORY_DIR}/llamaboard_cache"
cat <<EOF > "${LLAMA_FACTORY_DIR}/llamaboard_cache/user_config.yaml"
lang: zh
last_model: Qwen3-14B-Base
path_dict:
  Qwen3-14B-Base: /root/local-nvme/train_env/models/Qwen3-14B-Base
EOF

# 6. 启动
echo "--- 正在启动 HentAI 训练 WebUI ---"
cd "${LLAMA_FACTORY_DIR}"
pkill -f "llamafactory.cli webui" || true

echo "----------------------------------------------------------------"
echo "自动生效策略：已将训练目标锁定为 ${DATASET_KEY}。"
echo "配置已自动填充。产物每 10 步自动存盘。"
echo "----------------------------------------------------------------"

GRADIO_SERVER_NAME="0.0.0.0" python -m llamafactory.cli webui --share false
