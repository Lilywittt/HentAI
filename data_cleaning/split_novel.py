# -*- coding: utf-8 -*-
"""
本脚本用于将《隐杀》长篇小说 TXT 文件按卷和章节进行自动化拆分。
主要功能：
1. 自动识别“第X卷”、“第X章/节”以及“外篇”标志。
2. 将不同卷的内容存放在独立的子文件夹中。
3. 将原始 GBK 编码转换为 UTF-8 编码，解决乱码问题。
4. 清洗文件名，确保在 Windows 系统下合法且可读。
"""
import os
import re
import shutil

# 获取当前脚本所在目录 (data_cleaning)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 data_cleaning 的上一级)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

def split_novel(file_path, output_root):
    """
    Splits a novel text file into volumes and chapters.
    """
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root)

    with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
        content = f.read()

    # 正则表达式匹配：
    # 1. 第X卷/章/节
    # 2. --外篇--
    # 3. 外篇 第X节
    # 4. --后篇--
    # 5. 后篇 第X章/节
    pattern = r'\n(?=第[一二三四五六七八九十百千万]+[卷章节]|--外篇--|外篇\s+第[一二三四五六七八九十百千万]+节|--后篇--|后篇\s+第[一二三四五六七八九十百千万]+[章节])'
    
    parts = re.split(pattern, content)
    
    header = parts[0]
    intro_dir = os.path.join(output_root, "00_Introduction")
    os.makedirs(intro_dir)
    with open(os.path.join(intro_dir, '000_Intro.txt'), 'w', encoding='utf-8') as f:
        f.write(header)
    
    current_vol_name = "00_Introduction"
    current_vol_idx = 0
    chapter_idx = 1
    
    # Store volume index by name to keep them consistent
    vol_names = {}

    for part in parts[1:]:
        lines = part.strip().split('\n')
        if not lines:
            continue
            
        title = lines[0].strip()
        
        # 检查卷名开始
        vol_match = re.match(r'^(第[一二三四五六七八九十百千万]+卷)', title)
        outer_match = "--外篇--" in title or title.startswith("外篇")
        post_match = "--后篇--" in title or title.startswith("后篇")
        
        if vol_match:
            vol_title_str = vol_match.group(1)
            if vol_title_str not in vol_names:
                current_vol_idx += 1
                vol_names[vol_title_str] = current_vol_idx
            
            this_vol_idx = vol_names[vol_title_str]
            current_vol_name = f"{this_vol_idx:02d}_{vol_title_str}"
            current_vol_name = "".join([c for c in current_vol_name if ord(c) > 127 or c.isalnum() or c in (' ', '-', '_')]).strip()
        elif outer_match and "Outer_Chapters" not in current_vol_name:
            current_vol_idx += 1
            current_vol_name = f"{current_vol_idx:02d}_Outer_Chapters"
        elif post_match and "Post_Chapters" not in current_vol_name:
            current_vol_idx += 1
            current_vol_name = f"{current_vol_idx:02d}_Post_Chapters"
            
        vol_path = os.path.join(output_root, current_vol_name)
        if not os.path.exists(vol_path):
            os.makedirs(vol_path)
            
        # Clean title for filename
        safe_title = "".join([c for c in title if ord(c) > 127 or c.isalnum() or c in (' ', '-', '_')]).strip()
        safe_title = safe_title[:50]
        
        filename = f"{chapter_idx:03d}_{safe_title}.txt"
        if not safe_title:
            filename = f"{chapter_idx:03d}.txt"
            
        with open(os.path.join(vol_path, filename), 'w', encoding='utf-8') as f:
            f.write(part)
        
        chapter_idx += 1

    print(f"Total parts saved: {len(parts)}")
    print(f"Output directory: {output_root}")

if __name__ == "__main__":
    source_dir = os.path.join(PROJECT_ROOT, 'novel_data', 'original_data')
    target_file = None
    if os.path.exists(source_dir):
        for f in os.listdir(source_dir):
            if f.endswith('.txt'):
                target_file = os.path.join(source_dir, f)
                break
    
    if target_file:
        split_novel(target_file, os.path.join(PROJECT_ROOT, 'novel_data', 'split_data'))
    else:
        print("Source file not found")
