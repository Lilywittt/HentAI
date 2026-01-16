# -*- coding: utf-8 -*-
"""
小说数据清洗与特征提取脚本 (异步高性能版)
功能：利用 DeepSeek API 提取小说章节中主角的交互行为，并转换为结构化 JSON 语料。
优化：支持异步 IO、并发控制、结果缓存及 Token 使用量统计。
"""

import os
import glob
import datetime
import sys
import logging
import asyncio
import hashlib
import json
from typing import List, Optional, Tuple, Dict
from tqdm.asyncio import tqdm
from openai import AsyncOpenAI
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# 1. Prompt 模板管理器 (从外部文件加载)
# ==========================================
class PromptManager:
    """
    负责从外部文件加载 AI 指令模板。
    将 Prompt 放在外部文件可以避免 Python 脚本本身的编码冲突，也方便用户直接编辑。
    """
    DEFAULT_SYSTEM = "You are a professional novel data cleaner. Output JSON."

    @staticmethod
    def _read_file(path: str) -> str:
        """鲁棒读取文件，支持多种编码自动切换"""
        if not os.path.exists(path):
            return ""
        for enc in ['utf-8', 'gbk', 'utf-16']:
            try:
                with open(path, 'r', encoding=enc) as f:
                    return f.read()
            except:
                continue
        return ""

    @classmethod
    def load_composed_prompt(cls, instruction_file: str, schema_file: str) -> str:
        """读取指令文件和Schema文件，并进行拼接"""
        instruction = cls._read_file(instruction_file)
        schema = cls._read_file(schema_file)
        
        if not instruction:
            return cls.DEFAULT_SYSTEM
            
        # 替换占位符
        if "{output_schema}" in instruction:
            return instruction.replace("{output_schema}", schema)
        else:
            # 如果没有占位符，默认追加在最后
            return f"{instruction}\n\n### Output Schema\n{schema}"

# ==========================================
# 2. 全局配置类
# ==========================================
class Config:
    """统一管理脚本运行所需的各项配置参数"""
    load_dotenv()
    API_KEY = os.getenv("DEEPSEEK_API_KEY")
    BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    # 路径定义
    BASE_INPUT_DIR = "novel_data/split_data"
    LORA_DATASET_DIR = "novel_data/lora_dataset"
    CACHE_DIR = "novel_data/.cache"
    
    # 并发与费用配置
    MAX_CONCURRENT_TASKS = 10 # 同时进行的 API 请求数
    PRICE_PROMPT = 0.001     # 每 1000 tokens 的输入价格 (CNY)
    PRICE_COMPLETION = 0.002 # 每 1000 tokens 的输出价格 (CNY)

    @classmethod
    def validate(cls):
        """检查必要配置项"""
        if not cls.API_KEY:
            raise ValueError("未在 .env 文件中找到 DEEPSEEK_API_KEY")

# ==========================================
# 3. 统计管理模块
# ==========================================
class StatsManager:
    """负责实时统计 Token 消耗量、任务成功率及预估费用"""
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self._lock = asyncio.Lock() # 协程锁，确保统计数据安全

    async def update_usage(self, usage):
        """更新 Token 使用量"""
        async with self._lock:
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens

    async def update_status(self, status: str):
        """更新任务执行状态"""
        async with self._lock:
            if status == "success": self.success += 1
            elif status == "failed": self.failed += 1
            elif status == "skipped": self.skipped += 1

    def get_cost(self) -> float:
        """根据当前消耗计算预估成本"""
        return (self.prompt_tokens / 1000 * Config.PRICE_PROMPT) + \
               (self.completion_tokens / 1000 * Config.PRICE_COMPLETION)

