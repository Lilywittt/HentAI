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

def get_mood_label(mood_zh: str) -> str:
    """直接返回原始情绪词，若为空则返回 neutral"""
    if not mood_zh:
        return "neutral"
    return mood_zh.strip()

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
    mood_label = get_mood_label(mood_state)
    
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
    parts.append(f"<mood:{mood_label}>")
    
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
            # 0. Check for New Direct Schema (Base/Hentai/Identity)
            if "input" in unit and "output" in unit:
                # Direct mapping: Input (Director Instruction) -> Instruction, Output -> Output
                # The 'input' field in Alpaca JSONL is left empty as context is embedded in instruction
                entry = {
                    "id": unit.get("global_id") or unit.get("id"),
                    "instruction": unit["input"],
                    "input": "",
                    "output": unit["output"]
                }
                results.append(entry)
                continue

            # 1. Construct Input (Legacy Schema)
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
    parser.add_argument("--input", "-i", type=str, nargs='+', required=True, help="Input file or directory paths (can be multiple)")
    parser.add_argument("--name", "-n", type=str, help="Target character name (overrides auto-detection)")
    parser.add_argument("--output", "-o", type=str, help="Custom output filename (under lora_train_dataset/)")
    args = parser.parse_args()
    
    input_paths = args.input
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
            
    # 2. Collect Files from all input paths
    all_entries = []
    total_file_count = 0
    total_sample_count = 0
    
    for input_path in input_paths:
        # Check for existence, fallback to default directory if needed
        if not os.path.exists(input_path):
            default_dataset_dir = os.path.join(PROJECT_ROOT, "novel_data", "lora_dataset")
            potential_path = os.path.join(default_dataset_dir, input_path)
            if os.path.exists(potential_path):
                log(f"[Info] Input path not found locally, resolved to default dir: {potential_path}")
                input_path = potential_path

        log(f"[Info] Processing input path: {input_path}")
        files_to_process = []
        if os.path.isfile(input_path):
            files_to_process.append(input_path)
        elif os.path.isdir(input_path):
            files_to_process.extend(glob.glob(os.path.join(input_path, "**/*.txt"), recursive=True))
            files_to_process.extend(glob.glob(os.path.join(input_path, "**/*.json"), recursive=True))
        else:
            log(f"[Error] Input path not found: {input_path}")
            continue

        log(f"[Info] Found {len(files_to_process)} files in this path.")

        # 3. Process Data for current path
        current_character = target_character
        if not current_character:
            # Try to infer from current path
            basename = os.path.basename(os.path.normpath(input_path))
            match = re.match(r"cleaned_([^_]+)_", basename)
            if match:
                current_character = match.group(1)
                log(f"[Info] Inferred character for this path: {current_character}")
            else:
                config = load_config()
                current_character = config.get("target_character") or "Unknown"
                log(f"[Info] Using fallback character for this path: {current_character}")

        for fp in files_to_process:
            entries = process_file(fp, current_character)
            if entries:
                all_entries.extend(entries)
                total_file_count += 1
                total_sample_count += len(entries)
    
    # Re-index IDs to ensure uniqueness across merged datasets
    log(f"[Info] Re-indexing {len(all_entries)} entries to ensure unique IDs...")
    for idx, entry in enumerate(all_entries, 1):
        entry["id"] = idx
            
    # 4. Write Output
    if not all_entries:
        log("[Warning] No valid data extracted.")
        return

    if args.output:
        output_filename = args.output
    else:
        # Use first character name if multiple might exist
        display_name = target_character or "merged"
        output_filename = f"lora_dataset_{display_name}_{timestamp}.jsonl"
        
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in all_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log(f"[Success] Total processed {total_file_count} files, generated {total_sample_count} samples.")
        log(f"[Output] Saved to: {output_path}")
    except Exception as e:
        log(f"[Error] Failed to write output file: {e}")

if __name__ == "__main__":
    main()
