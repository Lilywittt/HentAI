# -*- coding: utf-8 -*-
"""
数据接入接口 (Data Interface)
功能：将 HentAI 生成的 JSONL 数据集注册到 LLaMA-Factory 训练框架中。
本脚本提供可调用的接口，也可直接执行以完成数据“挂载”。
"""

import os
import json
import glob
import shutil
import sys
import argparse

# 获取当前脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# HentAI 根目录
HENTAI_ROOT = os.path.dirname(SCRIPT_DIR)
# 默认数据存放目录
DEFAULT_DATA_DIR = os.path.join(HENTAI_ROOT, "novel_data", "lora_train_dataset")

# 默认训练框架目录 (假设在 ../train_env/LLaMA-Factory)
WORKSPACE_ROOT = os.path.dirname(HENTAI_ROOT)
DEFAULT_FRAMEWORK_DIR = os.path.join(WORKSPACE_ROOT, "train_env", "LLaMA-Factory")

class DataInterface:
    def __init__(self, framework_dir: str = None):
        """
        初始化数据接口
        :param framework_dir: LLaMA-Factory 的根目录路径
        """
        self.framework_dir = framework_dir or DEFAULT_FRAMEWORK_DIR
        self.dataset_info_path = os.path.join(self.framework_dir, "data", "dataset_info.json")

    def find_latest_dataset(self, data_dir: str = None) -> str:
        """
        查找最新的 JSONL 数据集文件
        :param data_dir: HentAI 数据集生成目录
        :return: 最新文件的绝对路径，若未找到返回 None
        """
        if not data_dir:
            data_dir = DEFAULT_DATA_DIR
            
        if not os.path.exists(data_dir):
            print(f"[Error] 数据目录不存在: {data_dir}")
            return None
            
        # 查找所有 jsonl 文件
        files = glob.glob(os.path.join(data_dir, "*.jsonl"))
        if not files:
            print(f"[Warning] 在目录中未找到 JSONL 文件: {data_dir}")
            return None
            
        # 按修改时间排序，取最新的
        latest_file = max(files, key=os.path.getmtime)
        print(f"[Info] 找到最新数据集: {os.path.basename(latest_file)}")
        return latest_file

    def register_dataset(self, dataset_path: str, dataset_name: str = "hentai_lora") -> bool:
        """
        将数据集注册到 LLaMA-Factory
        1. 在框架 data 目录下创建软链接
        2. 更新 dataset_info.json 配置文件
        
        :param dataset_path: 源数据集绝对路径
        :param dataset_name: 在框架中使用的注册名称
        :return: 是否成功
        """
        if not os.path.exists(self.framework_dir):
            print(f"[Error] 训练框架目录不存在: {self.framework_dir}")
            return False
            
        framework_data_dir = os.path.join(self.framework_dir, "data")
        if not os.path.exists(framework_data_dir):
            print(f"[Error] 框架 data 目录不存在: {framework_data_dir}")
            return False

        # 1. 创建软链接 (Symlink)
        # 目标链接文件名 (为了方便管理，统一命名)
        link_name = f"{dataset_name}.jsonl"
        link_path = os.path.join(framework_data_dir, link_name)
        
        # 如果存在旧文件/链接，先删除
        if os.path.exists(link_path) or os.path.islink(link_path):
            try:
                os.remove(link_path)
            except Exception as e:
                print(f"[Error] 无法删除旧链接: {e}")
                return False
        
        try:
            # 创建软链接: dataset_path -> link_path
            os.symlink(dataset_path, link_path)
            print(f"[Info] 已创建软链接: {link_path} -> {dataset_path}")
        except OSError as e:
            # Windows 下可能需要管理员权限或使用 copy
            print(f"[Warning] 创建软链接失败 ({e})，尝试复制文件...")
            try:
                shutil.copy2(dataset_path, link_path)
                print(f"[Info] 已复制文件: {link_path}")
            except Exception as e2:
                print(f"[Error] 文件复制失败: {e2}")
                return False

        # 2. 更新 dataset_info.json
        if not os.path.exists(self.dataset_info_path):
            print(f"[Error] 配置文件不存在: {self.dataset_info_path}")
            return False
            
        try:
            with open(self.dataset_info_path, 'r', encoding='utf-8') as f:
                dataset_info = json.load(f)
        except json.JSONDecodeError:
            print(f"[Error] 配置文件 JSON 格式错误")
            return False
            
        # 构造注册信息 (Alpaca 格式)
        entry = {
            "file_name": link_name,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output"
            }
        }
        
        # 更新或新增条目
        dataset_info[dataset_name] = entry
        
        try:
            with open(self.dataset_info_path, 'w', encoding='utf-8') as f:
                json.dump(dataset_info, f, indent=2, ensure_ascii=False)
            print(f"[Success] 数据集 '{dataset_name}' 已成功注册到 LLaMA-Factory。")
            return True
        except Exception as e:
            print(f"[Error] 写入配置文件失败: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="HentAI 数据集接入工具")
    parser.add_argument("--file", "-f", type=str, help="指定要接入的 JSONL 文件名 (需位于 novel_data/lora_train_dataset 中)")
    parser.add_argument("--path", "-p", type=str, help="指定要接入的 JSONL 文件的绝对路径")
    args = parser.parse_args()
    
    print("=== 开始执行数据接入流程 ===")
    
    # 初始化接口
    interface = DataInterface()
    dataset_path = None
    
    if args.path:
        # 直接指定绝对路径
        dataset_path = args.path
        if not os.path.exists(dataset_path):
            print(f"[Error] 指定的文件不存在: {dataset_path}")
            sys.exit(1)
        print(f"[Info] 使用指定路径文件: {dataset_path}")
        
    elif args.file:
        # 指定默认目录下的文件名
        dataset_path = os.path.join(DEFAULT_DATA_DIR, args.file)
        if not os.path.exists(dataset_path):
            print(f"[Error] 指定文件在默认目录中不存在: {dataset_path}")
            sys.exit(1)
        print(f"[Info] 使用指定文件: {dataset_path}")
        
    else:
        # 自动查找最新
        print("[Info] 未指定文件，尝试自动查找最新数据集...")
        dataset_path = interface.find_latest_dataset()
        
    if not dataset_path:
        print("[Error] 未找到可用数据，流程终止。")
        sys.exit(1)
        
    # 执行注册
    success = interface.register_dataset(dataset_path)
    
    if success:
        print("=== 数据接入完成 ===")
    else:
        print("=== 数据接入失败 ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
