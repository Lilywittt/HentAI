#!/bin/bash

# ==============================================================================
# LLaMA-Factory WebUI 启动脚本
# ==============================================================================
# 功能：启动可视化界面，支持在浏览器中配置参数、管理数据集并监控训练过程。
# ==============================================================================

# 1. 环境配置
VENV_DIR="/root/local-nvme/train_env/venv"
LLAMA_FACTORY_DIR="/root/local-nvme/train_env/LLaMA-Factory"
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${LLAMA_FACTORY_DIR}/src:$PYTHONPATH"

# 2. 数据接口接入
# 指定 DATA_DIR 环境变量，使 Web 界面能自动识别 ./data/dataset_info.json 中的数据集
export DATA_DIR="/root/workspace/HentAI/simple_lora_test/data"

# 3. 启动 WebUI
# 默认端口: 7860
echo "--- 正在启动 WebUI 可视化界面 ---"
echo "您可以访问 http://localhost:7860 进行操作"
echo "自定义数据集目录已设置为: $DATA_DIR"

# 切换到脚本所在目录，确保相对路径正确
cd "$(dirname "$0")"
python -m llamafactory.cli webui
