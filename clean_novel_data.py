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
import shutil
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
            elif status == "empty": self.skipped += 1

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
                 nickname_list: Optional[List[str]] = None, source_novel: Optional[str] = None,
                 prompt_instruction_file: str = "prompts/prompt_instruction.txt", 
                 output_schema_file: str = "prompts/output_schema.txt",
                 force_refresh: bool = False):
        Config.validate()
        self.client = AsyncOpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.stats = StatsManager()
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_TASKS)
        self.target_prefix = target_prefix or "full"
        self.char_name = char_name
        self.nickname_list = nickname_list or []
        self.source_novel = source_novel or ""
        self.system_prompt = PromptManager.load_composed_prompt(prompt_instruction_file, output_schema_file)
        self.force_refresh = force_refresh
        
        # 自动生成带时间戳的任务输出目录，包含角色名作为索引
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_root = os.path.join(Config.LORA_DATASET_DIR, f"cleaned_{self.char_name}_{self.target_prefix}_{timestamp}")
        os.makedirs(self.output_root, exist_ok=True)
        
        # 如果强制刷新，先清空缓存目录
        if self.force_refresh:
            self._clear_cache()
            
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
        
        self._setup_logging()

    def _clear_cache(self):
        """清空缓存目录"""
        if os.path.exists(Config.CACHE_DIR):
            try:
                shutil.rmtree(Config.CACHE_DIR)
                print(f"Cache cleared: {Config.CACHE_DIR}")
            except Exception as e:
                print(f"Failed to clear cache: {e}")

    def _setup_logging(self):
        """初始化日志系统"""
        # 使用 logger 实例而不是全局配置
        self.logger = logging.getLogger("cleaner")
        self.logger.setLevel(logging.INFO)
        
        # 添加本地文件 Handler
        log_file = os.path.join(self.output_root, "processing.log")
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.logger.addHandler(fh)

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
            
            # 本地语义过滤：跳过不含主角名称关键部分的章节
            short_name = char_name[1:] if len(char_name) > 1 else char_name
            
            # 构建关键词集合：全名 + 短名 + 自定义昵称
            keywords = {char_name, short_name}
            if self.nickname_list:
                keywords.update(self.nickname_list)
            
            # 只要包含任意一个关键词，即视为命中
            if not any(k in content for k in keywords if k):
                await self.stats.update_status("skipped")
                self.logger.info(f"章节 {file_name} 本地过滤跳过 (未发现角色关键词)")
                # 即使跳过也生成空文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({"meta_info": {"global_scene_type": "Other"}, "interaction_units": []}, f, ensure_ascii=False, indent=2)
                return output_path

            # 创建输出目录（如果不存在）
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 缓存校验
            c_hash = self._get_hash(content + self.system_prompt)
            c_path = os.path.join(Config.CACHE_DIR, f"{c_hash}.json")
            
            if not self.force_refresh and os.path.exists(c_path):
                try:
                    res_data = json.loads(self._read_file(c_path))
                    with open(output_path, 'w', encoding='utf-8') as f: 
                        json.dump(res_data, f, ensure_ascii=False, indent=2)
                    
                    if not res_data.get("interaction_units"):
                        await self.stats.update_status("empty")
                        self.logger.info(f"章节 {file_name} 缓存命中: 角色无互动 (空)")
                    else:
                        await self.stats.update_status("success")
                        self.logger.info(f"章节 {file_name} 缓存命中: 提取成功")
                    return output_path
                except:
                    pass

            # 并发控制
            async with self.semaphore:
                formatted_system_prompt = self.system_prompt.replace("{character_name}", char_name)
                if "{source_novel}" in formatted_system_prompt:
                    formatted_system_prompt = formatted_system_prompt.replace("{source_novel}", self.source_novel)
                
                response = await self._api_call([
                    {"role": "system", "content": formatted_system_prompt},
                    {"role": "user", "content": f"目标角色: {char_name}\n来源文件: {file_name}\n\n待处理文本:\n{content}"}
                ])
                await self.stats.update_usage(response.usage)
                res_content = response.choices[0].message.content
                
                try:
                    res_data = json.loads(res_content)
                    with open(output_path, 'w', encoding='utf-8') as f: 
                        json.dump(res_data, f, ensure_ascii=False, indent=2)
                    with open(c_path, 'w', encoding='utf-8') as f: 
                        json.dump(res_data, f, ensure_ascii=False, indent=2)

                    if not res_data.get("interaction_units"):
                        await self.stats.update_status("empty")
                        self.logger.info(f"章节 {file_name} 处理完毕: 角色无互动 (空)")
                    else:
                        await self.stats.update_status("success")
                        self.logger.info(f"章节 {file_name} 处理完毕: 提取成功")
                    return output_path
                except json.JSONDecodeError:
                    self.logger.error(f"解析 {file_name} 的 AI 响应失败: 格式非 JSON")
                    await self.stats.update_status("failed")
                    return None
        except Exception as e:
            self.logger.error(f"处理 {file_name} 时发生错误: {e}")
            await self.stats.update_status("failed")
            return None

    async def run(self, start_idx: Optional[int] = None, end_idx: Optional[int] = None) -> List[str]:
        """启动清洗任务主循环"""
        vols = sorted([d for d in glob.glob(os.path.join(Config.BASE_INPUT_DIR, "[0-9][0-9]_*")) if os.path.isdir(d)])
        if self.target_prefix != "full":
            vols = [v for v in vols if os.path.basename(v).startswith(self.target_prefix)]
        
        if not vols:
            self.logger.error(f"未找到前缀为 {self.target_prefix} 的目标文件夹")
            return []

        tasks_list = []
        for vol in vols:
            vol_out = os.path.join(self.output_root, os.path.basename(vol))
            os.makedirs(vol_out, exist_ok=True)
            chapter_files = sorted(glob.glob(os.path.join(vol, "*.txt")))
            
            for cf in chapter_files:
                file_name = os.path.basename(cf)
                try:
                    current_file_idx = int(file_name.split('_')[0])
                except:
                    current_file_idx = -1

                if start_idx is not None and current_file_idx < start_idx: continue
                if end_idx is not None and current_file_idx > end_idx: continue

                tasks_list.append(self.process_chapter(cf, os.path.join(vol_out, file_name), self.char_name))

        if not tasks_list:
            self.logger.warning(f"未找到可处理的任务")
            return []

        self.logger.info(f"清洗任务启动: {len(tasks_list)} 章节")
        
        generated_files = []
        for f in tqdm.as_completed(tasks_list, total=len(tasks_list), desc=f"Cleaning {self.target_prefix}"):
            res = await f
            if res: generated_files.append(res)
            
            done = self.stats.success + self.stats.failed + self.stats.skipped
            if done % 10 == 0 or done == len(tasks_list):
                self.logger.info(f"进度: {done}/{len(tasks_list)} | 成功:{self.stats.success} 失败:{self.stats.failed} 跳过/空:{self.stats.skipped} | 成本: {self.stats.get_cost():.2f} CNY")

        self.logger.info("开始标记序号...")
        # 确保按文件名排序，保证全局ID的顺序正确
        generated_files.sort(key=lambda p: os.path.basename(p))
        
        global_counter = 1
        for file_path in generated_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                if "interaction_units" in data and data["interaction_units"]:
                    prefix = os.path.basename(file_path).split('_')[0]
                    for i, unit in enumerate(data["interaction_units"], 1):
                        unit["id"] = f"{prefix}_{i:03d}"
                        unit["global_id"] = global_counter
                        global_counter += 1
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"标记序号出错 {file_path}: {e}")
        
        self.logger.info(f"清洗完毕。输出至: {self.output_root}")
        return generated_files

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    cleaner = NovelCleaner(target_prefix="02", char_name="顾家明", force_refresh=True)
    asyncio.run(cleaner.run())
