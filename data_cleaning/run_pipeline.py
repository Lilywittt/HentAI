# -*- coding: utf-8 -*-
"""
流程编排脚本 (Pipeline Script)
功能：串联执行数据生成（清洗）与数据校验流程。
"""
import asyncio
import sys
import os
import json
import argparse
import datetime
import logging
from clean_novel_data import NovelCleaner, load_nicknames
from validate_data import validate_one

# 获取当前脚本所在目录 (data_cleaning)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 data_cleaning 的上一级)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# 配置日志
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"pipeline_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pipeline")


def load_config(config_file=None):
    """加载外部 JSON 配置文件"""
    if config_file is None:
        config_file = os.path.join(CURRENT_DIR, "config.json")

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"无法读取配置文件 {config_file}: {e}")
    return {}

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="小说数据清洗流程编排")
    parser.add_argument("--character", type=str, help="目标角色名称")
    parser.add_argument("--novel", type=str, help="来源小说名称")
    parser.add_argument("--prefix", type=str, help="卷前缀 (如 '03')")
    parser.add_argument("--start", type=int, help="起始章节编号")
    parser.add_argument("--end", type=int, help="结束章节编号")
    parser.add_argument("--instruction", "-ins", type=str, help="自定义 Prompt 指令文件名 (在 prompts 目录下)")
    parser.add_argument("--schema", "-sch", type=str, help="自定义 Output Schema 文件名 (在 prompts 目录下)")
    parser.add_argument("--no-refresh", action="store_true", help="不强制刷新缓存 (默认强制刷新)")
    # 这里的 parse_known_args 允许有未定义的参数传入而不报错，增强兼容性
    args, _ = parser.parse_known_args()
    return args

async def run_pipeline():
    # 加载外部配置 (优先级: CLI > Config > 默认值)
    config = load_config()
    args = parse_args()

    # --- 任务配置中心 ---
    
    # 1. 选择卷前缀 (默认 None 代表全本)
    # 逻辑: 如果 CLI 有值则用 CLI，否则尝试用 Config，最后回退到 None
    TARGET_PREFIX = args.prefix if args.prefix else config.get("target_prefix")
    
    # 2. 选择章节范围 (默认 None 不限制)
    START_CHAPTER = args.start if args.start is not None else config.get("start_chapter")
    END_CHAPTER = args.end if args.end is not None else config.get("end_chapter")
    
    # 3. 目标角色配置 (默认: 叶灵静 / 隐杀)
    TARGET_CHARACTER = args.character or config.get("target_character") or "叶灵静"
    SOURCE_NOVEL = args.novel or config.get("source_novel") or "隐杀"
    
    # 从配置文件自动加载昵称
    NICKNAME_LIST = load_nicknames(TARGET_CHARACTER, SOURCE_NOVEL)
    logger.info(f"已加载角色 [{TARGET_CHARACTER}] (出自: {SOURCE_NOVEL}) 的昵称列表: {NICKNAME_LIST}")

    # 4. Prompt 模板文件配置 (优先级: CLI > 默认值)
    ins_file = args.instruction or "prompt_instruction.txt"
    sch_file = args.schema or "output_schema.txt"
    
    PROMPT_INSTRUCTION_FILE = os.path.join(CURRENT_DIR, "prompts", ins_file)
    OUTPUT_SCHEMA_FILE = os.path.join(CURRENT_DIR, "prompts", sch_file)

    # 5. 是否强制刷新缓存 (True: 忽略缓存强制重跑; False: 优先使用缓存)
    # 逻辑: 默认 True。CLI --no-refresh 设为 False。Config 可覆盖。
    if args.no_refresh:
        FORCE_REFRESH = False
    else:
        # Config 默认为 True
        FORCE_REFRESH = config.get("force_refresh", True)


    
    logger.info(f"=== 开始执行流程 ===")
    logger.info(f"配置生效: 角色=[{TARGET_CHARACTER}] 来源=[{SOURCE_NOVEL}] 卷=[{TARGET_PREFIX}] 范围=[{START_CHAPTER}-{END_CHAPTER}] 强刷=[{FORCE_REFRESH}]")
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
        # 使用当前配置的 Schema 文件进行动态校验
        is_valid = validate_one(fpath, schema_file=OUTPUT_SCHEMA_FILE)
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
