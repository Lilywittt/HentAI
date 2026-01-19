# -*- coding: utf-8 -*-
"""
环境自检报告 (Environment Check)
功能：检查 LoRA 训练所需的部署环境是否准备就绪。
"""

import os
import json
import sys

# 获取路径信息
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HENTAI_ROOT = os.path.dirname(SCRIPT_DIR)
WORKSPACE_ROOT = os.path.dirname(HENTAI_ROOT)

# 定义预期的外部资源路径
# 优先检测本地高速数据盘 (与 deploy_server.sh 逻辑一致)
LOCAL_DISK = "/root/local-nvme"
if os.path.exists(LOCAL_DISK) and os.access(LOCAL_DISK, os.W_OK):
    BASE_DEPLOY_DIR = LOCAL_DISK
else:
    BASE_DEPLOY_DIR = WORKSPACE_ROOT

TRAIN_ENV_DIR = os.path.join(BASE_DEPLOY_DIR, "train_env")
LLAMA_FACTORY_DIR = os.path.join(TRAIN_ENV_DIR, "LLaMA-Factory")
MODELS_DIR = os.path.join(TRAIN_ENV_DIR, "models")
DATASET_INFO_PATH = os.path.join(LLAMA_FACTORY_DIR, "data", "dataset_info.json")

def print_status(item, status, message=""):
    """打印格式化的状态信息"""
    mark = "✅ [PASS]" if status else "❌ [FAIL]"
    print(f"{mark} {item:<20} | {message}")

def check_environment():
    print("=== 开始环境自检 ===\n")
    print(f"部署根目录: {TRAIN_ENV_DIR}\n")
    
    all_passed = True

    # 1. 检查 LLaMA-Factory 部署
    if os.path.exists(LLAMA_FACTORY_DIR) and os.path.isdir(LLAMA_FACTORY_DIR):
        print_status("训练框架", True, f"路径: {LLAMA_FACTORY_DIR}")
    else:
        print_status("训练框架", False, "未找到 LLaMA-Factory 目录")
        all_passed = False

    # 2. 检查基座模型
    # 简单的非空检查
    model_exists = False
    if os.path.exists(MODELS_DIR):
        subdirs = [d for d in os.listdir(MODELS_DIR) if os.path.isdir(os.path.join(MODELS_DIR, d))]
        if subdirs:
            print_status("基座模型", True, f"发现模型: {', '.join(subdirs)}")
            model_exists = True
        else:
            print_status("基座模型", False, "模型目录为空")
            all_passed = False
    else:
        print_status("基座模型", False, "未找到模型目录")
        all_passed = False

    # 3. 检查数据集注册情况
    # 检查 dataset_info.json 中是否有 hentai_lora
    dataset_registered = False
    if os.path.exists(DATASET_INFO_PATH):
        try:
            with open(DATASET_INFO_PATH, 'r', encoding='utf-8') as f:
                info = json.load(f)
            
            if "hentai_lora" in info:
                entry = info["hentai_lora"]
                file_name = entry.get("file_name")
                # 检查链接文件是否存在
                link_path = os.path.join(LLAMA_FACTORY_DIR, "data", file_name)
                if os.path.exists(link_path):
                    print_status("数据集注册", True, f"已注册且文件存在 ({file_name})")
                    dataset_registered = True
                else:
                    print_status("数据集注册", False, f"已注册但文件缺失 ({file_name})")
                    all_passed = False
            else:
                print_status("数据集注册", False, "未找到 'hentai_lora' 注册信息")
                all_passed = False
        except Exception as e:
            print_status("数据集注册", False, f"读取配置文件失败: {e}")
            all_passed = False
    else:
        print_status("数据集注册", False, "LLaMA-Factory 配置文件缺失")
        all_passed = False

    print("\n=== 自检总结 ===")
    if all_passed:
        print("🎉 环境部署完善，可以开始训练！")
    else:
        print("⚠️  环境存在问题，请根据上述检查项修复。")
        sys.exit(1)

if __name__ == "__main__":
    check_environment()
