#!/bin/bash

# ==============================================================================
# LoRA 训练统一启动脚本
# ==============================================================================
# 功能：自动挂载数据、生成配置、并基于 YAML 模板启动训练。
# ==============================================================================

# 0. 参数与路径
DATA_FILE_PATH="$1"
CONFIG_FILE="./configs/lora_sft.yaml"
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"

if [ -z "$DATA_FILE_PATH" ]; then
    echo "用法: $0 <数据文件路径.jsonl>"
    exit 1
fi

# 1. 环境激活
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 数据流接口实现 (Data Interface)
# ------------------------------------------------------------------------------
mkdir -p ./data
ABS_DATA_PATH=$(readlink -f "$DATA_FILE_PATH")
FILENAME=$(basename "$ABS_DATA_PATH")

# 创建软链接，实现数据零复制接入
ln -sf "$ABS_DATA_PATH" "./data/${FILENAME}"

# 动态注册数据集
cat > "./data/dataset_info.json" <<EOF
{
  "dynamic_dataset": {
    "file_name": "${FILENAME}",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
EOF

# 3. 启动训练
# ------------------------------------------------------------------------------
echo "--- 启动 LoRA 训练 ---"
echo "数据源: $ABS_DATA_PATH"
echo "配置项: $CONFIG_FILE"

python -m llamafactory.cli train "$CONFIG_FILE"

if [ $? -eq 0 ]; then
    echo "--- 训练任务完成 ---"
else
    echo "--- 训练任务失败 ---"
fi
