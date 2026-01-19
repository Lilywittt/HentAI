# HentAI: 小说主角语料清洗与 LoRA 训练套件

本项目提供从“原始小说文本”到“LoRA 训练接入”的全流程自动化方案。

---

## ?? 快速开始 (Usage)

### 1. 数据生产流程 (Data Cleaning)
| 步骤 | 运行命令 | 数据来源 (Input) | 数据去向 (Output) | 关键配置 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 切分章节** | `python data_cleaning/split_novel.py` | `novel_data/original_data/*.txt` | `novel_data/split_data/` | 无 |
| **2. 提取交互** | `python data_cleaning/run_pipeline.py` | `novel_data/split_data/` | `novel_data/lora_dataset/` | `config.json`, `nickname_map.json` |
| **3. 格式转换** | `python data_cleaning/convert_to_lora.py --input <路径>` | `novel_data/lora_dataset/` | `novel_data/lora_train_dataset/` | 无 |

### 2. 训练环境部署 (Deployment)
> **详细文档请参考: [lora_deploy/README.md](lora_deploy/README.md)**

| 步骤 | 运行命令 | 数据/资源来源 | 部署去向 (Impact) | 环境变量/关键参数 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 环境初始化** | `bash lora_deploy/deploy_server.sh` | Hugging Face, Gitee | `/root/local-nvme/train_env/` | `MODEL_REPO`, `HF_TOKEN` |
| **2. 数据挂载** | `python lora_deploy/data_interface.py` | `novel_data/lora_train_dataset/` | `train_env/LLaMA-Factory/data/` | 无 |
| **3. 状态自检** | `python lora_deploy/check_env.py` | 部署目录状态 | 控制台输出报告 | 无 |

---

## ?? 关键参数与环境配置

### 1. 外部配置方式 (Input Methods)
*   **配置文件**: `data_cleaning/config.json`
    *   `target_character`: 目标角色。
    *   `source_novel`: 小说名，决定 `nickname_map.json` 中的检索逻辑。
*   **环境变量**:
    *   `DEEPSEEK_API_KEY`: 必须在根目录 `.env` 或系统变量中提供。
    *   `HF_TOKEN`: 下载受限模型时，通过 `export HF_TOKEN=xxx` 传入。
*   **命令行参数**: `run_pipeline.py` 支持 `--prefix`, `--start`, `--end` 等参数覆盖 `config.json` 的设置。

### 2. 脚本对系统的影响 (System Impact)
*   **磁盘占用**: `deploy_server.sh` 会在 `/root/local-nvme` (若存在) 创建约 40GB+ 的数据。
*   **缓存重定向**: 脚本会强制设置 `HF_HOME`，将所有 Hugging Face 下载的临时文件引导至数据盘，避免撑爆 30GB 的系统盘。
*   **数据挂载**: `data_interface.py` 通过 **软链接 (Symlink)** 方式将本项目数据接入训练框架，不占用额外磁盘空间。

---

## ?? 核心目录结构
*   `data_cleaning/`: 清洗逻辑与 Prompt 模板。
*   `lora_deploy/`: 部署脚本与训练框架接口。
*   `novel_data/`: 
    *   `original_data/`: **用户在此放入 TXT 原作。**
    *   `split_data/`: 自动化切分后的章节。
    *   `lora_dataset/`: LLM 提取的原始交互 JSON。
    *   `lora_train_dataset/`: 最终生成的 Alpaca 格式 JSONL。

---

详细技术文档与开发日志请参考 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。
