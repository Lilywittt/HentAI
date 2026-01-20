# HentAI 训练与验证套件

本目录提供 HentAI 项目的自动化训练、产物收割与聊天验证方案，实现了数据流与存储空间的解耦。

## 数据流与文件流向

### 1. 数据准备 (Input)
*   **直接路径接口**: 执行 `./run_webui.sh <数据集路径>` 可直接指定训练语料。
*   **智能缺省逻辑**: 若未提供路径，脚本将自动扫描 `novel_data/lora_train_dataset/` 并选择**修改时间最新**的 `.jsonl` 文件。
*   **索引机制**: 脚本会自动生成 `dataset_info.json` 并动态调整训练配置。（实现方式：通过环境变量与索引注入将项目路径直接指向 LLaMA-Factory，非物理复制）

### 2. 自动化训练 (Process)
*   **执行脚本**: `./run_webui.sh`。
*   **模型来源**: `/root/local-nvme/train_env/models/Qwen3-14B-Base` (已建立指向 abliterated 的软连接)。
*   **配置载入**: **100% 自动静默填充**。脚本通过劫持 LLaMA-Factory 缓存与配置目录，确保启动后模型、数据集、输出路径等参数已全部回填，无需手动点击。
*   **存储重定向**: 训练产物（Checkpoint/Log）存储在数据盘 `/root/local-nvme/train_output/hentai_lora_results`。

### 3. 产物收割 (Harvest)
*   **执行脚本**: `./collect_lora.sh`。
*   **动作**: 从数据盘同步 LoRA 核心权重（`adapter_*`）到项目目录 `novel_data/lora_train_output/harvested_lora`。
*   **接口**: 可通过脚本内的 `SOURCE_DIR` 和 `DEST_DIR` 调整来源去向。

### 4. 体验验证 (Test)
*   **执行脚本**: `./chat_webui.sh`。
*   **动作**: 抓取 `harvested_lora` 目录下的权重启动 Web 对话端。

## 脚本清单
| 脚本 | 功能 | 默认不运行 |
| :--- | :--- | :---: |
| `run_webui.sh` | 接受数据集路径、自动生成索引、强制注入配置并启动 WebUI | 否 |
| `collect_lora.sh` | 将 LoRA 核心权重同步到项目目录 (Git 排除) | 是 |
| `chat_webui.sh` | 加载收割后的 LoRA 产物进行对话测试 | 是 |

## 配置接口
主要参数在 `configs/hentai_webui_config.yaml` 中配置，包括：
*   `top.model_name`: 基座模型名称。
*   `top.checkpoint_path`: 检查点加载接口。
*   `train.output_dir`: 产物输出路径。
