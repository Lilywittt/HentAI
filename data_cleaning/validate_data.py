# -*- coding: utf-8 -*-
"""
数据校验脚本
功能：校验生成的 JSON 数据是否符合 output_schema.txt 中定义的结构。
依赖：pydantic
"""
import os
import json
import glob
import sys
import logging
from typing import List, Optional, Literal
from pydantic import BaseModel, ValidationError

# 获取当前脚本所在目录 (data_cleaning)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 data_cleaning 的上一级)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

logger = logging.getLogger("validator")

# ==========================================
# 数据模型定义 (对应 output_schema.txt)
# ==========================================

class MetaInfo(BaseModel):
    global_scene_type: Literal["Combat", "Daily_Life", "Negotiation", "Romance", "Suspense", "Other"]

class InterlocutorInfo(BaseModel):
    name: str
    relationship_tag: str

class Trigger(BaseModel):
    sender: str
    content: str
    type: Literal["dialogue", "action", "environment"]

class CharacterResponse(BaseModel):
    active_persona: str
    inner_monologue: str
    external_action: Optional[str] = None
    speech_text: Optional[str] = None
    mood_state: str

class InteractionUnit(BaseModel):
    id: Optional[str] = None
    global_id: Optional[int] = None
    scene_snapshot: str
    interlocutor_info: InterlocutorInfo
    trigger: Trigger
    character_response: CharacterResponse

class AnalysisOutput(BaseModel):
    meta_info: MetaInfo
    interaction_units: List[InteractionUnit]

# ==========================================
# 校验逻辑
# ==========================================

def validate_one(file_path: str) -> bool:
    """校验单个 JSON 文件。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logger.warning(f"文件为空: {file_path}")
                return False
            data = json.loads(content)
        
        AnalysisOutput.model_validate(data)
        logger.info(f"[PASS] {os.path.basename(file_path)}")
        return True
        
    except json.JSONDecodeError:
        logger.error(f"JSON 格式错误: {file_path}")
        return False
    except ValidationError as e:
        logger.error(f"Schema 不匹配: {file_path}")
        for err in e.errors():
            loc_tuple = err['loc']
            loc = "->".join(str(l) for l in loc_tuple)
            msg = err['msg']

            # 尝试获取出错数据的 ID 信息
            id_info = ""
            # 如果错误发生在 interaction_units 列表中的某一项
            if len(loc_tuple) >= 2 and loc_tuple[0] == 'interaction_units' and isinstance(loc_tuple[1], int):
                try:
                    idx = loc_tuple[1]
                    # 确保 data 是字典且包含 interaction_units 列表，且索引有效
                    if (isinstance(data, dict) and 
                        "interaction_units" in data and 
                        isinstance(data["interaction_units"], list) and 
                        0 <= idx < len(data["interaction_units"])):
                        
                        item = data["interaction_units"][idx]
                        if isinstance(item, dict):
                            # 提取 id 和 global_id
                            curr_id = item.get("id")
                            curr_global_id = item.get("global_id")
                            
                            parts = []
                            if curr_id is not None:
                                parts.append(f"id={curr_id}")
                            if curr_global_id is not None:
                                parts.append(f"global_id={curr_global_id}")
                            
                            if parts:
                                id_info = f" (Data: {', '.join(parts)})"
                except Exception:
                    pass

            logger.error(f"  - 位置: {loc}, 错误信息: {msg}{id_info}")
        return False
    except Exception as e:
        logger.error(f"处理 {file_path} 时发生未知错误: {str(e)}")
        return False

def validate_path(path: str):
    """入口函数：根据路径是文件还是目录分发处理逻辑。"""
    if os.path.isfile(path):
        logger.info(f"校验单文件: {path}")
        validate_one(path)
        return

    # 目录逻辑
    json_files = glob.glob(os.path.join(path, "**", "*.json"), recursive=True)
    txt_files = glob.glob(os.path.join(path, "**", "*.txt"), recursive=True)
    target_files = [f for f in json_files + txt_files if ".cache" not in f]
    
    if not target_files:
        logger.warning(f"在 {path} 中未找到 JSON 或 TXT 文件 (已忽略 .cache)")
        return

    logger.info(f"在 {path} 中找到 {len(target_files)} 个 JSON 文件。开始校验...")
    passed = 0
    failed = 0
    
    for f in target_files:
        if validate_one(f):
            passed += 1
        else:
            failed += 1
            
    logger.info("-" * 30)
    logger.info(f"校验完成。总数: {len(target_files)}, 通过: {passed}, 失败: {failed}")

if __name__ == "__main__":
    # 默认目标
    target = os.path.join(PROJECT_ROOT, "novel_data", "lora_dataset")
    
    # 命令行参数支持
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    if not os.path.exists(target):
        # 如果是直接运行，且未配置 logger，简单的 print 做保底
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)
        logging.error(f"路径不存在: {target}")
        sys.exit(1)
        
    validate_path(target)
