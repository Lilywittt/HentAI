# -*- coding: utf-8 -*-
"""
流程编排脚本 (Pipeline Script)
功能：串联执行数据生成（清洗）与数据校验流程。
"""
import asyncio
import sys
from clean_novel_data import NovelCleaner
from validate_data import validate_one

async def run_pipeline():
    # --- 任务配置中心 ---
    # 1. 选择卷前缀 (如 "03", "04", 或 None 代表全本)
    TARGET_PREFIX = None
    
    # 2. 选择章节范围 (基于文件开头的数字编号，None 代表不限制)
    # 示例：处理第 100 到 150 章
    START_CHAPTER = None  # 起始编号
    END_CHAPTER = None    # 结束编号
    
    # 3. 目标角色配置
    TARGET_CHARACTER = "顾家明"

    # 4. Prompt 模板文件配置
    PROMPT_INSTRUCTION_FILE = "prompt_instruction.txt"
    OUTPUT_SCHEMA_FILE = "output_schema.txt"

    # 5. 是否强制刷新缓存 (True: 忽略缓存强制重跑; False: 优先使用缓存)
    FORCE_REFRESH = True


    
    print(f"=== 开始执行流程 ===")
    print(f"1. 正在生成数据: 角色[{TARGET_CHARACTER}] | 卷前缀[{TARGET_PREFIX}]...")
    
    cleaner = NovelCleaner(
        target_prefix=TARGET_PREFIX, 
        char_name=TARGET_CHARACTER, 
        prompt_instruction_file=PROMPT_INSTRUCTION_FILE, 
        output_schema_file=OUTPUT_SCHEMA_FILE, 
        force_refresh=FORCE_REFRESH
    )
    
    generated_files = await cleaner.run(start_idx=START_CHAPTER, end_idx=END_CHAPTER)
    
    if not generated_files:
        print("未生成或处理任何文件。")
        return

    print(f"\n2. 正在校验 {len(generated_files)} 个生成文件...")
    
    passed_count = 0
    failed_count = 0
    
    for fpath in generated_files:
        is_valid = validate_one(fpath)
        if is_valid:
            passed_count += 1
        else:
            failed_count += 1
            
    print("\n=== 流程汇总 ===")
    print(f"总生成文件数: {len(generated_files)}")
    print(f"校验通过:     {passed_count}")
    print(f"校验失败:     {failed_count}")
    
    if failed_count > 0:
        print("请查看上方日志以获取校验错误详情。")
    else:
        print("所有生成文件均通过校验。")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_pipeline())
