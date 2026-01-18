# 小说主角语料清洗与结构化项目 (HentAI)

本项目旨在通过自动化流程，将超长篇小说文本解构为高质量的、适用于 LoRA 训练或 AI Agent 构建的结构化交互语料。系统设计具有高度通用性，可适配不同风格的长篇文学作品。

---

## ?? 新人快速指南 (Quick Start)

### 1. 环境准备
确保已安装 Python 环境，并安装依赖：
```bash
pip install -r requirements.txt
```
确保项目根目录存在 `.env` 文件，并填入 API 密钥：
`DEEPSEEK_API_KEY=你的_API_密钥`

### 2. 运行项目
我们使用 `data_cleaning/run_pipeline.py` 作为统一入口，它会自动读取配置、清洗数据并进行校验。

**方式一：直接运行（使用默认配置）**
```bash
python data_cleaning/run_pipeline.py
```
*默认读取 `data_cleaning/config.json` 中的设置。*

**方式二：通过命令行覆盖配置（推荐调试用）**
```bash
# 仅处理第 5 卷的前 10 章，且不强制刷新缓存
python data_cleaning/run_pipeline.py --prefix 05 --start 1 --end 10 --no-refresh

# 查看所有可用参数
python data_cleaning/run_pipeline.py --help
```

---

## ?? 配置文件详解 (`config.json`)

为了避免频繁修改代码，项目引入了 `config.json` 作为全局配置文件。该文件位于 `data_cleaning` 目录下，被 `run_pipeline.py` 关联并读取。

### 字段说明
你可以直接编辑此文件来固化你的常用设置：

```json
{
  "target_character": "叶灵静",   // 目标角色名称，用于筛选交互
  "source_novel": "隐杀",        // 小说名，用于关联 nickname_map.json 中的昵称
  "target_prefix": null,         // 卷前缀筛选（如 "03"），null 表示处理全本
  "start_chapter": null,         // 起始章节编号（整数），null 不限制
  "end_chapter": null,           // 结束章节编号（整数），null 不限制
  "force_refresh": true          // true: 即使有缓存也重新调用 API; false: 优先使用缓存
}
```

> **注意**：命令行参数（CLI）的优先级高于 `config.json`。如果你在命令行中指定了 `--prefix 05`，那么 `config.json` 中的 `target_prefix` 将被忽略。

---

## ?? 核心功能模块

### 1. 数据预处理 (`split_novel.py`)
将 TXT 长文本切分为章节文件。
*   **输入**：`novel_data/original_data/` 下的 TXT 文件。
*   **输出**：`novel_data/split_data/` 下的分卷目录。
*   **用法**：通常只需要在引入新小说时运行一次。
    ```bash
    python data_cleaning/split_novel.py
    ```

### 2. 数据清洗与提取 (`clean_novel_data.py`)
利用 LLM 提取角色交互数据。
*   **核心逻辑**：基于 `data_cleaning/prompts/prompt_instruction.txt` 中的指令进行提取。
*   **输出**：`novel_data/lora_dataset/` 下的结构化数据。
*   **用法**：一般不需要直接运行，由 `run_pipeline.py` 调用。

### 3. 数据校验 (`validate_data.py`)
检查生成的 JSON 数据是否符合 Schema。
*   **核心逻辑**：基于 `validate_data.py` 中的 Pydantic 模型进行校验。
*   **用法**：由 `run_pipeline.py` 自动调用。

### 4. LoRA 格式转换 (`convert_to_lora.py`)
将中间态树状 JSON 转换为 Alpaca 格式的 `.jsonl` 训练数据。
*   **输入**：`novel_data/lora_dataset/` 下的文件夹或单文件。
*   **输出**：`novel_data/lora_train_dataset/` 下的 `.jsonl` 和日志文件。
*   **用法**：
    ```bash
    # 处理整个文件夹（自动识别角色名）
    python data_cleaning/convert_to_lora.py --input novel_data/lora_dataset/cleaned_柳怀沙_...

    # 处理单文件（指定角色名）
    python data_cleaning/convert_to_lora.py --input example1.txt --name 柳怀沙
    ```

---

## ? 常见问题

**Q: 如何添加新的小说？**
A: 把 TXT 放入 `novel_data/original_data/`，先运行 `python data_cleaning/split_novel.py`，然后修改 `data_cleaning/config.json` 中的 `source_novel` 字段。

**Q: 生成的文件名乱码怎么办？**
A: Windows 终端默认编码可能导致显示乱码，但这不影响文件内容的 UTF-8 编码。建议使用 VS Code 的文件资源管理器查看结果。

**Q: 如何控制成本？**
A: 使用 `--no-refresh` 参数利用缓存；或者在 `config.json` 中设置具体的章节范围 (`start_chapter`, `end_chapter`) 进行小范围测试。

---

## ?? 自动化训练部署 (Auto Deployment)

为了简化 LoRA 训练环境的搭建，项目在 `lora_deploy/` 目录下提供了自动化脚本，支持一键部署训练框架与基座模型。

### 1. 快速部署 (`deploy_server.sh`)
在服务器上拉取本项目后，直接运行此脚本即可完成环境准备：

```bash
cd lora_deploy
# 若下载受限模型，需先设置 Token：export HF_TOKEN="your_token"
bash deploy_server.sh
```

**配置说明**：
*   **更换模型**：编辑 `deploy_server.sh` 顶部的 `MODEL_REPO` 变量。
*   **Hugging Face Access Token**：若模型需要授权（如某些 Llama 模型或私有模型），必须配置 `HF_TOKEN`。推荐通过环境变量传入：`export HF_TOKEN=hf_xxxxxxxxxxxx`。

该脚本会自动执行：
*   在项目外部创建 `../train_env` 目录。
*   拉取 **LLaMA-Factory** 训练框架并安装依赖。
*   下载指定的基座模型（支持断点续传）。

### 2. 数据接入 (`data_interface.py`)
当数据清洗完成（即 `novel_data/lora_train_dataset` 下有 JSONL 文件后），使用此脚本将指定数据“挂载”到训练环境：

```bash
# 方式一：自动使用最新生成的 JSONL 文件
python lora_deploy/data_interface.py

# 方式二：指定文件名（需位于默认数据目录中）
python lora_deploy/data_interface.py --file lora_dataset_叶灵静_20260118.jsonl

# 方式三：指定绝对路径
python lora_deploy/data_interface.py --path /path/to/your/custom.jsonl
```
*   在 LLaMA-Factory 的 data 目录下创建软链接。
*   自动修改 `dataset_info.json` 进行注册。

### 3. 环境自检 (`check_env.py`)
随时运行此脚本检查部署状态：

```bash
python lora_deploy/check_env.py
```
*   输出训练框架、模型路径及数据集注册状态的检查报告。
