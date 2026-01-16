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
    PROMPT_FILE = "prompt_template.txt"
    DEFAULT_SYSTEM = "You are a professional novel data cleaner. Output JSON."

    @classmethod
    def load_system_prompt(cls) -> str:
        """从 prompt_template.txt 读取指令内容"""
        if not os.path.exists(cls.PROMPT_FILE):
            return cls.DEFAULT_SYSTEM
        
        # 尝试多种编码读取模板文件
        for enc in ['utf-8', 'gbk', 'utf-16']:
            try:
                with open(cls.PROMPT_FILE, 'r', encoding=enc) as f:
                    return f.read()
            except:
                continue
        return cls.DEFAULT_SYSTEM

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
    def __init__(self, target_prefix: Optional[str] = None):
        Config.validate()
        self.client = AsyncOpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.stats = StatsManager()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_TASKS)
        self.target_prefix = target_prefix or "full"
        self.system_prompt = PromptManager.load_system_prompt()
        
        # 自动生成带时间戳的任务输出目录
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_root = os.path.join(Config.LORA_DATASET_DIR, f"cleaned_{self.target_prefix}_{timestamp}")
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

    async def process_chapter(self, file_path: str, output_path: str, char_name: str):
        """处理单个章节的协程"""
        file_name = os.path.basename(file_path)
        try:
            content = self._read_file(file_path)
            
            # 本地语义过滤：跳过不含主角名称的章节，节省 API 成本
            if char_name not in content and char_name[1:] not in content:
                await self.stats.update_status("skipped")
                return

            # 缓存校验：如果处理过相同内容，直接复用结果
            c_hash = self._get_hash(content)
            c_path = os.path.join(Config.CACHE_DIR, f"{c_hash}.json")
            if os.path.exists(c_path):
                res = self._read_file(c_path)
                with open(output_path, 'w', encoding='utf-8') as f: f.write(res)
                await self.stats.update_status("success")
                return

            # 并发控制：在信号量槽位空闲时发起请求
            async with self.semaphore:
                response = await self._api_call([
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"目标角色: {char_name}\n来源文件: {file_name}\n\n待处理文本:\n{content}"}
                ])
                await self.stats.update_usage(response.usage)
                res_content = response.choices[0].message.content
                
                # 写入结果文件并存入缓存
                with open(output_path, 'w', encoding='utf-8') as f: f.write(res_content)
                with open(c_path, 'w', encoding='utf-8') as f: f.write(res_content)
                await self.stats.update_status("success")
        except Exception as e:
            logging.error(f"处理 {file_name} 时发生错误: {e}")
            await self.stats.update_status("failed")

    async def run(self, start_idx: Optional[int] = None, end_idx: Optional[int] = None):
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
        char_name = "顾家明" # 主角姓名
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

                tasks_list.append(self.process_chapter(cf, os.path.join(vol_out, file_name), char_name))

        if not tasks_list:
            logging.warning(f"在指定范围 [{start_idx} ~ {end_idx}] 内未找到可处理的任务")
            return

        logging.info(f"清洗任务启动: {self.target_prefix} | 范围: {start_idx or 'Start'} ~ {end_idx or 'End'} | 待处理章节: {len(tasks_list)}")
        
        # 利用 tqdm.asyncio 显示并发进度
        for f in tqdm.as_completed(tasks_list, total=len(tasks_list), desc=f"Cleaning {self.target_prefix}"):
            await f
            done = self.stats.success + self.stats.failed + self.stats.skipped
            # 每完成 10 章输出一次阶段性状态
            if done % 10 == 0 or done == len(tasks_list):
                logging.info(f"任务进度: {done}/{len(tasks_list)} | 成功:{self.stats.success} 失败:{self.stats.failed} 跳过:{self.stats.skipped} | 预估成本: {self.stats.get_cost():.2f} CNY")
        
        logging.info("-" * 30)
        logging.info(f"清洗完毕。最终预估成本: {self.stats.get_cost():.2f} CNY. 输出结果已存至: {self.output_root}")

# ==========================================
# 5. 执行入口
# ==========================================
if __name__ == "__main__":
    # 配置 Windows 平台异步事件循环策略，防止运行时警告
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # --- 任务配置中心 ---
    # 1. 选择卷前缀 (如 "03", "04", 或 None 代表全本)
    TARGET_PREFIX = "03" 
    
    # 2. 选择章节范围 (基于文件开头的数字编号，None 代表不限制)
    # 示例：处理第 100 到 150 章
    START_CHAPTER = None  # 起始编号
    END_CHAPTER = None    # 结束编号
    
    cleaner = NovelCleaner(target_prefix=TARGET_PREFIX)
    asyncio.run(cleaner.run(start_idx=START_CHAPTER, end_idx=END_CHAPTER))
