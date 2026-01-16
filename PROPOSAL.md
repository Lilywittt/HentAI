# 修改方案提案 (Proposal for Modification)

根据您的要求，我制定了以下修改方案，旨在将提示词模板与输出结构分离，并增加数据校验脚本。

## 1. 文件结构变更

我们将 `prompt_template_02.txt` 拆分为两个独立文件，以便于复用和微调：

1.  **`prompt_instruction.txt`** (逻辑指令)
    *   包含角色定义、处理指令、思维链要求等。
    *   包含一个占位符 `{output_schema}` 用于插入输出模板。
2.  **`output_schema.txt`** (输出模板)
    *   仅包含 TypeScript Interface 定义或 JSON Schema。
    *   方便您单独调整输出结构，同时被 `clean_novel_data.py` 读取嵌入提示词。

## 2. 新增校验脚本: `validate_data.py`

这个脚本用于校验生成的 JSON 数据是否符合 `output_schema.txt` 中定义的结构。
为了保证“可复用性和可二次开发性”，我将使用 **Pydantic** 库来定义数据模型。虽然这需要您在修改 `output_schema.txt` (文本) 后，可能需要对应更新 `validate_data.py` 中的 Python 类，但这是目前保证类型安全和逻辑校验最健壮的方法。

(如果您希望完全无需改代码即可校验，我们需要约定 `output_schema.txt` 必须是标准的 JSON Schema 格式，但这可能会降低 LLM 的理解能力，因为 LLM 对 TypeScript 接口格式理解通常更好。因此建议保留 Python 校验代码)

### `validate_data.py` 代码预览

```python
import os
import json
import glob
from typing import List, Optional, Literal
from pydantic import BaseModel, ValidationError, Field

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
    external_action: Optional[str]
    speech_text: Optional[str]
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

def validate_files(data_dir: str):
    json_files = glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)
    print(f"Found {len(json_files)} JSON files. Starting validation...")
    
    passed = 0
    failed = 0
    
    for file_path in json_files:
        # 跳过缓存文件
        if ".cache" in file_path:
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 校验核心
            AnalysisOutput.model_validate(data)
            passed += 1
            
        except json.JSONDecodeError:
            print(f"[ERROR] Invalid JSON format: {file_path}")
            failed += 1
        except ValidationError as e:
            print(f"[FAIL] Schema Mismatch: {file_path}")
            # 打印简化的错误信息
            for err in e.errors():
                loc = "->".join(str(l) for l in err['loc'])
                print(f"  - Location: {loc}, Message: {err['msg']}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] Unexpected error in {file_path}: {str(e)}")
            failed += 1

    print("-" * 30)
    print(f"Validation Complete. Passed: {passed}, Failed: {failed}")

if __name__ == "__main__":
    # 指向生成的数据目录
    TARGET_DIR = "novel_data/lora_dataset" 
    validate_files(TARGET_DIR)
```

## 3. `clean_novel_data.py` 修改预览

主要修改 `PromptManager` 和 `Config`，以及 `NovelCleaner` 的初始化。

**PromptManager 修改:**

```python
class PromptManager:
    @classmethod
    def load_composed_prompt(cls, instruction_file: str, schema_file: str) -> str:
        """读取指令文件和Schema文件，并进行拼接"""
        
        # 读取主指令
        instruction = cls._read_file(instruction_file)
        # 读取Schema
        schema = cls._read_file(schema_file)
        
        # 替换占位符
        # 假设 prompt_instruction.txt 中包含 "{output_schema}" 标记
        if "{output_schema}" in instruction:
            return instruction.replace("{output_schema}", schema)
        else:
            # 如果没有占位符，默认追加在最后
            return f"{instruction}\n\n### Output Schema\n{schema}"

    @staticmethod
    def _read_file(path):
        # ... (原有的读取逻辑) ...
        pass
```

**配置项修改:**

```python
    # Config 中新增
    PROMPT_INSTRUCTION_FILE = "prompt_instruction.txt"
    OUTPUT_SCHEMA_FILE = "output_schema.txt"
```

---

请审查以上方案。如果通过，我将：
1. 创建 `prompt_instruction.txt` 和 `output_schema.txt` (基于现有的 `prompt_template_02.txt`)。
2. 创建 `validate_data.py`。
3. 修改 `clean_novel_data.py`。
