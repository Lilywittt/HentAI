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
import re
import logging
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, ValidationError

# 获取当前脚本所在目录 (data_cleaning)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 data_cleaning 的上一级)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

logger = logging.getLogger("validator")

# ==========================================
# Legacy Data Models (for default/old schema)
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
# Dynamic Validator Logic
# ==========================================

def extract_json_structure(text: str) -> Optional[Dict]:
    """From schema text (which may contain markdown), extract the JSON object."""
    # Try to find JSON code block
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try to find the first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end+1]
        else:
            return None
    
    try:
        # We want to use this as a template structure, so we load it.
        # But the template might have comments or placeholders.
        # Simple JSON load might fail if it's not valid JSON (e.g. comments).
        # We'll assume the schema file provided is valid JSON or valid JSON in markdown.
        return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Failed to parse JSON schema from text: {e}")
        return None

def validate_structure(data: Any, template: Any, path: str = "") -> List[str]:
    """
    Recursively check if `data` has the same keys/structure as `template`.
    Returns a list of error messages.
    """
    errors = []
    
    if isinstance(template, dict):
        if not isinstance(data, dict):
            errors.append(f"{path}: Expected dict, got {type(data).__name__}")
            return errors
        
        for k, v in template.items():
            if k not in data:
                errors.append(f"{path}: Missing key '{k}'")
            else:
                errors.extend(validate_structure(data[k], v, path=f"{path}.{k}" if path else k))
                
    elif isinstance(template, list):
        if not isinstance(data, list):
            errors.append(f"{path}: Expected list, got {type(data).__name__}")
            return errors
        
        if not template:
            return [] # Empty list in template means "list of anything" or just list
            
        # We assume the list in template has 1 item representing the schema of items
        item_template = template[0]
        for i, item in enumerate(data):
            errors.extend(validate_structure(item, item_template, path=f"{path}[{i}]"))
            
    # For other types (str, int, etc.), we don't validate specific values, just presence is enough via parent dict check.
    # The template values like "Description..." are ignored, only keys matter.
    
    return errors

def validate_dynamic(file_path: str, schema_path: str) -> bool:
    """Validate JSON file against a schema file."""
    try:
        # Load Data
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logger.warning(f"文件为空: {file_path}")
                return False
            data = json.loads(content)
            
        # Load Schema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_text = f.read()
            
        template = extract_json_structure(schema_text)
        if not template:
            logger.error(f"无法从 {schema_path} 提取有效的 JSON 结构模板")
            return False
            
        errors = validate_structure(data, template)
        
        if errors:
            logger.error(f"Schema 校验失败: {os.path.basename(file_path)}")
            for err in errors[:10]: # Limit error output
                logger.error(f"  - {err}")
            if len(errors) > 10:
                logger.error(f"  - ... (共 {len(errors)} 个错误)")
            return False
            
        logger.info(f"[PASS] {os.path.basename(file_path)}")
        return True

    except json.JSONDecodeError:
        logger.error(f"JSON 格式错误: {file_path}")
        return False
    except Exception as e:
        logger.error(f"动态校验发生错误: {str(e)}")
        return False

# ==========================================
# Main Validation Logic
# ==========================================

def validate_one(file_path: str, schema_file: Optional[str] = None) -> bool:
    """校验单个 JSON 文件。支持指定 Schema 文件。"""
    if schema_file and os.path.exists(schema_file):
        return validate_dynamic(file_path, schema_file)
    
    # Fallback to legacy hardcoded Pydantic validation
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
        logger.error(f"Schema 不匹配 (Legacy): {file_path}")
        # ... (Legacy error printing)
        return False
    except Exception as e:
        logger.error(f"处理 {file_path} 时发生未知错误: {str(e)}")
        return False

def validate_path(path: str, schema_file: Optional[str] = None):
    """入口函数：根据路径是文件还是目录分发处理逻辑。"""
    if os.path.isfile(path):
        logger.info(f"校验单文件: {path}")
        validate_one(path, schema_file)
        return

    # 目录逻辑
    json_files = glob.glob(os.path.join(path, "**", "*.json"), recursive=True)
    target_files = [f for f in json_files if ".cache" not in f]
    
    if not target_files:
        logger.warning(f"在 {path} 中未找到 JSON 文件")
        return

    logger.info(f"在 {path} 中找到 {len(target_files)} 个 JSON 文件。开始校验...")
    passed = 0
    failed = 0
    
    for f in target_files:
        if validate_one(f, schema_file):
            passed += 1
        else:
            failed += 1
            
    logger.info("-" * 30)
    logger.info(f"校验完成。总数: {len(target_files)}, 通过: {passed}, 失败: {failed}")

if __name__ == "__main__":
    target = os.path.join(PROJECT_ROOT, "novel_data", "lora_dataset")
    schema = None
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=target, help="Target file or directory")
    parser.add_argument("--schema", help="Path to schema definition file")
    args = parser.parse_args()
    
    validate_path(args.path, args.schema)
