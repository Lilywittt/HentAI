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
from typing import List, Optional, Literal
from pydantic import BaseModel, ValidationError

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
                print(f"[WARN] 文件为空: {file_path}")
                return False
            data = json.loads(content)
        
        AnalysisOutput.model_validate(data)
        print(f"[PASS] {os.path.basename(file_path)}")
        return True
        
    except json.JSONDecodeError:
        print(f"[ERROR] JSON 格式错误: {file_path}")
        return False
    except ValidationError as e:
        print(f"[FAIL] Schema 不匹配: {file_path}")
        for err in e.errors():
            loc = "->".join(str(l) for l in err['loc'])
            msg = err['msg']
            print(f"  - 位置: {loc}, 错误信息: {msg}")
        return False
    except Exception as e:
        print(f"[ERROR] 处理 {file_path} 时发生未知错误: {str(e)}")
        return False

def validate_path(path: str):
    """入口函数：根据路径是文件还是目录分发处理逻辑。"""
    if os.path.isfile(path):
        print(f"校验单文件: {path}")
        validate_one(path)
        return

    # 目录逻辑
    json_files = glob.glob(os.path.join(path, "**", "*.json"), recursive=True)
    txt_files = glob.glob(os.path.join(path, "**", "*.txt"), recursive=True)
    target_files = [f for f in json_files + txt_files if ".cache" not in f]
    
    if not target_files:
        print(f"在 {path} 中未找到 JSON 或 TXT 文件 (已忽略 .cache)")
        return

    print(f"在 {path} 中找到 {len(target_files)} 个 JSON 文件。开始校验...")
    passed = 0
    failed = 0
    
    for f in target_files:
        if validate_one(f):
            passed += 1
        else:
            failed += 1
            
    print("-" * 30)
    print(f"校验完成。总数: {len(target_files)}, 通过: {passed}, 失败: {failed}")

if __name__ == "__main__":
    # 默认目标
    target = "novel_data/lora_dataset/cleaned_顾家明_02_20260116_203605.txt"
    
    # 命令行参数支持
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    if not os.path.exists(target):
        print(f"路径不存在: {target}")
        sys.exit(1)
        
    validate_path(target)
