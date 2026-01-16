# -*- coding: utf-8 -*-
import os
import glob
import datetime
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# --- Global Config ---
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MAX_WORKERS = 5 
BASE_INPUT_DIR = "novel_data/split_data"

if not API_KEY:
    print("Error: DEEPSEEK_API_KEY not found in .env file.")
    exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# System Prompt (Escaped Unicode for safety)
SYSTEM_PROMPT_CONTENT = '### Role Definition\n\u4f60\u662f\u4e00\u4f4d\u8d44\u6df1\u7684\u5c0f\u8bf4\u5267\u672c\u6539\u7f16\u4e13\u5bb6\u3002\u4f60\u7684\u4e13\u957f\u662f\u5c06\u5927\u6bb5\u7684\u5c0f\u8bf4\u6587\u672c\uff08Text\uff09\u89e3\u6784\u4e3a\u7ed3\u6784\u5316\u7684**\u201c\u4ea4\u4e92\u5355\u5143\uff08Interaction Units\uff09\u201d**\u3002\n\u4f60\u5177\u5907\u6781\u5f3a\u7684**\u201c\u6f5c\u53f0\u8bcd\u6d1e\u5bdf\u529b\u201d**\uff0c\u80fd\u591f\u6839\u636e\u4e0a\u4e0b\u6587\u8865\u5168\u89d2\u8272\u672a\u76f4\u63a5\u8868\u8fbe\u7684\u5fc3\u7406\u6d3b\u52a8\u3002\n\n### Task\n\u9605\u8bfb\u63d0\u4f9b\u7684\u5c0f\u8bf4\u6587\u672c\u7247\u6bb5\uff0c\u63d0\u53d6**\u6307\u5b9a\u76ee\u6807\u89d2\u8272**\u53c2\u4e0e\u7684\u6240\u6709\u4ea4\u4e92\u4e8b\u4ef6\u3002\n\n### Extraction Logic (The Universal Paradigm)\n\u4f60\u9700\u8981\u6267\u884c\u4ee5\u4e0b\u4e09\u4e2a\u6b65\u9aa4\u7684\u601d\u7ef4\u94fe\uff1a\n1.  **Observe (\u89c2\u5bdf)**\uff1a\u8bc6\u522b\u5f15\u53d1\u89d2\u8272\u53cd\u5e94\u7684\u5916\u90e8\u4e8b\u4ef6\uff08Trigger\uff09\u3002\n2.  **Extract (\u63d0\u53d6)**\uff1a\u63d0\u53d6\u89d2\u8272\u532d\u539f\u6587\u4e2d\u660e\u786e\u8868\u73b0\u51fa\u7684\u8bed\u8a00\uff08Speech\uff09\u548c\u52a8\u4f5c\uff08Action\uff09\u3002\n3.  **Deduce (\u63a8\u6f14 - \u6838\u5fc3)**\uff1a\n    - \u5982\u679c\u539f\u6587\u4e2d\u6709\u5fc3\u7406\u63cf\u5199\uff0c\u76f4\u63a5\u63d0\u53d6\u3002\n    - **\u5982\u679c\u539f\u6587\u6ca1\u6709\u5fc3\u7406\u63cf\u5199**\uff0c\u4f60\u5fc5\u987b\u6839\u636e**\u5f53\u524d\u573a\u666f\u7684\u4e0a\u4e0b\u6587\uff08Context\uff09**\u548c**\u89d2\u8272\u7684\u884c\u4e3a\u903b\u8f91**\uff0c\u63a8\u6f14\u51fa\u4ed6\u6b64\u523b\u7684**\u6f5c\u53f0\u8bcd\uff08Subtext\uff09**\u3002\n    - *\u63a8\u6f14\u539f\u5219*\uff1a\u601d\u8003\u201c\u4ed6\u4e3a\u4ec0\u4e48\u8fd9\u4e48\u505a\uff1f\u201d\u3001\u201c\u4ed6\u60f3\u8fbe\u5230\u4ec0\u4e48\u76ee\u7684\uff1f\u201d\u3001\u201c\u4ed6\u5728\u9690\u85cf\u4ec0\u4e48\u60c5\u7eea\uff1f\u201d\u3002\n\n### Output Format\n\u8bf7\u8f93\u51fa\u4e25\u683c\u7684 JSON \u683c\u5f0f\uff0c\u4e0d\u8981\u5305\u542b Markdown \u4ee3\u7801\u5757\u6807\u8bb0\uff08\u5982 ```json\uff09\u3002\u7ed3\u6784\u5982\u4e0b\uff1a\n{\n  "interactions": [\n    {\n      "context": "\u5f53\u524d\u573a\u666f\u7684\u7b80\u8981\u80cc\u666f\uff08\u5982\uff1a\u53cc\u65b9\u6b63\u5728\u5bf9\u5cd9/\u95f2\u804a\uff09",\n      "trigger_event": "\u5f15\u53d1\u53cd\u5e94\u7684\u5916\u90e8\u523a\u6fc0\uff08\u5982\uff1a\u5bf9\u65b9\u7684\u6311\u8845/\u63d0\u95ee\uff09",\n      "response": {\n        "speech": "\u89d2\u8272\u7684\u53f0\u8bcd\uff08\u82e5\u65e0\u5219\u586b null\uff09",\n        "action": "\u89d2\u8272\u7684\u52a8\u4f5c\u63cf\u5199\uff08\u82e5\u65e0\u5219\u586b null\uff09",\n        "inner_monologue": "\u3010\u91cd\u70b9\u3011\u89d2\u8272\u7684\u5fc3\u7406\u6d3b\u52a8\u6216\u6f5c\u53f0\u8bcd\uff08\u57fa\u4e8e\u4e0a\u4e0b\u6587\u63a8\u6f14\uff09",\n        "mood": "\u5f53\u524d\u60c5\u7eea\u6807\u7b7e\uff08\u5982\uff1a\u8b66\u60d5/\u5174\u594b/\u65e0\u5948\uff09"\n      }\n    }\n  ]\n}\n'

