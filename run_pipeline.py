# -*- coding: utf-8 -*-
"""
流程编排脚本 (Pipeline Script)
功能：串联执行数据生成（清洗）与数据校验流程。
"""
import asyncio
import sys
import os
import json
import datetime
import logging
from clean_novel_data import NovelCleaner
from validate_data import validate_one

# 配置日志
os.makedirs("logs", exist_ok=True)
log_filename = f"logs/pipeline_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pipeline")

def load_nicknames(char_name, source_novel=None, map_file="nickname_map.json"):
    """从外部 JSON 文件加载角色昵称，支持按作品归类"""
    if not os.path.exists(map_file):
        logger.warning(f"昵称映射文件 {map_file} 不存在，将不使用额外昵称")
        return []
    try:
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 优先在指定作品下查找
        if source_novel and source_novel in data:
            return data[source_novel].get(char_name, [])
        
        # 兼容性处理：如果没有找到或未指定作品，尝试直接查找（针对旧格式）
        if char_name in data and isinstance(data[char_name], list):
            return data[char_name]
            
        return []
    except Exception as e:
        logger.error(f"读取昵称映射文件失败: {e}")
        return []

async def run_pipeline():
    # --- 任务配置中心 ---
    # 1. 选择卷前缀 (如 "03", "04", 或 None 代表全本)
    TARGET_PREFIX = None
    
    # 2. 选择章节范围 (基于文件开头的数字编号，None 代表不限制)
    # 示例：处理第 100 到 150 章
    START_CHAPTER = None  # 起始编号
    END_CHAPTER = None    # 结束编号
    
    # 3. 目标角色配置
    TARGET_CHARACTER = "柳怀沙"
    SOURCE_NOVEL = "隐杀" # 原作名称，用于从昵称库中检索
    
    # 从配置文件自动加载昵称
    NICKNAME_LIST = load_nicknames(TARGET_CHARACTER, SOURCE_NOVEL)
    logger.info(f"已加载角色 [{TARGET_CHARACTER}] (出自: {SOURCE_NOVEL}) 的昵称列表: {NICKNAME_LIST}")

    # 4. Prompt 模板文件配置
    PROMPT_INSTRUCTION_FILE = "prompts/prompt_instruction.txt"
    OUTPUT_SCHEMA_FILE = "prompts/output_schema.txt"

    # 5. 是否强制刷新缓存 (True: 忽略缓存强制重跑; False: 优先使用缓存)
    FORCE_REFRESH = True


    
    logger.info(f"=== 开始执行流程 ===")
    logger.info(f"1. 正在生成数据: 角色[{TARGET_CHARACTER}] | 卷前缀[{TARGET_PREFIX}]...")
    
    cleaner = NovelCleaner(
        target_prefix=TARGET_PREFIX, 
        char_name=TARGET_CHARACTER, 
        nickname_list=NICKNAME_LIST,
        source_novel=SOURCE_NOVEL,
        prompt_instruction_file=PROMPT_INSTRUCTION_FILE, 
        output_schema_file=OUTPUT_SCHEMA_FILE, 
        force_refresh=FORCE_REFRESH
    )
    
    generated_files = await cleaner.run(start_idx=START_CHAPTER, end_idx=END_CHAPTER)
    
    if not generated_files:
        logger.warning("未生成或处理任何文件。")
        return

    logger.info(f"2. 正在校验 {len(generated_files)} 个生成文件...")
    
    passed_count = 0
    failed_count = 0
    
    for fpath in generated_files:
        is_valid = validate_one(fpath)
        if is_valid:
            passed_count += 1
        else:
            failed_count += 1
            
    logger.info("=== 流程汇总 ===")
    logger.info(f"总生成文件数: {len(generated_files)}")
    logger.info(f"校验通过:     {passed_count}")
    logger.info(f"校验失败:     {failed_count}")
    
    if failed_count > 0:
        logger.error("请查看上方日志以获取校验错误详情。")
    else:
        logger.info("所有生成文件均通过校验。")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_pipeline())
