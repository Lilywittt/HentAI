#!/bin/bash

# ==============================================================================
# HentAI LLaMA-Factory 自动化训练脚本 (直接路径接口版)
# ==============================================================================
# 功能：
# 1. 自动环境配置
# 2. 直接接受数据集路径作为参数 (例如: ./run_webui.sh novel_data/my_data.jsonl)
# 3. 自动根据输入路径生成索引、同步数据、调整 YAML 配置
# 4. 强制静默载入 HentAI 预设参数，100% 自动生效
# ==============================================================================

# --- 配置接口 ---
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"
HENTAI_CONFIG_TEMPLATE="/root/workspace/HentAI/simple_lora_test/configs/hentai_webui_config.yaml"
# 默认搜寻数据集的基础目录
DEFAULT_DATA_DIR="/root/workspace/HentAI/novel_data/lora_train_dataset"

# 1. 环境激活
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 数据集路径接口处理
RAW_INPUT_PATH=$1

if [ -z "$RAW_INPUT_PATH" ]; then
    # 自动寻找最新的语料作为缺省值
    SELECTED_PATH=$(ls -t "${DEFAULT_DATA_DIR}"/*.jsonl 2>/dev/null | head -n 1)
    echo "--- 自动载入默认数据集 ---"
    echo "提示: 未指定路径，已为您自动选择最新产出的语料: $(basename "$SELECTED_PATH")"
else
    # 检查输入是否是绝对路径，如果不是，尝试相对于当前目录或默认目录补全
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
    echo "错误: 未找到任何有效的数据集文件。请检查 ${DEFAULT_DATA_DIR}"
    exit 1
fi

DATASET_FILENAME=$(basename "$SELECTED_PATH")
DATASET_KEY="${DATASET_FILENAME%.*}"
echo "--- 数据集就绪 ---"
echo "完整路径: ${SELECTED_PATH}"
echo "数据集名: ${DATASET_KEY}"

# 3. 清理并动态挂载
echo "--- 正在同步环境与索引 ---"
# 清理 LLaMA-Factory 内部旧映射
find "${LLAMA_FACTORY_DIR}/data/" -maxdepth 1 -type l -lname "/root/workspace/*" -delete
rm -f "${LLAMA_FACTORY_DIR}/data/dataset_info.json"

# 建立新软链
ln -sf "${SELECTED_PATH}" "${LLAMA_FACTORY_DIR}/data/${DATASET_FILENAME}"

# 生成索引文件
cat <<EOF > "${LLAMA_FACTORY_DIR}/data/dataset_info.json"
{
  "${DATASET_KEY}": {
    "file_name": "${DATASET_FILENAME}",
    "columns": { "prompt": "instruction", "query": "input", "response": "output" }
  }
}
EOF

# 4. 自动调整 YAML 配置并静默注入
echo "--- 正在注入训练配置 ---"
TIMESTAMP=$(date +"%Y-%m-%d-%H-%M-%S")
TEMP_CONFIG_FILE="${LLAMA_FACTORY_DIR}/llamaboard_config/${TIMESTAMP}.yaml"
mkdir -p "$(dirname "$TEMP_CONFIG_FILE")"

# 清理旧的自动配置
rm -f "${LLAMA_FACTORY_DIR}/llamaboard_config"/202*.yaml

# 使用 sed 动态注入当前选定的数据集 key
cp "${HENTAI_CONFIG_TEMPLATE}" "$TEMP_CONFIG_FILE"
# 替换 train.dataset 下的列表项
sed -i "s/- lora_train_dataset/- ${DATASET_KEY}/g" "$TEMP_CONFIG_FILE"

# 强制劫持 WebUI 的“最后一次配置”缓存，确保 100% 自动载入
mkdir -p "${LLAMA_FACTORY_DIR}/llamaboard_cache"
cat <<EOF > "${LLAMA_FACTORY_DIR}/llamaboard_cache/user_config.yaml"
lang: zh
last_model: Qwen3-14B-Base
path_dict:
  Qwen3-14B-Base: /root/local-nvme/train_env/models/Qwen3-14B-Base
EOF

# 5. 启动
echo "--- 正在启动 HentAI 训练 WebUI ---"
cd "${LLAMA_FACTORY_DIR}"
pkill -f "llamafactory.cli webui" || true

echo "----------------------------------------------------------------"
echo "自动生效策略：已将训练目标锁定为 ${DATASET_KEY}。"
echo "打开网页后，无需操作，参数已为您填充完毕。"
echo "----------------------------------------------------------------"

GRADIO_SERVER_NAME="0.0.0.0" python -m llamafactory.cli webui --share false