def process_single_file(file_info):
    input_path, output_path, character_name = file_info
    file_name = os.path.basename(input_path)
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        response = client.chat.completions.create(
            response_format={ "type": "json_object" }, 
            model="deepseek-chat", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_CONTENT},
                {"role": "user", "content": f"Target Character: {character_name}\nFile Name: {file_name}\n\nText Content:\n{content}"},
            ],
            temperature=0.3, 
            stream=False
        )
        result = response.choices[0].message.content
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        return file_name, True, None
    except Exception as e:
        return file_name, False, str(e)

def run_cleaning_task(volume_prefix=None):
    # 1. Scan target directories
    all_volumes = sorted([d for d in glob.glob(os.path.join(BASE_INPUT_DIR, "[0-9][0-9]_*")) if os.path.isdir(d)])
    
    if volume_prefix:
        target_volumes = [v for v in all_volumes if os.path.basename(v).startswith(volume_prefix)]
    else:
        target_volumes = all_volumes

    if not target_volumes:
        print(f"Error: No volumes found matching prefix: {volume_prefix}")
        return

    # 2. Init output and logging
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = 'full' if not volume_prefix else volume_prefix
    output_root = f"novel_data/lora_dataset/cleaned_{suffix}_{timestamp}"
    os.makedirs(output_root, exist_ok=True)

    log_file = os.path.join(output_root, "processing.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)],
        force=True
    )

    logging.info(f"Task Started. Target: {suffix}")
    logging.info(f"Output: {output_root}")

    # 3. Prepare tasks
    tasks = []
    character_name = "\u987e\u5bb6\u660e"
    for vol_dir in target_volumes:
        vol_name = os.path.basename(vol_dir)
        vol_out_dir = os.path.join(output_root, vol_name)
        os.makedirs(vol_out_dir, exist_ok=True)
        for cf in sorted(glob.glob(os.path.join(vol_dir, "*.txt"))):
            tasks.append((cf, os.path.join(vol_out_dir, os.path.basename(cf)), character_name))

    # 4. ThreadPool execution
    success, fail = 0, 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_file, t): t for t in tasks}
        pbar = tqdm(as_completed(futures), total=len(tasks), desc="Cleaning Process", file=sys.stdout)
        
        for i, future in enumerate(pbar):
            fname, ok, err = future.result()
            if ok:
                success += 1
            else:
                fail += 1
                logging.error(f"Failed: {fname} | {err}")
            
            if (i + 1) % 10 == 0 or (i + 1) == len(tasks):
                logging.info(f"Progress: {i+1}/{len(tasks)} (Success: {success}, Fail: {fail})")

    logging.info(f"Task Finished. Success: {success}, Fail: {fail}. Saved to: {output_root}")

if __name__ == "__main__":
    # Clean Volume 2
    run_cleaning_task(volume_prefix="02")
