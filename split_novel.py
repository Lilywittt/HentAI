# -*- coding: utf-8 -*-
import os
import re
import shutil

def split_novel(file_path, output_root):
    """
    Splits a novel text file into volumes and chapters.
    """
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root)

    with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
        content = f.read()

    # Pattern using Unicode escapes
    pattern = r'\n(?=\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07]+[\u5377\u7ae0\u8282]|--\u5916\u7bc7--|\u5916\u7bc7\s+\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07]+\u8282)'
    
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
        
        # Check volume start
        vol_match = re.match(r'^(\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07]+\u5377)', title)
        outer_match = "--\u5916\u7bc7--" in title or title.startswith("\u5916\u7bc7")
        
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
    source_dir = 'novel_data/original_data'
    target_file = None
    if os.path.exists(source_dir):
        for f in os.listdir(source_dir):
            if f.endswith('.txt'):
                target_file = os.path.join(source_dir, f)
                break
    
    if target_file:
        split_novel(target_file, 'novel_data/split_data')
    else:
        print("Source file not found")
