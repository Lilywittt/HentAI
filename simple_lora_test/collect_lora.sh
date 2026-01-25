#!/bin/bash

# ==============================================================================
# HentAI LoRA 训练产物收割脚本
# ==============================================================================
# 功能：将训练完成的 LoRA 核心权重从数据盘同步到项目目录，方便后续版本管理。
# 支持：指定绝对路径或默认目录下的相对路径。
# 用法：./collect_lora.sh [来源路径/名称] [目标路径/名称]
# ==============================================================================

# --- 默认基础配置 ---
# 默认来源基础目录 (当输入相对路径时以此为根)
DEFAULT_SOURCE_BASE="/root/local-nvme/train_output"
# 默认来源目录名
DEFAULT_SOURCE_NAME="hentai_lora_results"

# 默认去向基础目录 (当输入相对路径时以此为根)
DEFAULT_DEST_BASE="/root/workspace/HentAI/novel_data/lora_train_output"
# 默认去向目录名
DEFAULT_DEST_NAME="harvested_lora"

# --- 参数解析函数 ---
# resolve_path <input_arg> <default_base> <default_name>
resolve_path() {
    local input="$1"
    local base="$2"
    local default_name="$3"

    if [ -z "$input" ]; then
        # 情况1：未提供参数，使用默认全路径
        echo "${base}/${default_name}"
    elif [[ "$input" == /* ]]; then
        # 情况2：提供绝对路径，直接使用
        echo "$input"
    else
        # 情况3：提供相对路径，拼接到默认基础目录
        echo "${base}/${input}"
    fi
}

# 1. 解析路径
SOURCE_DIR=$(resolve_path "$1" "$DEFAULT_SOURCE_BASE" "$DEFAULT_SOURCE_NAME")
DEST_DIR=$(resolve_path "$2" "$DEFAULT_DEST_BASE" "$DEFAULT_DEST_NAME")

# 2. 检查来源目录
if [ ! -d "$SOURCE_DIR" ]; then
    echo "错误: 来源目录不存在: $SOURCE_DIR"
    echo "请检查路径是否正确，或是否已运行训练。"
    exit 1
fi

# 3. 执行收割 (同步核心文件)
echo "--- 正在收割 LoRA 核心产物 ---"
echo "来源: $SOURCE_DIR"
echo "去向: $DEST_DIR"

# 确保目标目录存在
mkdir -p "$DEST_DIR"

# 检查是否存在 rsync，如果不存在则回退到 cp
if command -v rsync &> /dev/null; then
    # 使用 rsync (更高效，支持 exclude)
    rsync -av \
        --include='adapter_*' \
        --include='*.json' \
        --include='*.png' \
        --include='*.txt' \
        --include='*.safetensors' \
        --exclude='*' \
        "$SOURCE_DIR/" "$DEST_DIR/"
else
    echo "提示: 未检测到 rsync，使用 cp 命令进行复制..."
    
    # 计数器
    count=0
    
    # 定义要复制的文件模式
    patterns=("adapter_*" "*.json" "*.png" "*.txt" "*.safetensors")
    
    for pattern in "${patterns[@]}"; do
        # 使用 find 查找根目录下匹配的文件 (不递归)
        # 注意: 这里使用 find 是为了更精确控制，避免 shell globbing 在文件不存在时报错或行为不一致
        find "$SOURCE_DIR" -maxdepth 1 -name "$pattern" -exec cp -v {} "$DEST_DIR/" \; | while read line; do
            ((count++))
        done
    done
fi

# 再次检查目标目录是否有文件
if [ -z "$(ls -A "$DEST_DIR")" ]; then
    echo "警告: 目标目录为空！可能来源目录中没有符合条件的核心文件 (adapter_*, *.json, *.safetensors 等)。"
else
    echo "--------------------------------------------------"
    echo "收割完成！产物已存放在: $DEST_DIR"
    echo "注意：本项目 .gitignore 已配置排除此目录。"
fi
