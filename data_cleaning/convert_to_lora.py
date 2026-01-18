# -*- coding: utf-8 -*-
"""
数据转换器 (Data Converter)
功能：将中间态树状 JSON 文件批量转换为 LoRA 训练用的 Alpaca 格式 JSONL 文件。
"""

import os
import json
import glob
import datetime
import argparse
import re
from typing import List, Dict, Any, Optional

# 获取当前脚本所在目录 (data_cleaning)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 data_cleaning 的上一级)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# ==========================================
# 1. 配置与常量
# ==========================================

# 情绪映射表 (中文 -> 英文)
MOOD_MAP = {
    "愤怒": "angry",
    "开心": "happy",
    "悲伤": "sad",
    "恐惧": "fearful",
    "惊讶": "surprised",
    "厌恶": "disgusted",
    "中性": "neutral",
    "平静": "calm",
    "期待": "expectant",
    "焦虑": "anxious",
    "羞涩": "shy",
    "害羞": "shy",
    "尴尬": "awkward",
    "惘然": "dazed",
    "不知所措": "overwhelmed",
    "失落": "lost",
    "绝望": "hopeless",
    "兴奋": "excited",
    "疲惫": "tired",
    "疑惑": "confused",
    "坚定": "determined",
    "痛苦": "painful",
    "温柔": "gentle",
    "冷漠": "indifferent",
    "得意": "proud",
    "无奈": "helpless",
    "紧张": "nervous",
    "警惕": "vigilant",
    "愧疚": "guilty",
    "感动": "touched",
    "委屈": "aggrieved"
}

def load_config(config_path: str = None) -> Dict[str, Any]:
    """加载配置文件"""
    if config_path is None:
        config_path = os.path.join(CURRENT_DIR, "config.json")

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            pass
    return {}

def get_mood_en(mood_zh: str) -> str:
    """将中文情绪转换为英文，未知情绪保留原样或尝试映射"""
    if not mood_zh:
        return "neutral"
    
    # 直接匹配
    if mood_zh in MOOD_MAP:
        return MOOD_MAP[mood_zh]
    
    # 尝试查找包含关键词的映射 (例如 "非常愤怒" -> "angry")
    for k, v in MOOD_MAP.items():
        if k in mood_zh:
            return v
            
    # 如果全是ASCII，假设已经是英文
    if all(ord(c) < 128 for c in mood_zh):
        return mood_zh
        
    return "neutral" # 默认 fallback

# ==========================================
# 2. 核心处理逻辑
# ==========================================

def construct_instruction(meta_info: Dict, unit: Dict, target_character: str) -> str:
    """构造 instruction 字段"""
    scene_snapshot = unit.get("scene_snapshot", "Unknown")
    global_scene_type = meta_info.get("global_scene_type", "Unknown")
    
    char_resp = unit.get("character_response", {})
    active_persona = char_resp.get("active_persona", "Default")
    
    interlocutor = unit.get("interlocutor_info", {})
    interlocutor_name = interlocutor.get("name", "Unknown")
    relationship_tag = interlocutor.get("relationship_tag", "Unknown")
    
    template = (
        f"你现在是{target_character}。\n"
        f"当前场景：{scene_snapshot} (类型：{global_scene_type})。\n"
        f"当前状态：[{active_persona}]。\n"
        f"对话对象：{interlocutor_name} (关系：[{relationship_tag}])。\n"
        f"请基于人设和当前局势进行回应。"
    )
    return template

def construct_input(unit: Dict) -> str:
    """构造 input 字段"""
    trigger = unit.get("trigger", {})
    content = trigger.get("content", "")
    return content.strip()

