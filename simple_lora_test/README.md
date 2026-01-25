# HentAI 训练与验证套件

本目录提供 HentAI 项目的自动化训练、产物收割与聊天验证方案，实现了数据流与存储空间的解耦。

## 数据流与文件流向

### 1. 数据准备 (Input)
*   **直接路径接口**: 执行 `./run_webui.sh <数据集路径>` 可直接指定训练语料。
    *   支持**绝对路径**: 如 `/root/workspace/HentAI/novel_data/lora_train_dataset/my_data.jsonl`
    *   支持**相对路径**: 如 `novel_data/lora_train_dataset/my_data.jsonl` 或直接输入文件名 `my_data.jsonl` (会自动在默认目录下搜寻)。
*   **智能缺省逻辑**: 若未提供路径，脚本将自动扫描 `novel_data/lora_train_dataset/` 并选择**修改时间最新**的 `.jsonl` 文件。
*   **索引机制**: 脚本会自动生成 `dataset_info.json` 并动态调整训练配置。（实现方式：通过环境变量与索引注入将项目路径直接指向 LLaMA-Factory，非物理复制）

### 2. 自动化训练 (Process)
*   **执行脚本**: `./run_webui.sh`。
*   **模型来源**: `/root/local-nvme/train_env/models/Qwen3-14B-Base` (已建立指向 abliterated 的软连接)。
*   **配置载入**: **100% 自动静默填充**。脚本通过劫持 LLaMA-Factory 缓存与配置目录，确保启动后参数已自动回填。
*   **存储重定向**: 训练产物存储在数据盘 `/root/local-nvme/train_output/hentai_lora_results`。

### 3. 产物收割 (Harvest)
*   **执行脚本**: `./collect_lora.sh [来源路径/名称] [目标路径/名称]`。
*   **动作**: 将 LoRA 核心权重同步到项目目录。
*   **用法示例**:
    *   **默认**: `./collect_lora.sh` (从默认输出目录同步到默认收割目录)。
    *   **相对路径**: `./collect_lora.sh my_run my_version` (在默认基目录下操作)。
    *   **绝对路径**: `./collect_lora.sh /tmp/src /tmp/dst`。

### 4. 体验验证 (Test)
*   **执行脚本**: `./chat_webui.sh [可选外部LoRA路径]`。
*   **灵活接口**: 
    *   **默认**: 直接运行 `./chat_webui.sh`，加载 `harvested_lora` 目录下的权重。
    *   **指定路径**: 传入路径（如 `./chat_webui.sh /root/local-nvme/train_output/checkpoint-10`）可直接测试原始 Checkpoint。

## 脚本清单
| 脚本 | 功能 | 默认不运行 |
| :--- | :--- | :---: |
| `run_webui.sh` | 接受数据集路径、自动注入配置并启动训练 WebUI | 否 |
| `collect_lora.sh` | 将 LoRA 核心权重同步到项目目录 (Git 排除) | 是 |
| `chat_webui.sh` | 接受 LoRA 路径参数（默认收割目录），启动对话测试 | 是 |

## 配置接口
主要参数在 `configs/hentai_webui_config.yaml` 中配置，包括模型名称、输出路径等。
