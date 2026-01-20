#!/bin/bash

# ==============================================================================
# HentAI LoRA 训练产物收割脚本
# ==============================================================================
# 功能：将训练完成的 LoRA 核心权重从数据盘同步到项目目录，方便后续版本管理。
# ==============================================================================

# --- 配置接口 (可复用) ---
# 来源：训练输出目录 (local-nvme)
SOURCE_DIR="/root/local-nvme/train_output/hentai_lora_results"
# 去向：项目产物目录 (HentAI)
DEST_DIR="/root/workspace/HentAI/novel_data/lora_train_output/harvested_lora"

# 1. 检查来源目录
if [ ! -d "$SOURCE_DIR" ]; then
    echo "提示: 尚未在 $SOURCE_DIR 发现训练产物。"
    exit 0
fi

# 2. 执行收割 (同步核心文件)
echo "--- 正在收割 LoRA 核心产物 ---"
echo "来源: $SOURCE_DIR"
echo "去向: $DEST_DIR"

mkdir -p "$DEST_DIR"

# 只拷贝核心权重、配置文件、图表，不拷贝庞大的优化器状态文件 (optimizer.pt 等)
rsync -av --include='adapter_*' --include='*.json' --include='*.png' --include='*.txt' --exclude='*' "$SOURCE_DIR/" "$DEST_DIR/"

echo "收割完成！产物已存放在 $DEST_DIR"
echo "注意：本项目 .gitignore 已配置排除此目录，核心产物不会被上传到 Git。"