def construct_output(unit: Dict) -> Optional[str]:
    """构造 output 字段"""
    char_resp = unit.get("character_response", {})
    
    inner_monologue = char_resp.get("inner_monologue", "")
    if inner_monologue:
        inner_monologue = inner_monologue.replace("\n", " ").strip()
    
    # 核心校验：如果 inner_monologue 为空，视为无效数据
    if not inner_monologue:
        return None
        
    external_action = char_resp.get("external_action")
    speech_text = char_resp.get("speech_text")
    mood_state = char_resp.get("mood_state", "neutral")
    mood_en = get_mood_en(mood_state)
    
    # 组装 parts
    parts = []
    
    # 1. <think>...</think>
    parts.append(f"<think>{inner_monologue}</think>")
    
    # 2. *action*
    if external_action:
        parts.append(f"*{external_action.strip()}*")
        
    # 3. speech
    if speech_text:
        parts.append(speech_text.strip())
        
    # 4. <mood:...>
    parts.append(f"<mood:{mood_en}>")
    
    return " ".join(parts)

def process_file(file_path: str, target_character: str) -> List[Dict]:
    """处理单个文件，返回有效的样本列表"""
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            
        meta_info = data.get("meta_info", {})
        interaction_units = data.get("interaction_units", [])
        
        for unit in interaction_units:
            # 1. Construct Input
            inp = construct_input(unit)
            if not inp:
                continue
                
            # 2. Construct Output (includes validation for inner_monologue)
            out = construct_output(unit)
            if not out:
                continue
                
            # 3. Construct Instruction
            instr = construct_instruction(meta_info, unit, target_character)
            
            # 4. Get Global ID
            global_id = unit.get("global_id")
            
            entry = {
                "id": global_id,
                "instruction": instr,
                "input": inp,
                "output": out
            }
            results.append(entry)
            
    except json.JSONDecodeError:
        pass # Ignore JSON errors
    except Exception as e:
        pass
        
    return results

# ==========================================
# 3. 主程序
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Convert intermediate novel data to LoRA JSONL format.")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input file or directory path")
    parser.add_argument("--name", "-n", type=str, help="Target character name (overrides auto-detection)")
    args = parser.parse_args()
    
    input_path = args.input
    target_character = args.name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Setup Output Dir
    output_dir = os.path.join(PROJECT_ROOT, "novel_data", "lora_train_dataset")
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup Logging
    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"conversion_{timestamp}.log")
    
    def log(msg):
        print(msg)
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(msg + "\n")
        except:
            pass
            
    # 1. Determine Target Character
    if not target_character:
        # Try to infer from path
        basename = os.path.basename(os.path.normpath(input_path))
        # Pattern: cleaned_{Name}_{Type}_{Timestamp}
        match = re.match(r"cleaned_([^_]+)_", basename)
        if match:
            target_character = match.group(1)
            log(f"[Info] Detected character name from path: {target_character}")
        else:
            # Fallback to config
            config = load_config()
            target_character = config.get("target_character")
            if target_character:
                log(f"[Info] Using character name from config: {target_character}")
            else:
                target_character = "Unknown"
                log(f"[Warning] Could not detect character name. Using default: {target_character}")
    else:
        log(f"[Info] Using specified character name: {target_character}")

    log(f"[Info] Input Path: {input_path}")
    log(f"[Info] Log file: {log_file}")

    # 2. Collect Files
    files_to_process = []
    if os.path.isfile(input_path):
        files_to_process.append(input_path)
    elif os.path.isdir(input_path):
        files_to_process.extend(glob.glob(os.path.join(input_path, "**/*.txt"), recursive=True))
        files_to_process.extend(glob.glob(os.path.join(input_path, "**/*.json"), recursive=True))
    else:
        log(f"[Error] Input path not found: {input_path}")
        return

    log(f"[Info] Found {len(files_to_process)} files to process.")

    # 3. Process Data
    all_entries = []
    file_count = 0
    sample_count = 0
    
    for fp in files_to_process:
        entries = process_file(fp, target_character)
        if entries:
            all_entries.extend(entries)
            file_count += 1
            sample_count += len(entries)
            
    # 4. Write Output
    if not all_entries:
        log("[Warning] No valid data extracted.")
        return

    output_filename = f"lora_dataset_{target_character}_{timestamp}.jsonl"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in all_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log(f"[Success] Processed {file_count} files, generated {sample_count} samples.")
        log(f"[Output] Saved to: {output_path}")
    except Exception as e:
        log(f"[Error] Failed to write output file: {e}")

if __name__ == "__main__":
    main()