# ==========================================
# 4. 核心清洗引擎
# ==========================================
class NovelCleaner:
    """封装了从扫描文件到调用 API 处理的完整清洗流程"""
    def __init__(self, target_prefix: Optional[str] = None, char_name: str = "顾家明", 
                 prompt_instruction_file: str = "prompt_instruction.txt", 
                 output_schema_file: str = "output_schema.txt",
                 force_refresh: bool = False):
        Config.validate()
        self.client = AsyncOpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.stats = StatsManager()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_TASKS)
        self.target_prefix = target_prefix or "full"
        self.char_name = char_name
        self.system_prompt = PromptManager.load_composed_prompt(prompt_instruction_file, output_schema_file)
        self.force_refresh = force_refresh
        
        # 自动生成带时间戳的任务输出目录，包含角色名作为索引
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_root = os.path.join(Config.LORA_DATASET_DIR, f"cleaned_{self.char_name}_{self.target_prefix}_{timestamp}")
        os.makedirs(self.output_root, exist_ok=True)
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
        
        self._setup_logging()

    def _setup_logging(self):
        """初始化日志系统，同时输出到文件和控制台"""
        log_file = os.path.join(self.output_root, "processing.log")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                            handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)],
                            force=True)

    def _get_hash(self, content: str) -> str:
        """生成文本哈希值，用于缓存唯一识别"""
        return hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()

    def _read_file(self, path: str) -> str:
        """鲁棒读取文件，支持多种编码自动切换"""
        for enc in ['utf-8', 'gbk', 'utf-16']:
            try:
                with open(path, 'r', encoding=enc) as f: return f.read()
            except: continue
        with open(path, 'r', encoding='utf-8', errors='ignore') as f: return f.read()

    @retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
    async def _api_call(self, messages: List[Dict]):
        """执行带重试机制的异步 API 调用"""
        return await self.client.chat.completions.create(
            model="deepseek-chat", messages=messages, 
            response_format={"type": "json_object"}, temperature=0.3
        )

    async def process_chapter(self, file_path: str, output_path: str, char_name: str) -> Optional[str]:
        """处理单个章节的协程"""
        file_name = os.path.basename(file_path)
        try:
            content = self._read_file(file_path)
            
            # 本地语义过滤：跳过不含主角名称的章节，节省 API 成本
            if char_name not in content and char_name[1:] not in content:
                await self.stats.update_status("skipped")
                return None

            # 缓存校验：将 "Prompt 内容" 加入哈希计算，确保 Prompt 修改后缓存自动失效
            # 如果 force_refresh 为 True，则跳过缓存检查
            c_hash = self._get_hash(content + self.system_prompt)
            c_path = os.path.join(Config.CACHE_DIR, f"{c_hash}.json")
            
            if not self.force_refresh and os.path.exists(c_path):
                res = self._read_file(c_path)
                with open(output_path, 'w', encoding='utf-8') as f: f.write(res)
                await self.stats.update_status("success")
                return output_path

            # 并发控制：在信号量槽位空闲时发起请求
            async with self.semaphore:
                # 动态替换 System Prompt 中的角色占位符
                formatted_system_prompt = self.system_prompt.replace("{character_name}", char_name)
                
                response = await self._api_call([
                    {"role": "system", "content": formatted_system_prompt},
                    {"role": "user", "content": f"目标角色: {char_name}\n来源文件: {file_name}\n\n待处理文本:\n{content}"}
                ])
                await self.stats.update_usage(response.usage)
                res_content = response.choices[0].message.content
                
                # 写入结果文件并存入缓存
                with open(output_path, 'w', encoding='utf-8') as f: f.write(res_content)
                with open(c_path, 'w', encoding='utf-8') as f: f.write(res_content)
                await self.stats.update_status("success")
                return output_path
        except Exception as e:
            logging.error(f"处理 {file_name} 时发生错误: {e}")
            await self.stats.update_status("failed")
            return None

    async def run(self, start_idx: Optional[int] = None, end_idx: Optional[int] = None) -> List[str]:
        """
        启动清洗任务主循环
        :param start_idx: 起始章节编号 (包含)
        :param end_idx: 结束章节编号 (包含)
        """
        # 扫描并过滤目标卷册
        vols = sorted([d for d in glob.glob(os.path.join(Config.BASE_INPUT_DIR, "[0-9][0-9]_*")) if os.path.isdir(d)])
        if self.target_prefix != "full":
            vols = [v for v in vols if os.path.basename(v).startswith(self.target_prefix)]
        
        if not vols:
            logging.error(f"未找到前缀为 {self.target_prefix} 的目标文件夹")
            return

        # 构造异步任务列表
        tasks_list = []
        for vol in vols:
            vol_out = os.path.join(self.output_root, os.path.basename(vol))
            os.makedirs(vol_out, exist_ok=True)
            
            # 获取当前卷下的所有章节文件
            chapter_files = sorted(glob.glob(os.path.join(vol, "*.txt")))
            
            for cf in chapter_files:
                file_name = os.path.basename(cf)
                # 提取文件名开头的数字编号 (如 "001")
                try:
                    current_file_idx = int(file_name.split('_')[0])
                except (ValueError, IndexError):
                    current_file_idx = -1

                # 范围过滤逻辑
                if start_idx is not None and current_file_idx < start_idx:
                    continue
                if end_idx is not None and current_file_idx > end_idx:
                    continue

                tasks_list.append(self.process_chapter(cf, os.path.join(vol_out, file_name), self.char_name))

        if not tasks_list:
            logging.warning(f"在指定范围 [{start_idx} ~ {end_idx}] 内未找到可处理的任务")
            return []

        logging.info(f"清洗任务启动: {self.target_prefix} | 范围: {start_idx or 'Start'} ~ {end_idx or 'End'} | 待处理章节: {len(tasks_list)}")
        
        generated_files = []
        # 利用 tqdm.asyncio 显示并发进度
        for f in tqdm.as_completed(tasks_list, total=len(tasks_list), desc=f"Cleaning {self.target_prefix}"):
            res = await f
            if res:
                generated_files.append(res)
            
            done = self.stats.success + self.stats.failed + self.stats.skipped
            # 每完成 10 章输出一次阶段性状态
            if done % 10 == 0 or done == len(tasks_list):
                logging.info(f"任务进度: {done}/{len(tasks_list)} | 成功:{self.stats.success} 失败:{self.stats.failed} 跳过:{self.stats.skipped} | 预估成本: {self.stats.get_cost():.2f} CNY")
        
        logging.info("-" * 30)
        logging.info(f"清洗完毕。最终预估成本: {self.stats.get_cost():.2f} CNY. 输出结果已存至: {self.output_root}")
        return generated_files

# ==========================================
# 5. 执行入口
# ==========================================
if __name__ == "__main__":
    # 配置 Windows 平台异步事件循环策略，防止运行时警告
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # --- 任务配置中心 ---
    # 1. 选择卷前缀 (如 "03", "04", 或 None 代表全本)
    TARGET_PREFIX = "02" 
    
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
    
    cleaner = NovelCleaner(
        target_prefix=TARGET_PREFIX, 
        char_name=TARGET_CHARACTER, 
        prompt_instruction_file=PROMPT_INSTRUCTION_FILE, 
        output_schema_file=OUTPUT_SCHEMA_FILE, 
        force_refresh=FORCE_REFRESH
    )
    asyncio.run(cleaner.run(start_idx=START_CHAPTER, end_idx=END_CHAPTER))
